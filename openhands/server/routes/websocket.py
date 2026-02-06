# IMPORTANT: LEGACY V0 CODE - Deprecated since version 1.0.0, scheduled for removal April 1, 2026
# This file provides a raw WebSocket endpoint for V1 conversations.
# The V1 frontend expects WebSocket at /sockets/events/{conversation_id} but the
# SDK agent_server doesn't have this endpoint. This route bridges that gap by
# polling the SDK's REST API and streaming events over WebSocket.
#
# UPDATE: Now supports "local mode" for when this server IS the agent server
# (e.g., accessing child container directly). In local mode, events are read
# from /api/conversations/{id}/events instead of polling a nested SDK.
# Tag: Legacy-V0-Bridge

import asyncio
from typing import Optional

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from openhands.core.logger import openhands_logger as logger
from openhands.utils.http_session import httpx_verify_option

app = APIRouter(tags=['websocket'])

# Sentinel value to indicate local mode (this server IS the agent server)
LOCAL_MODE = 'LOCAL'


async def _get_events_source_for_conversation(
    conversation_id: str,
) -> tuple[Optional[str], Optional[str]]:
    """Get the events source for a conversation.

    Returns:
        Tuple of (source_url_or_mode, session_api_key):
        - (sdk_url, api_key): Poll events from nested SDK at sdk_url
        - (LOCAL_MODE, None): Read events from local /api/conversations/{id}/events
        - (None, None): Conversation not found
    """
    try:
        async with httpx.AsyncClient(verify=False) as client:
            # Try the conversations API endpoint (works on both parent and child)
            response = await client.get(
                f'http://127.0.0.1:8011/api/conversations/{conversation_id}',
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                url = data.get('url')
                session_api_key = data.get('session_api_key')

                # If URL exists, we have a nested SDK to poll
                if url:
                    return url, session_api_key

                # URL is None - check if events exist locally (we ARE the agent server)
                events_resp = await client.get(
                    f'http://127.0.0.1:8011/api/conversations/{conversation_id}/events',
                    params={'start_id': 0, 'limit': 1},
                    timeout=5.0,
                )
                if events_resp.status_code == 200:
                    # Local events endpoint works - use local mode
                    logger.info(
                        f'Conversation {conversation_id} has no SDK URL, '
                        'using local events mode'
                    )
                    return LOCAL_MODE, None

    except Exception as e:
        logger.warning(
            f'Error getting events source for conversation {conversation_id}: {e}'
        )

    return None, None


async def _poll_local_events(
    client: httpx.AsyncClient,
    conversation_id: str,
    start_id: int,
) -> tuple[list, int]:
    """Poll events from local /api/conversations/{id}/events endpoint.

    Returns:
        Tuple of (events_list, last_event_index)
    """
    response = await client.get(
        f'http://127.0.0.1:8011/api/conversations/{conversation_id}/events',
        params={'start_id': start_id, 'limit': 50},
        timeout=10.0,
    )
    if response.status_code == 200:
        data = response.json()
        events = data.get('events', [])
        return events, len(events)
    return [], 0


async def _poll_sdk_events(
    client: httpx.AsyncClient,
    sdk_url: str,
    headers: dict,
    start_index: int,
) -> list:
    """Poll events from nested SDK's events/search endpoint.

    Returns:
        List of events
    """
    response = await client.get(
        f'{sdk_url}/events/search',
        params={'start_index': start_index, 'limit': 50},
        headers=headers,
        timeout=10.0,
    )
    if response.status_code == 200:
        data = response.json()
        # SDK returns {items: [...]} structure
        return data.get('items', [])
    return []


@app.websocket('/sockets/events/{conversation_id}')
async def websocket_events(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for V1 conversations that streams events.

    This endpoint bridges V1 frontend's raw WebSocket expectations with either:
    1. A nested SDK's REST API (when conversation.url exists)
    2. Local events storage (when this server IS the agent server)
    """
    await websocket.accept()
    logger.info(f'WebSocket connected for conversation {conversation_id}')

    # Track the last event index we've sent
    last_event_index = 0
    poll_interval = 0.5  # seconds
    max_retries = 30  # Wait up to 15 seconds for conversation to be ready

    try:
        # Wait for conversation to be ready and determine events source
        events_source: Optional[str] = None
        session_api_key: Optional[str] = None

        for attempt in range(max_retries):
            events_source, session_api_key = await _get_events_source_for_conversation(
                conversation_id
            )
            if events_source:
                break
            await asyncio.sleep(0.5)

        if not events_source:
            logger.warning(
                f'WebSocket: Conversation {conversation_id} not ready '
                f'after {max_retries} attempts'
            )
            await websocket.send_json({
                'error': f'Conversation {conversation_id} not ready'
            })
            await websocket.close()
            return

        is_local_mode = events_source == LOCAL_MODE
        if is_local_mode:
            logger.info(
                f'WebSocket using LOCAL events for conversation {conversation_id}'
            )
        else:
            logger.info(
                f'WebSocket polling SDK at {events_source} '
                f'for conversation {conversation_id}'
            )

        headers = {}
        if session_api_key:
            headers['X-Session-API-Key'] = session_api_key

        async with httpx.AsyncClient(verify=httpx_verify_option()) as client:
            while websocket.client_state == WebSocketState.CONNECTED:
                try:
                    # Poll for new events based on mode
                    if is_local_mode:
                        events, count = await _poll_local_events(
                            client, conversation_id, last_event_index
                        )
                        for event in events:
                            await websocket.send_json(event)
                        if count > 0:
                            last_event_index += count
                    else:
                        events = await _poll_sdk_events(
                            client, events_source, headers, last_event_index
                        )
                        for event in events:
                            event_id = event.get('id', -1)
                            if isinstance(event_id, int) and event_id >= last_event_index:
                                await websocket.send_json(event)
                                last_event_index = event_id + 1
                            else:
                                # Non-integer ID, just send it
                                await websocket.send_json(event)
                        if events and not any(
                            isinstance(e.get('id'), int) for e in events
                        ):
                            last_event_index += len(events)

                    # Check for incoming messages (commands from client)
                    try:
                        message = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=0.01
                        )
                        logger.debug(f'Received message from client: {message[:100]}')
                    except asyncio.TimeoutError:
                        pass  # No message, continue polling

                    # Wait before next poll
                    await asyncio.sleep(poll_interval)

                except httpx.HTTPError as e:
                    logger.warning(f'HTTP error polling events: {e}')
                    await asyncio.sleep(poll_interval * 2)
                except Exception as e:
                    logger.error(f'Error in WebSocket event loop: {e}')
                    await asyncio.sleep(poll_interval * 2)

    except WebSocketDisconnect:
        logger.info(f'WebSocket disconnected for conversation {conversation_id}')
    except Exception as e:
        logger.error(f'WebSocket error for conversation {conversation_id}: {e}')
        try:
            await websocket.send_json({'error': str(e)})
        except Exception:
            pass
    finally:
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception:
            pass
