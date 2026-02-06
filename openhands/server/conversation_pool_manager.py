"""Manages a pool of pre-warmed conversations for saved repositories.

This module provides the ConversationPoolManager which maintains ready-to-use
conversations for each saved repository, enabling instant conversation starts.

The pre-warming process starts REAL conversations that go through the full
initialization including runtime creation, repo cloning, and autostart commands.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from openhands.core.logger import openhands_logger as logger
from openhands.integrations.provider import PROVIDER_TOKEN_TYPE
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
    - Starts REAL conversations with full runtime, repo clone, and autostart
    - Automatically spawns new conversations when pool is depleted
    - Handles invalidation when code changes are detected
    """
    
    repos_store: ReposStore | None = None
    _prewarm_tasks: dict[str, asyncio.Task] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    _initialized: bool = False
    # Store user credentials for pre-warming (keyed by repo_full_name)
    _repo_credentials: dict[str, dict[str, Any]] = field(default_factory=dict)
    
    async def initialize(self) -> None:
        """Initialize the pool manager and start pre-warming all saved repos."""
        if self._initialized:
            return
            
        logger.info('Initializing ConversationPoolManager')
        self.repos_store = await FileReposStore.get_instance(config, user_id=None)
        
        # Load all saved repos - pre-warming will happen when credentials are provided
        repos = await self.repos_store.load_all()
        logger.info(f'Found {len(repos)} saved repositories (awaiting credentials for pre-warm)')
        
        self._initialized = True
        logger.info('ConversationPoolManager initialized')
    
    async def shutdown(self) -> None:
        """Shutdown the pool manager and cancel all pending tasks."""
        logger.info('Shutting down ConversationPoolManager')
        for task in self._prewarm_tasks.values():
            task.cancel()
        self._prewarm_tasks.clear()
        self._repo_credentials.clear()
        self._initialized = False
    
    async def _get_repos_store(self) -> ReposStore:
        """Get the repos store, initializing if needed."""
        if self.repos_store is None:
            self.repos_store = await FileReposStore.get_instance(config, user_id=None)
        return self.repos_store
    
    def set_credentials_for_repo(
        self, 
        repo_full_name: str, 
        user_id: str | None,
        provider_tokens: PROVIDER_TOKEN_TYPE | None,
    ) -> None:
        """Store credentials for a repo to use during pre-warming.
        
        Called when a user adds a repo - we capture their credentials
        so we can start real conversations in the background.
        """
        self._repo_credentials[repo_full_name] = {
            'user_id': user_id,
            'provider_tokens': provider_tokens,
        }
        logger.info(f'Stored credentials for repo: {repo_full_name}')
    
    async def prewarm_for_repo(
        self, 
        repo_full_name: str,
        user_id: str | None = None,
        provider_tokens: PROVIDER_TOKEN_TYPE | None = None,
    ) -> None:
        """Start pre-warming conversations for a specific repository.
        
        This is called when:
        - A new repo is added (with user credentials)
        - Code changes are detected (after invalidation)
        - Manually triggered
        
        If user_id and provider_tokens are provided, they're stored for future use.
        """
        if user_id or provider_tokens:
            self.set_credentials_for_repo(repo_full_name, user_id, provider_tokens)
        
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
        """Actually warm up a conversation by starting a REAL agent session.
        
        This creates a full conversation with:
        1. Runtime (Docker container)
        2. Repo cloned into the container
        3. All autostart.yaml commands executed
        
        The conversation will be fully ready when the user claims it.
        """
        try:
            logger.info(f'Starting REAL warming for conversation {conversation_id} for repo {repo_full_name}')
            
            # Step 1: Initializing
            await self._update_conversation_status(
                repo_full_name, conversation_id, 'warming', warming_step='initializing'
            )
            
            repos_store = await self._get_repos_store()
            repo = await repos_store.get_repo(repo_full_name)
            if not repo:
                logger.error(f'Repository not found during warming: {repo_full_name}')
                await self._update_conversation_status(
                    repo_full_name, conversation_id, 'error', 'Repository not found', warming_step='error'
                )
                return
            
            # Get stored credentials
            credentials = self._repo_credentials.get(repo_full_name, {})
            user_id = credentials.get('user_id')
            provider_tokens = credentials.get('provider_tokens')
            
            if not provider_tokens:
                logger.warning(f'No credentials stored for {repo_full_name}, falling back to metadata-only warming')
                # Fall back to just creating metadata (fast but not fully warmed)
                await self._warm_conversation_metadata_only(repo_full_name, conversation_id, repo)
                return
            
            # Import here to avoid circular imports
            from openhands.server.services.conversation_service import create_new_conversation
            from openhands.storage.data_models.conversation_metadata import ConversationTrigger
            
            # Step 2: Starting full conversation (this does EVERYTHING including autostart)
            await self._update_conversation_status(
                repo_full_name, conversation_id, 'warming', warming_step='cloning_repo'
            )
            
            logger.info(f'Creating FULL conversation {conversation_id} with runtime for {repo_full_name}')
            
            try:
                # This will:
                # 1. Create conversation metadata
                # 2. Start the runtime (Docker container) in background
                # 3. Clone the repository
                # 4. Run setup scripts
                # 5. Execute ALL autostart commands
                # NOTE: create_new_conversation returns immediately after scheduling
                # the background task, so we need to wait for the runtime to be ready
                await create_new_conversation(
                    user_id=user_id,
                    git_provider_tokens=provider_tokens,
                    custom_secrets=None,
                    selected_repository=repo.repo_full_name,
                    selected_branch=repo.branch,
                    initial_user_msg=None,  # No initial message - just warm it up
                    image_urls=None,
                    replay_json=None,
                    conversation_instructions=None,
                    conversation_trigger=ConversationTrigger.GUI,
                    git_provider=repo.git_provider if isinstance(repo.git_provider, ProviderType) else ProviderType(repo.git_provider),
                    conversation_id=conversation_id,
                )
                
                # Wait for the runtime to actually be ready
                # create_new_conversation returns immediately, but runtime init happens in background
                await self._wait_for_runtime_ready(repo_full_name, conversation_id)
                
                # Update status to ready - the conversation is now FULLY warmed
                await self._update_conversation_status(
                    repo_full_name, conversation_id, 'ready', warming_step='ready'
                )
                logger.info(f'Conversation {conversation_id} is FULLY ready for repo {repo_full_name}')
                
            except Exception as e:
                error_msg = str(e)
                logger.error(f'Failed to create full conversation {conversation_id}: {error_msg}')
                
                # Check if it's a settings/auth error - these are expected if user hasn't configured LLM
                if 'Settings not found' in error_msg or 'LLM' in error_msg or 'API key' in error_msg:
                    logger.info(f'Settings not configured, falling back to metadata-only warming')
                    await self._warm_conversation_metadata_only(repo_full_name, conversation_id, repo)
                else:
                    await self._update_conversation_status(
                        repo_full_name, conversation_id, 'error', error_msg, warming_step='error'
                    )
            
        except Exception as e:
            logger.error(f'Error warming conversation {conversation_id}: {e}')
            await self._update_conversation_status(
                repo_full_name, conversation_id, 'error', str(e), warming_step='error'
            )
        finally:
            # Clean up task reference
            self._prewarm_tasks.pop(conversation_id, None)
    
    async def _wait_for_runtime_ready(
        self, 
        repo_full_name: str, 
        conversation_id: str,
        timeout_seconds: int = 600,  # 10 minute timeout for full warmup
        poll_interval: float = 5.0,
    ) -> None:
        """Wait for the runtime to be fully initialized including autostart commands.
        
        This polls the conversation manager to check if the agent state has moved
        past LOADING, indicating the runtime is ready for use.
        """
        from openhands.core.schema.agent import AgentState
        from openhands.server.shared import conversation_manager
        
        start_time = asyncio.get_event_loop().time()
        last_step = 'cloning_repo'
        
        while True:
            elapsed = asyncio.get_event_loop().time() - start_time
            if elapsed > timeout_seconds:
                logger.warning(f'Timeout waiting for runtime {conversation_id} to be ready after {elapsed:.0f}s')
                raise TimeoutError(f'Runtime {conversation_id} did not become ready within {timeout_seconds}s')
            
            # Check if the session exists and has a runtime
            session = conversation_manager._local_agent_loops_by_sid.get(conversation_id)
            
            if session and session.agent_session:
                agent_session = session.agent_session
                
                # Check runtime status
                if agent_session.runtime and agent_session.runtime.runtime_initialized:
                    # Runtime is initialized, now check agent state
                    if agent_session.controller:
                        state = agent_session.controller.get_state()
                        if state and state.agent_state != AgentState.LOADING:
                            logger.info(f'Runtime {conversation_id} is ready (state: {state.agent_state}, elapsed: {elapsed:.0f}s)')
                            return
                        else:
                            # Still loading but runtime exists
                            if last_step != 'starting_agent':
                                last_step = 'starting_agent'
                                await self._update_conversation_status(
                                    repo_full_name, conversation_id, 'warming', warming_step='starting_agent'
                                )
                    else:
                        # Runtime exists but no controller yet
                        if last_step != 'building_runtime':
                            last_step = 'building_runtime'
                            await self._update_conversation_status(
                                repo_full_name, conversation_id, 'warming', warming_step='building_runtime'
                            )
                else:
                    # No runtime yet
                    if last_step != 'cloning_repo' and elapsed > 10:
                        last_step = 'cloning_repo'
                        await self._update_conversation_status(
                            repo_full_name, conversation_id, 'warming', warming_step='cloning_repo'
                        )
            
            logger.debug(f'Waiting for runtime {conversation_id}... ({elapsed:.0f}s elapsed)')
            await asyncio.sleep(poll_interval)

    async def _warm_conversation_metadata_only(
        self, 
        repo_full_name: str, 
        conversation_id: str,
        repo: SavedRepository,
    ) -> None:
        """Fallback: Create only conversation metadata (fast, but not fully warmed).
        
        This is used when we don't have user credentials or settings.
        The conversation will need to do the full startup when claimed.
        """
        from openhands.server.services.conversation_service import initialize_conversation
        from openhands.storage.data_models.conversation_metadata import ConversationTrigger
        
        await self._update_conversation_status(
            repo_full_name, conversation_id, 'warming', warming_step='creating_metadata'
        )
        
        # Just create the metadata
        await initialize_conversation(
            user_id=None,
            conversation_id=conversation_id,
            selected_repository=repo.repo_full_name,
            selected_branch=repo.branch,
            conversation_trigger=ConversationTrigger.GUI,
            git_provider=repo.git_provider if isinstance(repo.git_provider, ProviderType) else ProviderType(repo.git_provider),
        )
        
        # Mark as ready (though it's only metadata-ready, not runtime-ready)
        await self._update_conversation_status(
            repo_full_name, conversation_id, 'ready', warming_step='ready'
        )
        logger.info(f'Conversation {conversation_id} metadata ready (runtime will start on claim)')
    
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
