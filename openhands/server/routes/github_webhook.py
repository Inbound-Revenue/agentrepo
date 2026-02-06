"""GitHub webhook handler for detecting code changes.

This module receives GitHub webhook events and triggers conversation pool
invalidation when code is pushed to monitored repositories.
"""

import hashlib
import hmac
import os

from fastapi import APIRouter, Header, HTTPException, Request, status
from fastapi.responses import JSONResponse

from openhands.core.logger import openhands_logger as logger


app = APIRouter(prefix='/api')

# GitHub webhook secret - should be set in environment
GITHUB_WEBHOOK_SECRET = os.environ.get('GITHUB_WEBHOOK_SECRET', '')


def verify_github_signature(payload: bytes, signature: str | None, secret: str) -> bool:
    """Verify the GitHub webhook signature.
    
    GitHub sends a X-Hub-Signature-256 header containing HMAC-SHA256 of the payload.
    """
    if not signature:
        return False
    
    if not secret:
        # If no secret is configured, skip validation (not recommended for production)
        logger.warning('GITHUB_WEBHOOK_SECRET not set - skipping signature validation')
        return True
    
    # GitHub signature format: sha256=<hex-digest>
    if not signature.startswith('sha256='):
        return False
    
    expected_signature = signature[7:]  # Remove 'sha256=' prefix
    
    # Calculate HMAC-SHA256
    mac = hmac.new(secret.encode(), payload, hashlib.sha256)
    calculated_signature = mac.hexdigest()
    
    # Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(calculated_signature, expected_signature)


@app.post(
    '/webhooks/github',
    responses={
        200: {'description': 'Webhook processed successfully'},
        400: {'description': 'Invalid request'},
        401: {'description': 'Invalid signature'},
        500: {'description': 'Error processing webhook'},
    },
)
async def handle_github_webhook(
    request: Request,
    x_hub_signature_256: str | None = Header(None),
    x_github_event: str | None = Header(None),
    x_github_delivery: str | None = Header(None),
) -> JSONResponse:
    """Handle incoming GitHub webhook events.
    
    Supported events:
    - push: Triggers conversation pool invalidation for the affected repository
    
    Setup instructions:
    1. Go to your GitHub repository → Settings → Webhooks → Add webhook
    2. Payload URL: https://your-server/api/webhooks/github
    3. Content type: application/json
    4. Secret: Set GITHUB_WEBHOOK_SECRET environment variable to match
    5. Events: Select "Just the push event"
    """
    try:
        # Read raw body for signature verification
        body = await request.body()
        
        # Verify signature
        if GITHUB_WEBHOOK_SECRET:
            if not verify_github_signature(body, x_hub_signature_256, GITHUB_WEBHOOK_SECRET):
                logger.warning(f'Invalid GitHub webhook signature for delivery {x_github_delivery}')
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail='Invalid signature',
                )
        
        # Parse JSON payload
        try:
            payload = await request.json()
        except Exception as e:
            logger.error(f'Failed to parse webhook payload: {e}')
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail='Invalid JSON payload',
            )
        
        # Log the event
        logger.info(
            f'Received GitHub webhook: event={x_github_event}, delivery={x_github_delivery}'
        )
        
        # Handle different event types
        if x_github_event == 'push':
            return await _handle_push_event(payload)
        elif x_github_event == 'ping':
            return await _handle_ping_event(payload)
        else:
            logger.info(f'Ignoring GitHub event type: {x_github_event}')
            return JSONResponse(
                status_code=status.HTTP_200_OK,
                content={'message': f'Event type {x_github_event} ignored'},
            )
            
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f'Error processing GitHub webhook: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail='Error processing webhook',
        )


async def _handle_ping_event(payload: dict) -> JSONResponse:
    """Handle GitHub ping event (sent when webhook is created)."""
    zen = payload.get('zen', '')
    hook_id = payload.get('hook_id', '')
    logger.info(f'GitHub webhook ping received: hook_id={hook_id}, zen="{zen}"')
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={'message': 'Pong!', 'hook_id': hook_id},
    )


async def _handle_push_event(payload: dict) -> JSONResponse:
    """Handle GitHub push event - invalidate conversation pool for the repo."""
    from openhands.server.conversation_pool_manager import get_pool_manager
    from openhands.storage.repos.file_repos_store import FileReposStore
    from openhands.server.shared import config
    
    # Extract repository info
    repository = payload.get('repository', {})
    repo_full_name = repository.get('full_name', '')
    ref = payload.get('ref', '')
    pusher = payload.get('pusher', {}).get('name', 'unknown')
    commits = payload.get('commits', [])
    
    if not repo_full_name:
        logger.warning('Push event missing repository full_name')
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'message': 'Push event ignored - missing repository info'},
        )
    
    # Extract branch name from ref (refs/heads/main -> main)
    branch = ref.replace('refs/heads/', '') if ref.startswith('refs/heads/') else ref
    
    logger.info(
        f'GitHub push event: repo={repo_full_name}, branch={branch}, '
        f'pusher={pusher}, commits={len(commits)}'
    )
    
    # Check if this repo is in our saved repos
    repos_store = await FileReposStore.get_instance(config, user_id=None)
    repo = await repos_store.get_repo(repo_full_name)
    
    if not repo:
        logger.info(f'Push event for untracked repo: {repo_full_name}')
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'message': f'Repository {repo_full_name} not tracked'},
        )
    
    # Check if the push is to the tracked branch
    if repo.branch != branch:
        logger.info(
            f'Push event for different branch: {branch} (tracking {repo.branch})'
        )
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                'message': f'Push to branch {branch} ignored (tracking {repo.branch})'
            },
        )
    
    # Update the last commit SHA
    head_commit = payload.get('head_commit', {})
    if head_commit:
        repo.last_commit_sha = head_commit.get('id')
        await repos_store.update_repo(repo)
    
    # Invalidate the conversation pool for this repo
    pool_manager = await get_pool_manager()
    await pool_manager.invalidate_for_repo(repo_full_name)
    
    logger.info(f'Invalidated conversation pool for {repo_full_name} due to push event')
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            'message': f'Conversation pool invalidated for {repo_full_name}',
            'repo': repo_full_name,
            'branch': branch,
            'commits': len(commits),
        },
    )
