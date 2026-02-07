# IMPORTANT: LEGACY V0 CODE - Deprecated since version 1.0.0, scheduled for removal April 1, 2026
# This file is part of the legacy (V0) implementation of OpenHands and will be removed soon as we complete the migration to V1.
# OpenHands V1 uses the Software Agent SDK for the agentic core and runs a new application server. Please refer to:
#   - V1 agentic core (SDK): https://github.com/OpenHands/software-agent-sdk
#   - V1 application server (in this repo): openhands/app_server/
# Unless you are working on deprecation, please avoid extending this legacy file and consult the V1 codepaths above.
# Tag: Legacy-V0
# This module belongs to the old V0 web server. The V1 application server lives under openhands/app_server/.
import contextlib
import warnings
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi.routing import Mount

with warnings.catch_warnings():
    warnings.simplefilter('ignore')

from fastapi import (
    FastAPI,
    Request,
)
from fastapi.responses import JSONResponse

import openhands.agenthub  # noqa F401 (we import this to get the agents registered)
from openhands.core.logger import openhands_logger as logger
from openhands.app_server import v1_router
from openhands.app_server.config import get_app_lifespan_service
from openhands.integrations.service_types import AuthenticationError
from openhands.server.routes.conversation import app as conversation_api_router
from openhands.server.routes.feedback import app as feedback_api_router
from openhands.server.routes.files import app as files_api_router
from openhands.server.routes.git import app as git_api_router
from openhands.server.routes.github_webhook import app as github_webhook_router
from openhands.server.routes.health import add_health_endpoints
from openhands.server.routes.manage_conversations import (
    app as manage_conversation_api_router,
)
from openhands.server.routes.mcp import mcp_server
from openhands.server.routes.public import app as public_api_router
from openhands.server.routes.repo_ideas import app as repo_ideas_router
from openhands.server.routes.saved_repos import app as saved_repos_router
from openhands.server.routes.secrets import app as secrets_router
from openhands.server.routes.security import app as security_api_router
from openhands.server.routes.settings import app as settings_router
from openhands.server.routes.trajectory import app as trajectory_router
from openhands.server.routes.websocket import app as websocket_router
from openhands.server.shared import conversation_manager, server_config
from openhands.server.types import AppMode
from openhands.version import get_version

mcp_app = mcp_server.http_app(path='/mcp', stateless_http=True)


def combine_lifespans(*lifespans):
    # Create a combined lifespan to manage multiple session managers
    @contextlib.asynccontextmanager
    async def combined_lifespan(app):
        async with contextlib.AsyncExitStack() as stack:
            for lifespan in lifespans:
                await stack.enter_async_context(lifespan(app))
            yield

    return combined_lifespan


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    from openhands.server.conversation_pool_manager import (
        initialize_pool_manager,
        shutdown_pool_manager,
    )
    
    async with conversation_manager:
        # Initialize the conversation pool manager for pre-warming
        try:
            await initialize_pool_manager()
        except Exception as e:
            logger.warning(f'Failed to initialize ConversationPoolManager: {e}')
        
        yield
        
        # Shutdown the pool manager
        try:
            await shutdown_pool_manager()
        except Exception as e:
            logger.warning(f'Error shutting down ConversationPoolManager: {e}')


lifespans = [_lifespan, mcp_app.lifespan]
app_lifespan_ = get_app_lifespan_service()
if app_lifespan_:
    lifespans.append(app_lifespan_.lifespan)


app = FastAPI(
    title='OpenHands',
    description='OpenHands: Code Less, Make More',
    version=get_version(),
    lifespan=combine_lifespans(*lifespans),
    routes=[Mount(path='/mcp', app=mcp_app)],
)


@app.exception_handler(AuthenticationError)
async def authentication_error_handler(request: Request, exc: AuthenticationError):
    return JSONResponse(
        status_code=401,
        content=str(exc),
    )


app.include_router(public_api_router)
app.include_router(files_api_router)
app.include_router(security_api_router)
app.include_router(feedback_api_router)
app.include_router(conversation_api_router)
app.include_router(manage_conversation_api_router)
app.include_router(settings_router)
app.include_router(secrets_router)
app.include_router(repo_ideas_router)  # Must be before saved_repos_router for /ideas routes
app.include_router(saved_repos_router)
app.include_router(github_webhook_router)
if server_config.app_mode == AppMode.OPENHANDS:
    app.include_router(git_api_router)
if server_config.enable_v1:
    app.include_router(v1_router.router)
app.include_router(trajectory_router)
app.include_router(websocket_router)
add_health_endpoints(app)
