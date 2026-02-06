"""Manages a pool of pre-warmed conversations for saved repositories.

This module provides the ConversationPoolManager which maintains ready-to-use
conversations for each saved repository, enabling instant conversation starts.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING

from openhands.core.logger import openhands_logger as logger
from openhands.integrations.service_types import ProviderType
from openhands.server.shared import config
from openhands.storage.data_models.saved_repo import PrewarmedConversation, SavedRepository
from openhands.storage.repos.file_repos_store import FileReposStore

if TYPE_CHECKING:
    from openhands.storage.repos.repos_store import ReposStore


@dataclass
class ConversationPoolManager:
    """Manages pre-warmed conversation pools for saved repositories.
    
    This manager:
    - Maintains a pool of ready-to-use conversations per saved repo
    - Automatically spawns new conversations when pool is depleted
    - Handles invalidation when code changes are detected
    - Integrates with server startup to pre-warm all saved repos
    """
    
    repos_store: ReposStore | None = None
    _prewarm_tasks: dict[str, asyncio.Task] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _initialized: bool = False
    
    async def initialize(self) -> None:
        """Initialize the pool manager and start pre-warming all saved repos."""
        if self._initialized:
            return
            
        logger.info('Initializing ConversationPoolManager')
        self.repos_store = await FileReposStore.get_instance(config, user_id=None)
        
        # Load all saved repos and start pre-warming
        repos = await self.repos_store.load_all()
        logger.info(f'Found {len(repos)} saved repositories to pre-warm')
        
        for repo in repos:
            # Don't await - let them run in parallel
            asyncio.create_task(self._ensure_pool_filled(repo.repo_full_name))
        
        self._initialized = True
        logger.info('ConversationPoolManager initialized')
    
    async def shutdown(self) -> None:
        """Shutdown the pool manager and cancel all pending tasks."""
        logger.info('Shutting down ConversationPoolManager')
        for task in self._prewarm_tasks.values():
            task.cancel()
        self._prewarm_tasks.clear()
        self._initialized = False
    
    async def _get_repos_store(self) -> ReposStore:
        """Get the repos store, initializing if needed."""
        if self.repos_store is None:
            self.repos_store = await FileReposStore.get_instance(config, user_id=None)
        return self.repos_store
    
    async def prewarm_for_repo(self, repo_full_name: str) -> None:
        """Start pre-warming conversations for a specific repository.
        
        This is called when:
        - A new repo is added
        - Code changes are detected (after invalidation)
        - Server starts up
        """
        logger.info(f'Pre-warming conversations for repo: {repo_full_name}')
        await self._ensure_pool_filled(repo_full_name)
    
    async def _ensure_pool_filled(self, repo_full_name: str) -> None:
        """Ensure the conversation pool for a repo is filled to pool_size."""
        async with self._lock:
            repos_store = await self._get_repos_store()
            repo = await repos_store.get_repo(repo_full_name)
            
            if not repo:
                logger.warning(f'Repository not found: {repo_full_name}')
                return
            
            # Check how many more conversations we need
            while repo.needs_more_conversations():
                # Create a new pre-warmed conversation entry
                conv_id = uuid.uuid4().hex
                prewarmed_conv = PrewarmedConversation(
                    conversation_id=conv_id,
                    status='warming',
                    created_at=datetime.now(timezone.utc),
                    warming_step='queued',
                )
                repo.prewarmed_conversations.append(prewarmed_conv)
                await repos_store.update_repo(repo)
                
                # Spawn the actual conversation warming in background
                task = asyncio.create_task(
                    self._warm_conversation(repo_full_name, conv_id)
                )
                self._prewarm_tasks[conv_id] = task
                
                # Reload repo to get updated state
                repo = await repos_store.get_repo(repo_full_name)
                if not repo:
                    break
    
    async def _warm_conversation(self, repo_full_name: str, conversation_id: str) -> None:
        """Actually warm up a conversation (create it and run autostart).
        
        This creates the conversation metadata and starts the agent loop,
        which will clone the repo and run any autostart commands.
        """
        try:
            logger.info(f'Warming conversation {conversation_id} for repo {repo_full_name}')
            
            # Step 1: Initializing
            await self._update_conversation_status(
                repo_full_name, conversation_id, 'warming', warming_step='initializing'
            )
            
            repos_store = await self._get_repos_store()
            repo = await repos_store.get_repo(repo_full_name)
            if not repo:
                logger.error(f'Repository not found during warming: {repo_full_name}')
                return
            
            # Import here to avoid circular imports
            from openhands.server.services.conversation_service import initialize_conversation
            from openhands.storage.data_models.conversation_metadata import ConversationTrigger
            
            # Step 2: Creating conversation metadata
            await self._update_conversation_status(
                repo_full_name, conversation_id, 'warming', warming_step='creating_metadata'
            )
            
            # Initialize the conversation metadata
            await initialize_conversation(
                user_id=None,  # Pre-warmed conversations are not user-specific initially
                conversation_id=conversation_id,
                selected_repository=repo.repo_full_name,
                selected_branch=repo.branch,
                conversation_trigger=ConversationTrigger.GUI,
                git_provider=repo.git_provider if isinstance(repo.git_provider, ProviderType) else ProviderType(repo.git_provider),
            )
            
            # Note: We don't start the full agent loop here because that requires
            # user settings (API keys, etc.). The conversation is "warm" when:
            # 1. Metadata is created
            # 2. The conversation can be quickly resumed with user settings
            # 
            # For full pre-warming with autostart, we'd need to:
            # - Store default settings or use service account
            # - Actually start the runtime and run autostart commands
            # This is a future enhancement.
            
            # Update status to ready
            await self._update_conversation_status(
                repo_full_name, conversation_id, 'ready', warming_step='ready'
            )
            logger.info(f'Conversation {conversation_id} is ready for repo {repo_full_name}')
            
        except Exception as e:
            logger.error(f'Error warming conversation {conversation_id}: {e}')
            await self._update_conversation_status(
                repo_full_name, conversation_id, 'error', str(e), warming_step='error'
            )
        finally:
            # Clean up task reference
            self._prewarm_tasks.pop(conversation_id, None)
    
    async def _update_conversation_status(
        self, 
        repo_full_name: str, 
        conversation_id: str, 
        status: str,
        error_message: str | None = None,
        warming_step: str | None = None,
    ) -> None:
        """Update the status of a pre-warmed conversation."""
        async with self._lock:
            repos_store = await self._get_repos_store()
            repo = await repos_store.get_repo(repo_full_name)
            if not repo:
                return
            
            for conv in repo.prewarmed_conversations:
                if conv.conversation_id == conversation_id:
                    conv.status = status
                    conv.error_message = error_message
                    if warming_step is not None:
                        conv.warming_step = warming_step
                    break
            
            await repos_store.update_repo(repo)
    
    async def claim_conversation(self, repo_full_name: str) -> str | None:
        """Claim a ready conversation from the pool for immediate use.
        
        Returns the conversation_id if one is available, None otherwise.
        After claiming, automatically triggers spawning a replacement.
        """
        async with self._lock:
            repos_store = await self._get_repos_store()
            repo = await repos_store.get_repo(repo_full_name)
            
            if not repo:
                logger.warning(f'Cannot claim: repository not found: {repo_full_name}')
                return None
            
            # Find a ready conversation
            ready_convs = repo.get_ready_conversations()
            if not ready_convs:
                logger.warning(f'No ready conversations for repo: {repo_full_name}')
                return None
            
            # Claim the oldest ready conversation
            claimed = ready_convs[0]
            conversation_id = claimed.conversation_id
            
            # Remove from pool
            repo.prewarmed_conversations = [
                c for c in repo.prewarmed_conversations 
                if c.conversation_id != conversation_id
            ]
            await repos_store.update_repo(repo)
            
            logger.info(f'Claimed conversation {conversation_id} for repo {repo_full_name}')
        
        # Trigger refill outside the lock
        asyncio.create_task(self._ensure_pool_filled(repo_full_name))
        
        return conversation_id
    
    async def invalidate_for_repo(self, repo_full_name: str) -> None:
        """Invalidate all pre-warmed conversations for a repo.
        
        Called when code changes are detected (e.g., via GitHub webhook).
        This removes all existing pre-warmed conversations and starts fresh.
        """
        logger.info(f'Invalidating pre-warmed conversations for repo: {repo_full_name}')
        
        async with self._lock:
            repos_store = await self._get_repos_store()
            repo = await repos_store.get_repo(repo_full_name)
            
            if not repo:
                logger.warning(f'Cannot invalidate: repository not found: {repo_full_name}')
                return
            
            # Cancel any warming tasks for this repo
            for conv in repo.prewarmed_conversations:
                task = self._prewarm_tasks.pop(conv.conversation_id, None)
                if task:
                    task.cancel()
            
            # Clear all pre-warmed conversations
            repo.prewarmed_conversations = []
            await repos_store.update_repo(repo)
        
        # Start fresh pre-warming
        await self.prewarm_for_repo(repo_full_name)
    
    async def get_pool_status(self) -> dict:
        """Get the status of all conversation pools."""
        repos_store = await self._get_repos_store()
        repos = await repos_store.load_all()
        
        status = {
            'initialized': self._initialized,
            'repos': []
        }
        
        for repo in repos:
            repo_status = {
                'repo_full_name': repo.repo_full_name,
                'branch': repo.branch,
                'pool_size': repo.pool_size,
                'ready_count': len(repo.get_ready_conversations()),
                'warming_count': repo.get_warming_count(),
                'conversations': [
                    {
                        'conversation_id': c.conversation_id,
                        'status': c.status,
                        'created_at': c.created_at.isoformat() if c.created_at else None,
                        'error_message': c.error_message,
                    }
                    for c in repo.prewarmed_conversations
                ]
            }
            status['repos'].append(repo_status)
        
        return status


# Global singleton instance
_pool_manager: ConversationPoolManager | None = None


async def get_pool_manager() -> ConversationPoolManager:
    """Get the global ConversationPoolManager instance."""
    global _pool_manager
    if _pool_manager is None:
        _pool_manager = ConversationPoolManager()
    return _pool_manager


async def initialize_pool_manager() -> None:
    """Initialize the global pool manager."""
    manager = await get_pool_manager()
    await manager.initialize()


async def shutdown_pool_manager() -> None:
    """Shutdown the global pool manager."""
    global _pool_manager
    if _pool_manager:
        await _pool_manager.shutdown()
        _pool_manager = None
