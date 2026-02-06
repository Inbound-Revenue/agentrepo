# IMPORTANT: LEGACY V0 CODE - Deprecated since version 1.0.0, scheduled for removal April 1, 2026
# This file provides a raw WebSocket endpoint for V1 conversations.
# The V1 frontend expects WebSocket at /sockets/events/{conversation_id} but the
# SDK agent_server doesn't have this endpoint. This route bridges that gap by
# polling the SDK's REST API and streaming events over WebSocket.
# Tag: Legacy-V0-Bridge

import asyncio
from typing import Optional

import httpx
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

from openhands.core.logger import openhands_logger as logger
from openhands.utils.http_session import httpx_verify_option

app = APIRouter(tags=['websocket'])


async def _get_sdk_url_for_conversation(
    conversation_id: str,
) -> tuple[Optional[str], Optional[str]]:
    """Get the SDK agent_server URL for a conversation.
    
    Returns:
        Tuple of (agent_server_url, session_api_key) or (None, None) if not found.
    """
    try:
        # Use the REST API to get conversation info (this works because we're in the same server)
        async with httpx.AsyncClient(verify=False) as client:
            # First try the V1 API endpoint  
            response = await client.get(
                f'http://127.0.0.1:8011/api/v1/conversations/{conversation_id}',
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                url = data.get('url')
                session_api_key = data.get('session_api_key')
                
                # If URL is None, get it from sandbox
                if not url and data.get('sandbox_id'):
                    sandbox_id = data.get('sandbox_id')
                    # Try to get sandbox info
                    sandbox_resp = await client.get(
                        f'http://127.0.0.1:8011/api/v1/sandboxes/{sandbox_id}',
                        timeout=5.0,
                    )
                    if sandbox_resp.status_code == 200:
                        sandbox_data = sandbox_resp.json()
                        for eu in sandbox_data.get('exposed_urls', []):
                            if eu.get('name') == 'agent-server':
                                url = f"{eu.get('url')}/api/conversations/{conversation_id}"
                                break
                        session_api_key = sandbox_data.get('session_api_key')
                
                return url, session_api_key
                
    except Exception as e:
        logger.warning(f'Error getting SDK URL for conversation {conversation_id}: {e}')
    
    return None, None


@app.websocket('/sockets/events/{conversation_id}')
async def websocket_events(websocket: WebSocket, conversation_id: str):
    """WebSocket endpoint for V1 conversations that polls SDK and streams events.
    
    This endpoint bridges V1 frontend's raw WebSocket expectations with the
    SDK agent_server's REST API. It polls for events and streams them to the client.
    """
    await websocket.accept()
    logger.info(f'WebSocket connected for conversation {conversation_id}')
    
    # Track the last event ID we've sent
    last_event_id = -1
    poll_interval = 0.5  # seconds
    max_retries = 30  # Wait up to 15 seconds for conversation to be ready
    
    try:
        # Wait for conversation to be ready and get SDK URL
        agent_server_url: Optional[str] = None
        session_api_key: Optional[str] = None
        
        for attempt in range(max_retries):
            agent_server_url, session_api_key = await _get_sdk_url_for_conversation(
                conversation_id
            )
            if agent_server_url:
                break
            await asyncio.sleep(0.5)
        
        if not agent_server_url:
            logger.warning(
                f'WebSocket: Conversation {conversation_id} not ready after {max_retries} attempts'
            )
            await websocket.send_json({
                'error': f'Conversation {conversation_id} not ready'
            })
            await websocket.close()
            return
        
        logger.info(
            f'WebSocket polling SDK at {agent_server_url} for conversation {conversation_id}'
        )
        
        # Build SDK events search URL
        sdk_url = f'{agent_server_url}/events/search'
        headers = {}
        if session_api_key:
            headers['X-Session-API-Key'] = session_api_key
        
        async with httpx.AsyncClient(verify=httpx_verify_option()) as client:
            while websocket.client_state == WebSocketState.CONNECTED:
                try:
                    # Poll for new events
                    params = {
                        'start_index': last_event_id + 1,
                        'limit': 50,
                    }
                    
                    response = await client.get(
                        sdk_url, params=params, headers=headers, timeout=10.0
                    )
                    
                    if response.status_code == 200:
                        data = response.json()
                        # SDK returns {items: [...]} structure
                        events = data.get('items', [])
                        
                        for event in events:
                            event_id = event.get('id', -1)
                            if event_id > last_event_id:
                                # Send event to WebSocket client
                                await websocket.send_json(event)
                                last_event_id = event_id
                    
                    # Check for incoming messages (commands from client)
                    try:
                        message = await asyncio.wait_for(
                            websocket.receive_text(),
                            timeout=0.01
                        )
                        # Handle client messages if needed (e.g., send_message)
                        logger.debug(f'Received message from client: {message[:100]}')
                    except asyncio.TimeoutError:
                        pass  # No message, continue polling
                    
                    # Wait before next poll
                    await asyncio.sleep(poll_interval)
                    
                except httpx.HTTPError as e:
                    logger.warning(f'HTTP error polling SDK: {e}')
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
