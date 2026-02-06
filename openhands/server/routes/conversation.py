# IMPORTANT: LEGACY V0 CODE - Deprecated since version 1.0.0, scheduled for removal April 1, 2026
# This file is part of the legacy (V0) implementation of OpenHands and will be removed soon as we complete the migration to V1.
# OpenHands V1 uses the Software Agent SDK for the agentic core and runs a new application server. Please refer to:
#   - V1 agentic core (SDK): https://github.com/OpenHands/software-agent-sdk
#   - V1 application server (in this repo): openhands/app_server/
# Unless you are working on deprecation, please avoid extending this legacy file and consult the V1 codepaths above.
# Tag: Legacy-V0
# This module belongs to the old V0 web server. The V1 application server lives under openhands/app_server/.
import uuid

import httpx
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from openhands.app_server.app_conversation.app_conversation_service import (
    AppConversationService,
)
from openhands.utils.http_session import httpx_verify_option
from openhands.app_server.config import depends_app_conversation_service
from openhands.core.logger import openhands_logger as logger
from openhands.events.action.message import MessageAction
from openhands.events.event_filter import EventFilter
from openhands.events.event_store import EventStore
from openhands.events.serialization.event import event_to_dict
from openhands.memory.memory import Memory
from openhands.microagent.types import InputMetadata
from openhands.runtime.base import Runtime
from openhands.server.dependencies import get_dependencies
from openhands.server.session.conversation import ServerConversation
from openhands.server.shared import conversation_manager, file_store
from openhands.server.user_auth import get_user_id
from openhands.server.utils import get_conversation

app = APIRouter(
    prefix='/api/conversations/{conversation_id}', dependencies=get_dependencies()
)

# Dependency for app conversation service
app_conversation_service_dependency = depends_app_conversation_service()


async def _is_v1_conversation(
    conversation_id: str, app_conversation_service: AppConversationService
) -> bool:
    """Check if the given conversation_id corresponds to a V1 conversation.

    Args:
        conversation_id: The conversation ID to check
        app_conversation_service: Service to query V1 conversations

    Returns:
        True if this is a V1 conversation, False otherwise
    """
    try:
        conversation_uuid = uuid.UUID(conversation_id)
        app_conversation = await app_conversation_service.get_app_conversation(
            conversation_uuid
        )
        return app_conversation is not None
    except (ValueError, TypeError):
        # Not a valid UUID, so it's not a V1 conversation
        return False
    except Exception:
        # Service error, assume it's not a V1 conversation
        return False


async def _get_v1_conversation_config(
    conversation_id: str, app_conversation_service: AppConversationService
) -> dict[str, str | None]:
    """Get configuration for a V1 conversation.

    Args:
        conversation_id: The conversation ID
        app_conversation_service: Service to query V1 conversations

    Returns:
        Dictionary with runtime_id (sandbox_id) and session_id (conversation_id)
    """
    conversation_uuid = uuid.UUID(conversation_id)
    app_conversation = await app_conversation_service.get_app_conversation(
        conversation_uuid
    )

    if app_conversation is None:
        raise ValueError(f'V1 conversation {conversation_id} not found')

    return {
        'runtime_id': app_conversation.sandbox_id,
        'session_id': conversation_id,
    }


def _get_v0_conversation_config(
    conversation: ServerConversation,
) -> dict[str, str | None]:
    """Get configuration for a V0 conversation.

    Args:
        conversation: The server conversation object

    Returns:
        Dictionary with runtime_id and session_id from the runtime
    """
    runtime = conversation.runtime
    runtime_id = runtime.runtime_id if hasattr(runtime, 'runtime_id') else None
    session_id = runtime.sid if hasattr(runtime, 'sid') else None

    return {
        'runtime_id': runtime_id,
        'session_id': session_id,
    }


