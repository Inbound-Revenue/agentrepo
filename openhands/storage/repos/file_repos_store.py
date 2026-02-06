"""File-based implementation of ReposStore."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone

from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.core.logger import openhands_logger as logger
from openhands.integrations.service_types import ProviderType
from openhands.storage import get_file_store
from openhands.storage.data_models.saved_repo import PrewarmedConversation, SavedRepository
from openhands.storage.files import FileStore
from openhands.storage.repos.repos_store import ReposStore
from openhands.utils.async_utils import call_sync_from_async


SAVED_REPOS_FILENAME = 'saved_repos.json'


@dataclass
class FileReposStore(ReposStore):
    """File-based implementation of ReposStore.

    Stores saved repositories as a JSON file using the FileStore abstraction.
    """

    file_store: FileStore
    path: str = SAVED_REPOS_FILENAME

    async def load_all(self) -> list[SavedRepository]:
        """Load all saved repositories from the JSON file."""
        try:
            json_str = await call_sync_from_async(self.file_store.read, self.path)
            data = json.loads(json_str)
            repos = []
            for item in data.get('repositories', []):
                try:
                    repo = self._dict_to_repo(item)
                    repos.append(repo)
                except Exception as e:
                    logger.warning(f'Failed to parse saved repo: {e}')
            return repos
        except FileNotFoundError:
            return []
        except Exception as e:
            logger.error(f'Failed to load saved repos: {e}')
            return []

    async def save_all(self, repos: list[SavedRepository]) -> None:
        """Save all repositories to the JSON file."""
        data = {
            'repositories': [self._repo_to_dict(repo) for repo in repos]
        }
        json_str = json.dumps(data, indent=2, default=str)
        await call_sync_from_async(self.file_store.write, self.path, json_str)

    async def add_repo(self, repo: SavedRepository) -> None:
        """Add a single repository to the saved list."""
        repos = await self.load_all()
        # Check if repo already exists
        for existing in repos:
            if existing.repo_full_name == repo.repo_full_name:
                # Update existing instead of adding duplicate
                existing.branch = repo.branch
                existing.git_provider = repo.git_provider
                existing.pool_size = repo.pool_size
                await self.save_all(repos)
                return
        repos.append(repo)
        await self.save_all(repos)

    async def remove_repo(self, repo_full_name: str) -> bool:
        """Remove a repository by its full name."""
        repos = await self.load_all()
        original_count = len(repos)
        repos = [r for r in repos if r.repo_full_name != repo_full_name]
        if len(repos) < original_count:
            await self.save_all(repos)
            return True
        return False

    async def get_repo(self, repo_full_name: str) -> SavedRepository | None:
        """Get a repository by its full name."""
        repos = await self.load_all()
        for repo in repos:
            if repo.repo_full_name == repo_full_name:
                return repo
        return None

    async def update_repo(self, repo: SavedRepository) -> bool:
        """Update an existing repository."""
        repos = await self.load_all()
        for i, existing in enumerate(repos):
            if existing.repo_full_name == repo.repo_full_name:
                repos[i] = repo
                await self.save_all(repos)
                return True
        return False

    def _prewarmed_conv_to_dict(self, conv: PrewarmedConversation) -> dict:
        """Convert a PrewarmedConversation to a dictionary."""
        return {
            'conversation_id': conv.conversation_id,
            'status': conv.status,
            'created_at': conv.created_at.isoformat() if conv.created_at else None,
            'error_message': conv.error_message,
        }

    def _dict_to_prewarmed_conv(self, data: dict) -> PrewarmedConversation:
        """Convert a dictionary to a PrewarmedConversation."""
        created_at = data.get('created_at')
        if created_at and isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at)
        else:
            created_at = datetime.now(timezone.utc)

        return PrewarmedConversation(
            conversation_id=data['conversation_id'],
            status=data.get('status', 'pending'),
            created_at=created_at,
            error_message=data.get('error_message'),
        )

    def _repo_to_dict(self, repo: SavedRepository) -> dict:
        """Convert a SavedRepository to a dictionary for JSON serialization."""
        return {
            'repo_full_name': repo.repo_full_name,
            'branch': repo.branch,
            'git_provider': repo.git_provider.value if isinstance(repo.git_provider, ProviderType) else repo.git_provider,
            'added_at': repo.added_at.isoformat() if repo.added_at else None,
            'last_commit_sha': repo.last_commit_sha,
            'pool_size': repo.pool_size,
            'prewarmed_conversations': [
                self._prewarmed_conv_to_dict(c) for c in repo.prewarmed_conversations
            ],
            # Legacy fields
            'prewarmed_conversation_id': repo.prewarmed_conversation_id,
            'prewarmed_status': repo.prewarmed_status,
        }

    def _dict_to_repo(self, data: dict) -> SavedRepository:
        """Convert a dictionary to a SavedRepository."""
        added_at = data.get('added_at')
        if added_at and isinstance(added_at, str):
            added_at = datetime.fromisoformat(added_at)
        else:
            added_at = datetime.now(timezone.utc)

        git_provider = data.get('git_provider', 'github')
        if isinstance(git_provider, str):
            git_provider = ProviderType(git_provider)

        # Parse prewarmed conversations list
        prewarmed_conversations = []
        for conv_data in data.get('prewarmed_conversations', []):
            try:
                prewarmed_conversations.append(self._dict_to_prewarmed_conv(conv_data))
            except Exception as e:
                logger.warning(f'Failed to parse prewarmed conversation: {e}')

        return SavedRepository(
            repo_full_name=data['repo_full_name'],
            branch=data.get('branch', 'main'),
            git_provider=git_provider,
            added_at=added_at,
            last_commit_sha=data.get('last_commit_sha'),
            pool_size=data.get('pool_size', 2),
            prewarmed_conversations=prewarmed_conversations,
            # Legacy fields
            prewarmed_conversation_id=data.get('prewarmed_conversation_id'),
            prewarmed_status=data.get('prewarmed_status', 'pending'),
        )

    @classmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> FileReposStore:
        """Get a store instance for the given configuration."""
        file_store = get_file_store(
            file_store_type=config.file_store,
            file_store_path=config.file_store_path,
            file_store_web_hook_url=config.file_store_web_hook_url,
            file_store_web_hook_headers=config.file_store_web_hook_headers,
            file_store_web_hook_batch=config.file_store_web_hook_batch,
        )
        return FileReposStore(file_store)
