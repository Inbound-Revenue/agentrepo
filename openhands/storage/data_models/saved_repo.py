"""Data model for saved repositories."""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from openhands.integrations.service_types import ProviderType


@dataclass
class PrewarmedConversation:
    """A single pre-warmed conversation in the pool."""

    conversation_id: str
    status: str = 'pending'  # 'pending', 'warming', 'ready', 'error'
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    error_message: str | None = None
    # Current step in the warming process for UI feedback
    warming_step: str | None = None  # e.g., 'initializing', 'cloning_repo', 'building_runtime', 'ready'


@dataclass
class SavedRepository:
    """A repository that has been saved/added by the user for quick access.

    This is used to maintain a list of repositories that should have
    pre-warmed conversations ready to go.
    """

    repo_full_name: str  # e.g., "Inbound-Revenue/agentrepo"
    branch: str  # e.g., "main"
    git_provider: ProviderType  # e.g., ProviderType.GITHUB
    added_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    # For detecting code changes
    last_commit_sha: str | None = None
    # Number of pre-warmed conversations to maintain in the pool
    pool_size: int = 2
    # List of pre-warmed conversations in the pool
    prewarmed_conversations: list[PrewarmedConversation] = field(default_factory=list)

    # Legacy fields for backward compatibility (will be migrated)
    prewarmed_conversation_id: str | None = None
    prewarmed_status: str = 'pending'

    def get_ready_conversations(self) -> list[PrewarmedConversation]:
        """Get all conversations that are ready to be claimed."""
        return [c for c in self.prewarmed_conversations if c.status == 'ready']

    def get_warming_count(self) -> int:
        """Get count of conversations currently being warmed."""
        return len([c for c in self.prewarmed_conversations if c.status == 'warming'])

    def needs_more_conversations(self) -> bool:
        """Check if we need to spawn more pre-warmed conversations."""
        active_count = len([c for c in self.prewarmed_conversations 
                          if c.status in ('ready', 'warming')])
        return active_count < self.pool_size