@app.get('/config')
async def get_remote_runtime_config(
    conversation_id: str,
    app_conversation_service: AppConversationService = app_conversation_service_dependency,
    user_id: str | None = Depends(get_user_id),
) -> JSONResponse:
    """Retrieve the runtime configuration.

    For V0 conversations: returns runtime_id and session_id from the runtime.
    For V1 conversations: returns sandbox_id as runtime_id and conversation_id as session_id.
    """
    # Check if this is a V1 conversation first
    if await _is_v1_conversation(conversation_id, app_conversation_service):
        # This is a V1 conversation
        config = await _get_v1_conversation_config(
            conversation_id, app_conversation_service
        )
    else:
        # V0 conversation - get the conversation and use the existing logic
        conversation = await conversation_manager.attach_to_conversation(
            conversation_id, user_id
        )
        if not conversation:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Conversation {conversation_id} not found',
            )
        try:
            config = _get_v0_conversation_config(conversation)
        finally:
            await conversation_manager.detach_from_conversation(conversation)

    return JSONResponse(content=config)


@app.get('/vscode-url', deprecated=True)
async def get_vscode_url(
    conversation: ServerConversation = Depends(get_conversation),
) -> JSONResponse:
    """Get the VSCode URL.

    This endpoint allows getting the VSCode URL.

    Args:
        request (Request): The incoming FastAPI request object.

    Returns:
        JSONResponse: A JSON response indicating the success of the operation.

        For V1 conversations, the VSCode URL is available in the sandbox's ``exposed_urls``
        field. Use ``GET /api/v1/sandboxes?id={sandbox_id}`` to retrieve sandbox information and use the name VSCODE.
    """
    try:
        runtime: Runtime = conversation.runtime
        logger.debug(f'Runtime type: {type(runtime)}')
        logger.debug(f'Runtime VSCode URL: {runtime.vscode_url}')
        return JSONResponse(
            status_code=status.HTTP_200_OK, content={'vscode_url': runtime.vscode_url}
        )
    except Exception as e:
        logger.error(f'Error getting VSCode URL: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                'vscode_url': None,
                'error': f'Error getting VSCode URL: {e}',
            },
        )


@app.get('/web-hosts', deprecated=True)
async def get_hosts(
    conversation: ServerConversation = Depends(get_conversation),
) -> JSONResponse:
    """Get the hosts used by the runtime.

    This endpoint allows getting the hosts used by the runtime.

    Args:
        request (Request): The incoming FastAPI request object.

    Returns:
        JSONResponse: A JSON response indicating the success of the operation.

        For V1 conversations, web hosts are available in the sandbox's ``exposed_urls``
        field. Use ``GET /api/v1/sandboxes?id={sandbox_id}`` to retrieve sandbox information and use the name AGENT_SERVER.
    """
    try:
        runtime: Runtime = conversation.runtime
        logger.debug(f'Runtime type: {type(runtime)}')
        logger.debug(f'Runtime hosts: {runtime.web_hosts}')
        return JSONResponse(status_code=200, content={'hosts': runtime.web_hosts})
    except Exception as e:
        logger.error(f'Error getting runtime hosts: {e}')
        return JSONResponse(
            status_code=500,
            content={
                'hosts': None,
                'error': f'Error getting runtime hosts: {e}',
            },
        )


@app.get('/events', deprecated=True)
async def search_events(
    conversation_id: str,
    start_id: int = 0,
    end_id: int | None = None,
    reverse: bool = False,
    filter: EventFilter | None = None,
    limit: int = 20,
    app_conversation_service: AppConversationService = app_conversation_service_dependency,
    user_id: str | None = Depends(get_user_id),
):
    """Search through the event stream with filtering and pagination.

    Args:
        conversation_id: The conversation ID
        start_id: Starting ID in the event stream. Defaults to 0
        end_id: Ending ID in the event stream
        reverse: Whether to retrieve events in reverse order. Defaults to False.
        filter: Filter for events
        limit: Maximum number of events to return. Must be between 1 and 100. Defaults to 20
        app_conversation_service: Service to query V1 conversations
        user_id: User ID (injected by dependency)

    Returns:
        dict: Dictionary containing:
            - events: List of matching events
            - has_more: Whether there are more matching events after this batch
    Raises:
        HTTPException: If conversation is not found or access is denied
        ValueError: If limit is less than 1 or greater than 100

        Use the V1 endpoint ``GET /api/v1/events/search?conversation_id__eq={conversation_id}``
        instead, which provides enhanced filtering by event kind, timestamp ranges,
        and improved pagination.
    """
    if limit < 0 or limit > 100:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail='Invalid limit'
        )

    # Check if this is a V1 conversation - if so, proxy to SDK
    if await _is_v1_conversation(conversation_id, app_conversation_service):
        return await _search_events_v1(
            conversation_id, start_id, limit, app_conversation_service
        )

    # V0 conversation - use the legacy event store
    event_store = EventStore(
        sid=conversation_id,
        file_store=file_store,
        user_id=user_id,
    )

    # Get matching events from the store
    events = list(
        event_store.search_events(
            start_id=start_id,
            end_id=end_id,
            reverse=reverse,
            filter=filter,
            limit=limit + 1,
        )
    )

    # Check if there are more events
    has_more = len(events) > limit
    if has_more:
        events = events[:limit]  # Remove the extra event

    events_json = [event_to_dict(event) for event in events]
    return {
        'events': events_json,
        'has_more': has_more,
    }


