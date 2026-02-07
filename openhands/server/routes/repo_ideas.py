"""API routes for managing repository ideas."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from openhands.core.logger import openhands_logger as logger
from openhands.events.action import MessageAction
from openhands.events.serialization import event_to_dict
from openhands.server.shared import config, conversation_manager
from openhands.server.user_auth import get_provider_tokens, get_user_id
from openhands.storage.data_models.repo_idea import RepoIdea
from openhands.storage.ideas.file_ideas_store import FileIdeasStore
from openhands.storage.repos.file_repos_store import FileReposStore


app = APIRouter(prefix='/api')


# Request/Response Models

class IdeaResponse(BaseModel):
    """Response model for an idea."""
    id: str
    repo_full_name: str
    user_id: str
    text: str
    order: int
    created_at: str
    updated_at: str
    building_conversation_id: str | None
    building_status: str | None
    building_started_at: str | None
    building_error_message: str | None


class CreateIdeaRequest(BaseModel):
    """Request model for creating an idea."""
    text: str


class UpdateIdeaRequest(BaseModel):
    """Request model for updating an idea."""
    text: str | None = None


class ReorderIdeasRequest(BaseModel):
    """Request model for reordering ideas."""
    idea_ids: list[str]


class BuildIdeaResponse(BaseModel):
    """Response model for building an idea."""
    idea_id: str
    conversation_id: str | None
    status: str  # 'running', 'queued', 'error'
    message: str | None = None


# Helper functions

def idea_to_response(idea: RepoIdea) -> IdeaResponse:
    """Convert a RepoIdea to an IdeaResponse."""
    return IdeaResponse(
        id=idea.id,
        repo_full_name=idea.repo_full_name,
        user_id=idea.user_id,
        text=idea.text,
        order=idea.order,
        created_at=idea.created_at.isoformat() if idea.created_at else datetime.now(timezone.utc).isoformat(),
        updated_at=idea.updated_at.isoformat() if idea.updated_at else datetime.now(timezone.utc).isoformat(),
        building_conversation_id=idea.building_conversation_id,
        building_status=idea.building_status,
        building_started_at=idea.building_started_at.isoformat() if idea.building_started_at else None,
        building_error_message=idea.building_error_message,
    )


async def get_ideas_store(request: Request) -> FileIdeasStore:
    """Get the ideas store for the current user."""
    user_id = await get_user_id(request)
    if not user_id:
        user_id = 'anonymous'
    return await FileIdeasStore.get_instance(config, user_id)


async def get_repos_store() -> FileReposStore:
    """Get the repos store instance."""
    return await FileReposStore.get_instance(config, user_id=None)


# Routes

@app.get(
    '/saved-repos/{repo_full_name:path}/ideas',
    response_model=list[IdeaResponse],
    responses={
        200: {'description': 'List of ideas for the repository'},
        500: {'description': 'Error loading ideas'},
    },
)
async def list_ideas(
    repo_full_name: str,
    ideas_store: FileIdeasStore = Depends(get_ideas_store),
) -> list[IdeaResponse]:
    """Get all ideas for a repository."""
    try:
        ideas = await ideas_store.load_ideas(repo_full_name)
        return [idea_to_response(idea) for idea in ideas]
    except Exception as e:
        logger.error(f'Error loading ideas for {repo_full_name}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error loading ideas',
        )


@app.post(
    '/saved-repos/{repo_full_name:path}/ideas',
    response_model=IdeaResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {'description': 'Idea created successfully'},
        400: {'description': 'Invalid request'},
        500: {'description': 'Error creating idea'},
    },
)
async def create_idea(
    repo_full_name: str,
    request_body: CreateIdeaRequest,
    ideas_store: FileIdeasStore = Depends(get_ideas_store),
) -> IdeaResponse:
    """Create a new idea for a repository."""
    try:
        if not request_body.text or not request_body.text.strip():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Idea text cannot be empty',
            )
        
        idea = await ideas_store.create_idea(repo_full_name, request_body.text.strip())
        logger.info(f'Created idea {idea.id} for repo {repo_full_name}')
        return idea_to_response(idea)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error creating idea for {repo_full_name}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error creating idea',
        )


@app.patch(
    '/saved-repos/{repo_full_name:path}/ideas/{idea_id}',
    response_model=IdeaResponse,
    responses={
        200: {'description': 'Idea updated successfully'},
        404: {'description': 'Idea not found'},
        500: {'description': 'Error updating idea'},
    },
)
async def update_idea(
    repo_full_name: str,
    idea_id: str,
    request_body: UpdateIdeaRequest,
    ideas_store: FileIdeasStore = Depends(get_ideas_store),
) -> IdeaResponse:
    """Update an existing idea."""
    try:
        idea = await ideas_store.get_idea(repo_full_name, idea_id)
        if not idea:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Idea {idea_id} not found',
            )
        
        if request_body.text is not None:
            idea.text = request_body.text.strip()
        
        updated_idea = await ideas_store.update_idea(idea)
        logger.info(f'Updated idea {idea_id}')
        return idea_to_response(updated_idea)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating idea {idea_id}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating idea',
        )


@app.delete(
    '/saved-repos/{repo_full_name:path}/ideas/{idea_id}',
    responses={
        200: {'description': 'Idea deleted successfully'},
        404: {'description': 'Idea not found'},
        500: {'description': 'Error deleting idea'},
    },
)
async def delete_idea(
    repo_full_name: str,
    idea_id: str,
    ideas_store: FileIdeasStore = Depends(get_ideas_store),
) -> JSONResponse:
    """Delete an idea."""
    try:
        deleted = await ideas_store.delete_idea(repo_full_name, idea_id)
        if not deleted:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Idea {idea_id} not found',
            )
        logger.info(f'Deleted idea {idea_id} from repo {repo_full_name}')
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'message': f'Idea {idea_id} deleted'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error deleting idea {idea_id}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error deleting idea',
        )


@app.post(
    '/saved-repos/{repo_full_name:path}/ideas/reorder',
    response_model=list[IdeaResponse],
    responses={
        200: {'description': 'Ideas reordered successfully'},
        500: {'description': 'Error reordering ideas'},
    },
)
async def reorder_ideas(
    repo_full_name: str,
    request_body: ReorderIdeasRequest,
    ideas_store: FileIdeasStore = Depends(get_ideas_store),
) -> list[IdeaResponse]:
    """Reorder ideas for a repository."""
    try:
        ideas = await ideas_store.reorder_ideas(repo_full_name, request_body.idea_ids)
        logger.info(f'Reordered {len(ideas)} ideas for repo {repo_full_name}')
        return [idea_to_response(idea) for idea in ideas]
    except Exception as e:
        logger.error(f'Error reordering ideas for {repo_full_name}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error reordering ideas',
        )


@app.post(
    '/saved-repos/{repo_full_name:path}/ideas/{idea_id}/build',
    response_model=BuildIdeaResponse,
    responses={
        200: {'description': 'Build started or queued'},
        404: {'description': 'Idea or repo not found'},
        500: {'description': 'Error starting build'},
    },
)
async def build_idea(
    repo_full_name: str,
    idea_id: str,
    http_request: Request,
    ideas_store: FileIdeasStore = Depends(get_ideas_store),
    repos_store: FileReposStore = Depends(get_repos_store),
) -> BuildIdeaResponse:
    """Start building an idea by claiming a conversation and sending the prompt.
    
    This will:
    1. Get the idea text
    2. Claim a pre-warmed conversation (or queue if none available)
    3. Send the idea text as the first user message
    4. Update the idea with the conversation ID and status
    """
    try:
        from openhands.server.conversation_pool_manager import get_pool_manager
        
        # Get the idea
        idea = await ideas_store.get_idea(repo_full_name, idea_id)
        if not idea:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Idea {idea_id} not found',
            )
        
        # Verify repo exists
        repo = await repos_store.get_repo(repo_full_name)
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Repository {repo_full_name} not found',
            )
        
        # Try to claim a pre-warmed conversation
        pool_manager = await get_pool_manager()
        conversation_id = await pool_manager.claim_conversation(repo_full_name)
        
        if not conversation_id:
            # No conversation available, queue the request
            logger.warning(f'No ready conversations for {repo_full_name}, queuing idea {idea_id}')
            await ideas_store.start_building(
                repo_full_name, 
                idea_id, 
                conversation_id='',  # No conversation yet
                status='queued',
            )
            return BuildIdeaResponse(
                idea_id=idea_id,
                conversation_id=None,
                status='queued',
                message='No agents available. Your request has been queued and will start when an agent is ready.',
            )
        
        # Update idea with conversation info
        await ideas_store.start_building(
            repo_full_name,
            idea_id,
            conversation_id=conversation_id,
            status='running',
        )
        
        # Send the idea text as the first user message
        try:
            message_action = MessageAction(content=idea.text)
            message_data = event_to_dict(message_action)
            await conversation_manager.send_event_to_conversation(
                conversation_id, message_data
            )
            logger.info(f'Sent idea {idea_id} to conversation {conversation_id}')
        except Exception as e:
            logger.error(f'Error sending message to conversation {conversation_id}: {e}')
            # Update status to error
            await ideas_store.update_building_status(
                repo_full_name,
                idea_id,
                status='error',
                error_message=f'Failed to send message: {str(e)}',
            )
            return BuildIdeaResponse(
                idea_id=idea_id,
                conversation_id=conversation_id,
                status='error',
                message=f'Failed to send message to agent: {str(e)}',
            )
        
        logger.info(f'Started building idea {idea_id} with conversation {conversation_id}')
        return BuildIdeaResponse(
            idea_id=idea_id,
            conversation_id=conversation_id,
            status='running',
            message=None,
        )
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error building idea {idea_id}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error starting build: {str(e)}',
        )


@app.patch(
    '/saved-repos/{repo_full_name:path}/ideas/{idea_id}/status',
    response_model=IdeaResponse,
    responses={
        200: {'description': 'Status updated successfully'},
        404: {'description': 'Idea not found'},
        500: {'description': 'Error updating status'},
    },
)
async def update_idea_status(
    repo_full_name: str,
    idea_id: str,
    status_value: str,
    error_message: str | None = None,
    ideas_store: FileIdeasStore = Depends(get_ideas_store),
) -> IdeaResponse:
    """Update the building status of an idea."""
    try:
        if status_value not in ('running', 'review', 'error', 'queued'):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Invalid status: {status_value}',
            )
        
        idea = await ideas_store.update_building_status(
            repo_full_name,
            idea_id,
            status=status_value,
            error_message=error_message,
        )
        logger.info(f'Updated idea {idea_id} status to {status_value}')
        return idea_to_response(idea)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating idea {idea_id} status: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating status',
        )
