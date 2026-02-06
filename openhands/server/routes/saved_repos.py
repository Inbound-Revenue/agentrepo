"""API routes for managing saved repositories."""

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from openhands.core.logger import openhands_logger as logger
from openhands.integrations.service_types import ProviderType
from openhands.server.shared import config
from openhands.storage.data_models.saved_repo import PrewarmedConversation, SavedRepository
from openhands.storage.repos.file_repos_store import FileReposStore


# Note: saved-repos endpoints don't require session API key auth
# since they're used for local deployment repo management
app = APIRouter(prefix='/api')


class PrewarmedConversationResponse(BaseModel):
    """Response model for a pre-warmed conversation."""

    conversation_id: str
    status: str
    created_at: str
    error_message: str | None
    warming_step: str | None


class SavedRepoResponse(BaseModel):
    """Response model for a saved repository."""

    repo_full_name: str
    branch: str
    git_provider: str
    added_at: str
    last_commit_sha: str | None
    pool_size: int
    prewarmed_conversations: list[PrewarmedConversationResponse]
    ready_count: int
    warming_count: int


class AddRepoRequest(BaseModel):
    """Request model for adding a repository."""

    repo_full_name: str
    branch: str = 'main'
    git_provider: str = 'github'
    pool_size: int = 2


class UpdateRepoRequest(BaseModel):
    """Request model for updating a repository."""

    branch: str | None = None
    last_commit_sha: str | None = None
    pool_size: int | None = None


class ClaimConversationResponse(BaseModel):
    """Response model for claiming a conversation."""

    conversation_id: str
    repo_full_name: str
    branch: str


async def get_repos_store() -> FileReposStore:
    """Get the repos store instance."""
    return await FileReposStore.get_instance(config, user_id=None)


def prewarmed_conv_to_response(conv: PrewarmedConversation) -> PrewarmedConversationResponse:
    """Convert a PrewarmedConversation to a response model."""
    return PrewarmedConversationResponse(
        conversation_id=conv.conversation_id,
        status=conv.status,
        created_at=conv.created_at.isoformat() if conv.created_at else datetime.now(timezone.utc).isoformat(),
        error_message=conv.error_message,
        warming_step=conv.warming_step,
    )


def repo_to_response(repo: SavedRepository) -> SavedRepoResponse:
    """Convert a SavedRepository to a response model."""
    ready_convs = repo.get_ready_conversations()
    return SavedRepoResponse(
        repo_full_name=repo.repo_full_name,
        branch=repo.branch,
        git_provider=repo.git_provider.value if isinstance(repo.git_provider, ProviderType) else repo.git_provider,
        added_at=repo.added_at.isoformat() if repo.added_at else datetime.now(timezone.utc).isoformat(),
        last_commit_sha=repo.last_commit_sha,
        pool_size=repo.pool_size,
        prewarmed_conversations=[prewarmed_conv_to_response(c) for c in repo.prewarmed_conversations],
        ready_count=len(ready_convs),
        warming_count=repo.get_warming_count(),
    )


@app.get(
    '/saved-repos',
    response_model=list[SavedRepoResponse],
    responses={
        200: {'description': 'List of saved repositories'},
        500: {'description': 'Error loading repositories'},
    },
)
async def list_saved_repos(
    repos_store: FileReposStore = Depends(get_repos_store),
) -> list[SavedRepoResponse]:
    """Get all saved repositories."""
    try:
        repos = await repos_store.load_all()
        return [repo_to_response(repo) for repo in repos]
    except Exception as e:
        logger.error(f'Error loading saved repos: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error loading saved repositories',
        )


@app.get(
    '/saved-repos/{repo_full_name:path}',
    response_model=SavedRepoResponse,
    responses={
        200: {'description': 'Repository details'},
        404: {'description': 'Repository not found'},
        500: {'description': 'Error loading repository'},
    },
)
async def get_saved_repo(
    repo_full_name: str,
    repos_store: FileReposStore = Depends(get_repos_store),
) -> SavedRepoResponse:
    """Get a specific saved repository by its full name."""
    try:
        repo = await repos_store.get_repo(repo_full_name)
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Repository {repo_full_name} not found',
            )
        return repo_to_response(repo)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error loading saved repo {repo_full_name}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error loading repository',
        )


@app.post(
    '/saved-repos',
    response_model=SavedRepoResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        201: {'description': 'Repository added successfully'},
        400: {'description': 'Invalid request'},
        500: {'description': 'Error adding repository'},
    },
)
async def add_saved_repo(
    request: AddRepoRequest,
    repos_store: FileReposStore = Depends(get_repos_store),
) -> SavedRepoResponse:
    """Add a new repository to the saved list.
    
    After adding, the ConversationPoolManager will automatically start
    pre-warming conversations for this repo.
    """
    try:
        from openhands.server.conversation_pool_manager import get_pool_manager
        
        # Validate git provider
        try:
            git_provider = ProviderType(request.git_provider)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f'Invalid git provider: {request.git_provider}',
            )

        # Validate pool_size
        if request.pool_size < 1 or request.pool_size > 10:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='pool_size must be between 1 and 10',
            )

        repo = SavedRepository(
            repo_full_name=request.repo_full_name,
            branch=request.branch,
            git_provider=git_provider,
            added_at=datetime.now(timezone.utc),
            pool_size=request.pool_size,
            prewarmed_conversations=[],
        )
        await repos_store.add_repo(repo)
        logger.info(f'Added saved repo: {request.repo_full_name} with pool_size={request.pool_size}')
        
        # Trigger pre-warming for this repo
        pool_manager = await get_pool_manager()
        await pool_manager.prewarm_for_repo(request.repo_full_name)
        
        # Reload repo to get updated prewarmed_conversations
        repo = await repos_store.get_repo(request.repo_full_name)
        
        return repo_to_response(repo)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error adding saved repo: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error adding repository',
        )