async def _search_events_v1(
    conversation_id: str,
    start_id: int,
    limit: int,
    app_conversation_service: AppConversationService,
) -> dict:
    """Search events for a V1 conversation by proxying to the SDK agent_server.

    Args:
        conversation_id: The conversation ID
        start_id: Starting event index
        limit: Maximum number of events to return
        app_conversation_service: Service to get conversation info

    Returns:
        dict: Dictionary containing events and has_more flag
    """
    try:
        conversation_uuid = uuid.UUID(conversation_id)
        app_conversation = await app_conversation_service.get_app_conversation(
            conversation_uuid
        )

        if app_conversation is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Conversation {conversation_id} not found',
            )

        # Get agent_server_url - either from conversation_url or from sandbox
        agent_server_url = None
        if app_conversation.conversation_url:
            # conversation_url is like http://host:port/api/conversations/{id}
            # We need just http://host:port/api/conversations/{id}
            agent_server_url = app_conversation.conversation_url
        else:
            # For ProcessSandbox, conversation_url is None but we can get
            # the internal URL from the sandbox service
            sandbox = await app_conversation_service.sandbox_service.get_sandbox(
                app_conversation.sandbox_id
            )
            if sandbox and sandbox.exposed_urls:
                from openhands.app_server.sandbox.sandbox_models import AGENT_SERVER

                base_url = next(
                    (
                        eu.url
                        for eu in sandbox.exposed_urls
                        if eu.name == AGENT_SERVER
                    ),
                    None,
                )
                if base_url:
                    agent_server_url = (
                        f'{base_url}/api/conversations/{conversation_id}'
                    )

        if not agent_server_url:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f'Conversation {conversation_id} not ready',
            )

        # Build SDK events search URL
        # SDK endpoint: GET /api/conversations/{id}/events/search
        sdk_url = f'{agent_server_url}/events/search'
        params = {
            'start_index': start_id,
            'limit': limit + 1,  # Get one extra to check has_more
        }

        headers = {}
        if app_conversation.session_api_key:
            headers['X-Session-API-Key'] = app_conversation.session_api_key

        async with httpx.AsyncClient(verify=httpx_verify_option()) as client:
            response = await client.get(sdk_url, params=params, headers=headers)
            response.raise_for_status()
            sdk_response = response.json()

        # SDK returns {"items": [...], "next_page_id": ...}
        if isinstance(sdk_response, dict):
            events = sdk_response.get('items', [])
            # has_more is true if there's a next_page_id or if we got more than limit
            has_more = sdk_response.get('next_page_id') is not None or len(events) > limit
        else:
            # Fallback for unexpected response format
            events = sdk_response if isinstance(sdk_response, list) else []
            has_more = len(events) > limit

        if len(events) > limit:
            events = events[:limit]

        return {
            'events': events,
            'has_more': has_more,
        }

    except httpx.HTTPStatusError as e:
        logger.error(f'SDK events request failed: {e}')
        raise HTTPException(
            status_code=e.response.status_code,
            detail=f'Failed to fetch events from SDK: {e}',
        )
    except Exception as e:
        logger.error(f'Error fetching V1 events: {e}')
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f'Error fetching events: {e}',
        )


