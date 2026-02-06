"""Abstract base class for saved repositories storage."""

from __future__ import annotations

from abc import ABC, abstractmethod

from openhands.core.config.openhands_config import OpenHandsConfig
from openhands.storage.data_models.saved_repo import SavedRepository


class ReposStore(ABC):
    """Abstract base class for saved repositories storage.

    This is an extension point in OpenHands that allows applications to customize how
    saved repositories are stored. Applications can substitute their own implementation by:
    1. Creating a class that inherits from ReposStore
    2. Implementing all required methods
    3. Setting the appropriate config to use the custom class

    The default implementation uses file-based storage (FileReposStore).
    """

    @abstractmethod
    async def load_all(self) -> list[SavedRepository]:
        """Load all saved repositories."""

    @abstractmethod
    async def save_all(self, repos: list[SavedRepository]) -> None:
        """Save all repositories (replaces existing)."""

    @abstractmethod
    async def add_repo(self, repo: SavedRepository) -> None:
        """Add a single repository to the saved list."""

    @abstractmethod
    async def remove_repo(self, repo_full_name: str) -> bool:
        """Remove a repository by its full name.

        Returns True if the repo was found and removed, False otherwise.
        """

    @abstractmethod
    async def get_repo(self, repo_full_name: str) -> SavedRepository | None:
        """Get a repository by its full name."""

    @abstractmethod
    async def update_repo(self, repo: SavedRepository) -> bool:
        """Update an existing repository.

        Returns True if the repo was found and updated, False otherwise.
        """

    @classmethod
    @abstractmethod
    async def get_instance(
        cls, config: OpenHandsConfig, user_id: str | None
    ) -> ReposStore:
        """Get a store instance for the given user."""