@app.patch(
    '/saved-repos/{repo_full_name:path}',
    response_model=SavedRepoResponse,
    responses={
        200: {'description': 'Repository updated successfully'},
        404: {'description': 'Repository not found'},
        500: {'description': 'Error updating repository'},
    },
)
async def update_saved_repo(
    repo_full_name: str,
    request: UpdateRepoRequest,
    repos_store: FileReposStore = Depends(get_repos_store),
) -> SavedRepoResponse:
    """Update an existing saved repository."""
    try:
        repo = await repos_store.get_repo(repo_full_name)
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Repository {repo_full_name} not found',
            )

        # Update fields if provided
        if request.branch is not None:
            repo.branch = request.branch
        if request.last_commit_sha is not None:
            repo.last_commit_sha = request.last_commit_sha
        if request.pool_size is not None:
            if request.pool_size < 1 or request.pool_size > 10:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail='pool_size must be between 1 and 10',
                )
            repo.pool_size = request.pool_size

        await repos_store.update_repo(repo)
        logger.info(f'Updated saved repo: {repo_full_name}')
        return repo_to_response(repo)
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error updating saved repo {repo_full_name}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error updating repository',
        )


@app.delete(
    '/saved-repos/{repo_full_name:path}',
    responses={
        200: {'description': 'Repository removed successfully'},
        404: {'description': 'Repository not found'},
        500: {'description': 'Error removing repository'},
    },
)
async def remove_saved_repo(
    repo_full_name: str,
    repos_store: FileReposStore = Depends(get_repos_store),
) -> JSONResponse:
    """Remove a repository from the saved list."""
    try:
        removed = await repos_store.remove_repo(repo_full_name)
        if not removed:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Repository {repo_full_name} not found',
            )
        logger.info(f'Removed saved repo: {repo_full_name}')
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'message': f'Repository {repo_full_name} removed'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error removing saved repo {repo_full_name}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error removing repository',
        )


@app.post(
    '/saved-repos/{repo_full_name:path}/claim',
    response_model=ClaimConversationResponse,
    responses={
        200: {'description': 'Conversation claimed successfully'},
        404: {'description': 'Repository not found or no ready conversations'},
        500: {'description': 'Error claiming conversation'},
    },
)
async def claim_conversation(
    repo_full_name: str,
    repos_store: FileReposStore = Depends(get_repos_store),
) -> ClaimConversationResponse:
    """Claim a pre-warmed conversation from the pool.
    
    Returns a ready-to-use conversation ID. The pool will automatically
    spawn a replacement conversation in the background.
    """
    try:
        from openhands.server.conversation_pool_manager import get_pool_manager
        
        # Verify repo exists
        repo = await repos_store.get_repo(repo_full_name)
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Repository {repo_full_name} not found',
            )
        
        # Try to claim a conversation
        pool_manager = await get_pool_manager()
        conversation_id = await pool_manager.claim_conversation(repo_full_name)
        
        if not conversation_id:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'No ready conversations available for {repo_full_name}. Try again shortly.',
            )
        
        logger.info(f'Claimed conversation {conversation_id} for repo {repo_full_name}')
        return ClaimConversationResponse(
            conversation_id=conversation_id,
            repo_full_name=repo_full_name,
            branch=repo.branch,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error claiming conversation for {repo_full_name}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error claiming conversation',
        )


@app.post(
    '/saved-repos/{repo_full_name:path}/prewarm',
    responses={
        200: {'description': 'Pre-warming started'},
        404: {'description': 'Repository not found'},
        500: {'description': 'Error starting pre-warm'},
    },
)
async def trigger_prewarm(
    repo_full_name: str,
    repos_store: FileReposStore = Depends(get_repos_store),
) -> JSONResponse:
    """Manually trigger pre-warming for a repository.
    
    Use this to refill the conversation pool if it's depleted.
    """
    try:
        from openhands.server.conversation_pool_manager import get_pool_manager
        
        # Verify repo exists
        repo = await repos_store.get_repo(repo_full_name)
        if not repo:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Repository {repo_full_name} not found',
            )
        
        pool_manager = await get_pool_manager()
        await pool_manager.prewarm_for_repo(repo_full_name)
        
        logger.info(f'Triggered pre-warming for repo: {repo_full_name}')
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'message': f'Pre-warming started for {repo_full_name}'},
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error triggering pre-warm for {repo_full_name}: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error triggering pre-warm',
        )


@app.get(
    '/saved-repos/pool-status',
    responses={
        200: {'description': 'Pool status retrieved successfully'},
        500: {'description': 'Error getting pool status'},
    },
)
async def get_pool_status() -> JSONResponse:
    """Get the status of all conversation pools."""
    try:
        from openhands.server.conversation_pool_manager import get_pool_manager
        
        pool_manager = await get_pool_manager()
        status_data = await pool_manager.get_pool_status()
        
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content=status_data,
        )
    except Exception as e:
        logger.error(f'Error getting pool status: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error getting pool status',
        )
