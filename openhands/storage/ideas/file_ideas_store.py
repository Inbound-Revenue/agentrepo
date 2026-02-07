"""File-based storage for repository ideas."""

from __future__ import annotations

import json
import uuid
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from openhands.core.logger import openhands_logger as logger
from openhands.storage import get_file_store
from openhands.storage.data_models.repo_idea import RepoIdea
from openhands.storage.files import FileStore

if TYPE_CHECKING:
    from openhands.core.config.openhands_config import OpenHandsConfig


def _encode_repo_name(repo_full_name: str) -> str:
    """Encode repo name for use in file paths."""
    return repo_full_name.replace('/', '__')


def _idea_to_dict(idea: RepoIdea) -> dict:
    """Convert a RepoIdea to a dictionary for JSON serialization."""
    data = asdict(idea)
    # Convert datetimes to ISO format
    for key in ['created_at', 'updated_at', 'building_started_at']:
        if data.get(key) and isinstance(data[key], datetime):
            data[key] = data[key].isoformat()
    return data


def _dict_to_idea(data: dict) -> RepoIdea:
    """Convert a dictionary to a RepoIdea."""
    # Parse datetimes from ISO format
    for key in ['created_at', 'updated_at', 'building_started_at']:
        if data.get(key) and isinstance(data[key], str):
            data[key] = datetime.fromisoformat(data[key])
    return RepoIdea(**data)


class FileIdeasStore:
    """File-based storage for repository ideas.
    
    Ideas are stored per-user, per-repo in JSON files.
    Storage location: {file_store_path}/ideas/{user_id}/{encoded_repo_name}.json
    """

    def __init__(self, file_store: FileStore, user_id: str):
        self.file_store = file_store
        self.user_id = user_id

    def _get_ideas_file_path(self, repo_full_name: str) -> str:
        """Get the file path for a repo's ideas."""
        encoded_name = _encode_repo_name(repo_full_name)
        return f'ideas/{self.user_id}/{encoded_name}.json'

    def _load_ideas_file(self, repo_full_name: str) -> list[dict]:
        """Load the raw ideas data from file."""
        file_path = self._get_ideas_file_path(repo_full_name)
        try:
            content = self.file_store.read(file_path)
            return json.loads(content)
        except FileNotFoundError:
            return []
        except json.JSONDecodeError as e:
            logger.error(f'Error parsing ideas file {file_path}: {e}')
            return []

    def _save_ideas_file(self, repo_full_name: str, ideas: list[dict]) -> None:
        """Save the ideas data to file."""
        file_path = self._get_ideas_file_path(repo_full_name)
        content = json.dumps(ideas, indent=2)
        self.file_store.write(file_path, content)

    async def load_ideas(self, repo_full_name: str) -> list[RepoIdea]:
        """Load all ideas for a repository."""
        ideas_data = self._load_ideas_file(repo_full_name)
        ideas = [_dict_to_idea(data) for data in ideas_data]
        # Sort by order
        ideas.sort(key=lambda x: x.order)
        return ideas

    async def get_idea(self, repo_full_name: str, idea_id: str) -> RepoIdea | None:
        """Get a specific idea by ID."""
        ideas = await self.load_ideas(repo_full_name)
        for idea in ideas:
            if idea.id == idea_id:
                return idea
        return None

    async def create_idea(self, repo_full_name: str, text: str) -> RepoIdea:
        """Create a new idea."""
        ideas = await self.load_ideas(repo_full_name)
        
        # Determine order (add to end)
        max_order = max((idea.order for idea in ideas), default=-1)
        
        idea = RepoIdea(
            id=uuid.uuid4().hex,
            repo_full_name=repo_full_name,
            user_id=self.user_id,
            text=text,
            order=max_order + 1,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        
        ideas.append(idea)
        self._save_ideas_file(repo_full_name, [_idea_to_dict(i) for i in ideas])
        
        logger.info(f'Created idea {idea.id} for repo {repo_full_name}')
        return idea

    async def update_idea(self, idea: RepoIdea) -> RepoIdea:
        """Update an existing idea."""
        ideas = await self.load_ideas(idea.repo_full_name)
        
        # Find and update the idea
        updated = False
        for i, existing in enumerate(ideas):
            if existing.id == idea.id:
                idea.updated_at = datetime.now(timezone.utc)
                ideas[i] = idea
                updated = True
                break
        
        if not updated:
            raise ValueError(f'Idea {idea.id} not found')
        
        self._save_ideas_file(idea.repo_full_name, [_idea_to_dict(i) for i in ideas])
        logger.info(f'Updated idea {idea.id}')
        return idea

    async def delete_idea(self, repo_full_name: str, idea_id: str) -> bool:
        """Delete an idea."""
        ideas = await self.load_ideas(repo_full_name)
        
        original_len = len(ideas)
        ideas = [i for i in ideas if i.id != idea_id]
        
        if len(ideas) == original_len:
            return False  # Not found
        
        self._save_ideas_file(repo_full_name, [_idea_to_dict(i) for i in ideas])
        logger.info(f'Deleted idea {idea_id} from repo {repo_full_name}')
        return True

    async def reorder_ideas(self, repo_full_name: str, idea_ids: list[str]) -> list[RepoIdea]:
        """Reorder ideas based on the provided ID order."""
        ideas = await self.load_ideas(repo_full_name)
        
        # Create a map of id -> idea
        idea_map = {idea.id: idea for idea in ideas}
        
        # Reorder based on provided IDs
        reordered = []
        for i, idea_id in enumerate(idea_ids):
            if idea_id in idea_map:
                idea = idea_map[idea_id]
                idea.order = i
                idea.updated_at = datetime.now(timezone.utc)
                reordered.append(idea)
        
        # Add any ideas not in the list at the end (shouldn't happen normally)
        for idea in ideas:
            if idea.id not in idea_ids:
                idea.order = len(reordered)
                reordered.append(idea)
        
        self._save_ideas_file(repo_full_name, [_idea_to_dict(i) for i in reordered])
        logger.info(f'Reordered {len(reordered)} ideas for repo {repo_full_name}')
        return reordered

    async def start_building(
        self, 
        repo_full_name: str, 
        idea_id: str, 
        conversation_id: str,
        status: str = 'running',
    ) -> RepoIdea:
        """Mark an idea as building with the given conversation."""
        idea = await self.get_idea(repo_full_name, idea_id)
        if not idea:
            raise ValueError(f'Idea {idea_id} not found')
        
        idea.building_conversation_id = conversation_id
        idea.building_status = status
        idea.building_started_at = datetime.now(timezone.utc)
        idea.building_error_message = None
        
        return await self.update_idea(idea)

    async def update_building_status(
        self, 
        repo_full_name: str, 
        idea_id: str, 
        status: str,
        error_message: str | None = None,
    ) -> RepoIdea:
        """Update the building status of an idea."""
        idea = await self.get_idea(repo_full_name, idea_id)
        if not idea:
            raise ValueError(f'Idea {idea_id} not found')
        
        idea.building_status = status
        if error_message:
            idea.building_error_message = error_message
        
        return await self.update_idea(idea)

    @classmethod
    async def get_instance(
        cls, config: 'OpenHandsConfig', user_id: str
    ) -> 'FileIdeasStore':
        """Get an instance of the ideas store for a user."""
        file_store = get_file_store(
            file_store_type=config.file_store,
            file_store_path=config.file_store_path,
        )
        return cls(file_store, user_id)
