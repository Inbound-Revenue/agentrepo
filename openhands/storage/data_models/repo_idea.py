"""Data model for repository ideas/issues."""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RepoIdea:
    """An idea or issue associated with a repository.
    
    Ideas start in the "Ideas & Issues" column and can be
    moved to "Building" when the user wants to start working on them.
    """

    id: str  # UUID
    repo_full_name: str  # Parent repo (e.g., "owner/repo")
    user_id: str  # Owner of this idea (per-user storage)
    text: str  # The idea/issue text
    order: int  # Position in list (for reordering)
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    
    # When moved to "Building" column
    building_conversation_id: str | None = None
    building_status: str | None = None  # 'running', 'review', 'error', 'queued'
    building_started_at: datetime | None = None
    building_error_message: str | None = None