@app.post('/events', deprecated=True)
async def add_event(
    request: Request, conversation: ServerConversation = Depends(get_conversation)
):
    """Add an event to a conversation.

    For V1 conversations, events are managed through the sandbox webhook system.
    Use ``POST /api/v1/webhooks/events/{conversation_id}`` for event callbacks.
    """
    data = await request.json()
    await conversation_manager.send_event_to_conversation(conversation.sid, data)
    return JSONResponse({'success': True})


class AddMessageRequest(BaseModel):
    """Request model for adding a message to a conversation."""

    message: str


@app.post('/message')
async def add_message(
    data: AddMessageRequest,
    conversation: ServerConversation = Depends(get_conversation),
):
    """Add a message to an existing conversation.

    This endpoint allows adding a user message to an existing conversation.
    The message will be processed by the agent in the conversation.

    Args:
        data: The request data containing the message text
        conversation: The conversation to add the message to (injected by dependency)

    Returns:
        JSONResponse: A JSON response indicating the success of the operation
    """
    try:
        # Create a MessageAction from the provided message text
        message_action = MessageAction(content=data.message)

        # Convert the action to a dictionary for sending to the conversation
        message_data = event_to_dict(message_action)

        # Send the message to the conversation
        await conversation_manager.send_event_to_conversation(
            conversation.sid, message_data
        )

        return JSONResponse({'success': True})
    except Exception as e:
        logger.error(f'Error adding message to conversation: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                'success': False,
                'error': f'Error adding message to conversation: {e}',
            },
        )


class MicroagentResponse(BaseModel):
    """Response model for microagents endpoint."""

    name: str
    type: str
    content: str
    triggers: list[str] = []
    inputs: list[InputMetadata] = []
    tools: list[str] = []


@app.get('/microagents', deprecated=True)
async def get_microagents(
    conversation: ServerConversation = Depends(get_conversation),
) -> JSONResponse:
    """Get all microagents associated with the conversation.

    This endpoint returns all repository and knowledge microagents that are loaded for the conversation.

    Returns:
        JSONResponse: A JSON response containing the list of microagents.

        Use the V1 endpoint ``GET /api/v1/app-conversations/{conversation_id}/skills`` instead,
        which provides skill information including triggers and content for V1 conversations.
    """
    try:
        # Get the agent session for this conversation
        agent_session = conversation_manager.get_agent_session(conversation.sid)

        if not agent_session:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={'error': 'Agent session not found for this conversation'},
            )

        # Access the memory to get the microagents
        memory: Memory | None = agent_session.memory
        if memory is None:
            return JSONResponse(
                status_code=status.HTTP_404_NOT_FOUND,
                content={
                    'error': 'Memory is not yet initialized for this conversation'
                },
            )

        # Prepare the response
        microagents = []

        # Add repo microagents
        for name, r_agent in memory.repo_microagents.items():
            microagents.append(
                MicroagentResponse(
                    name=name,
                    type='repo',
                    content=r_agent.content,
                    triggers=[],
                    inputs=r_agent.metadata.inputs,
                    tools=(
                        [
                            server.name
                            for server in r_agent.metadata.mcp_tools.stdio_servers
                        ]
                        if r_agent.metadata.mcp_tools
                        else []
                    ),
                )
            )

        # Add knowledge microagents
        for name, k_agent in memory.knowledge_microagents.items():
            microagents.append(
                MicroagentResponse(
                    name=name,
                    type='knowledge',
                    content=k_agent.content,
                    triggers=k_agent.triggers,
                    inputs=k_agent.metadata.inputs,
                    tools=(
                        [
                            server.name
                            for server in k_agent.metadata.mcp_tools.stdio_servers
                        ]
                        if k_agent.metadata.mcp_tools
                        else []
                    ),
                )
            )

        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={'microagents': [m.model_dump() for m in microagents]},
        )
    except Exception as e:
        logger.error(f'Error getting microagents: {e}')
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={'error': f'Error getting microagents: {e}'},
        )
