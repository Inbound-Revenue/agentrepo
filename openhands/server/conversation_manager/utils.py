# IMPORTANT: LEGACY V0 CODE - Deprecated since version 1.0.0, scheduled for removal April 1, 2026
# This file is part of the legacy (V0) implementation of OpenHands and will be removed soon as we complete the migration to V1.
# OpenHands V1 uses the Software Agent SDK for the agentic core and runs a new application server. Please refer to:
#   - V1 agentic core (SDK): https://github.com/OpenHands/software-agent-sdk
#   - V1 application server (in this repo): openhands/app_server/
# Unless you are working on deprecation, please avoid extending this legacy file and consult the V1 codepaths above.
# Tag: Legacy-V0
# This module belongs to the old V0 web server. The V1 application server lives under openhands/app_server/.

import yaml

from openhands.core.logger import openhands_logger as logger
from openhands.events.action import CmdRunAction, FileReadAction
from openhands.events.observation import CmdOutputObservation, FileReadObservation
from openhands.runtime.base import Runtime
from openhands.utils.async_utils import call_sync_from_async


async def execute_autostart_commands(
    runtime: Runtime,
    sid: str,
    selected_repository: str | None = None,
) -> None:
    """Execute autostart commands from .openhands/autostart.yaml if it exists.

    This is a shared utility that works with any Runtime type (Local, Docker, Remote).
    It reads the autostart configuration from the workspace and executes defined
    startup commands before the agent begins.

    Supports two YAML formats:
    - Legacy: `startup: [...]`
    - New: `autostart: {enabled: true, commands: [...]}`

    Commands marked as 'background: true' will be run with nohup/disown
    to prevent them from being stopped by terminal signals.

    Args:
        runtime: The runtime instance to execute commands on
        sid: Session/conversation ID for logging
        selected_repository: Optional repository name (e.g., 'owner/repo')
    """
    workspace_path = runtime.config.workspace_mount_path_in_sandbox
    if not workspace_path:
        logger.debug('Autostart: No workspace path configured, skipping')
        return

    # Determine config path based on whether a repository is selected
    if selected_repository:
        repo_name = selected_repository.split('/')[-1]
        config_path = f'{workspace_path}/{repo_name}/.openhands/autostart.yaml'
    else:
        config_path = f'{workspace_path}/.openhands/autostart.yaml'

    logger.info(f'Autostart: Looking for config at {config_path}')

    try:
        # Read the autostart config file
        read_action = FileReadAction(path=config_path)
        read_obs = await call_sync_from_async(runtime.read, read_action)

        if not isinstance(read_obs, FileReadObservation):
            logger.debug(f'Autostart: No config found at {config_path}')
            return

        if not read_obs.content or read_obs.content.startswith('ERROR'):
            logger.debug(f'Autostart: Could not read {config_path}')
            return

        # Parse YAML config
        config = yaml.safe_load(read_obs.content)
        if not config:
            logger.debug('Autostart: Empty config file')
            return

        # Support both 'startup' (legacy) and 'autostart.commands' (new) formats
        commands = None
        if 'startup' in config:
            commands = config['startup']
        elif 'autostart' in config and isinstance(config['autostart'], dict):
            autostart_config = config['autostart']
            # Check if enabled (default True if not specified)
            if autostart_config.get('enabled', True):
                commands = autostart_config.get('commands', [])

        if not commands:
            logger.debug('Autostart: No startup commands in config')
            return

        logger.info(
            f'Autostart: Found {len(commands)} startup commands',
            extra={'session_id': sid},
        )

        # Execute each startup command
        for cmd_config in commands:
            name = cmd_config.get('name', 'unnamed')
            command = cmd_config.get('command', '')
            condition = cmd_config.get('condition')
            background = cmd_config.get('background', False)
            timeout = cmd_config.get('timeout', 120)

            if not command:
                logger.warning(f'Autostart: Skipping {name} - no command specified')
                continue

            # Check condition if specified
            if condition:
                check_cmd = (
                    f'[ {condition} ] && echo CONDITION_MET || echo CONDITION_NOT_MET'
                )
                check_action = CmdRunAction(
                    command=check_cmd, blocking=True, hidden=True
                )
                check_action.set_hard_timeout(30)
                check_obs = await call_sync_from_async(runtime.run, check_action)

                if isinstance(check_obs, CmdOutputObservation):
                    if 'CONDITION_NOT_MET' in check_obs.content:
                        logger.info(
                            f'Autostart: Skipping "{name}" - condition not met',
                            extra={'session_id': sid},
                        )
                        continue

            # Prepare the command
            if background:
                # Use nohup and disown to prevent SIGTSTP from stopping the process
                # Also redirect output to a log file for debugging
                safe_name = name.replace(' ', '_').replace('/', '_')
                log_file = f'/tmp/autostart_{safe_name}.log'
                command = f'nohup {command} > {log_file} 2>&1 & disown'

            logger.info(
                f'Autostart: Running "{name}"',
                extra={'session_id': sid, 'command': command},
            )

            # Execute the command
            run_action = CmdRunAction(command=command, blocking=True, hidden=True)
            run_action.set_hard_timeout(timeout)
            run_obs = await call_sync_from_async(runtime.run, run_action)

            if isinstance(run_obs, CmdOutputObservation):
                if run_obs.exit_code != 0 and not background:
                    logger.warning(
                        f'Autostart: "{name}" exited with code {run_obs.exit_code}',
                        extra={'session_id': sid, 'output': run_obs.content[:500]},
                    )
                else:
                    logger.info(
                        f'Autostart: "{name}" completed successfully',
                        extra={'session_id': sid},
                    )
            else:
                logger.warning(
                    f'Autostart: "{name}" returned unexpected observation type',
                    extra={'session_id': sid},
                )

    except yaml.YAMLError as e:
        logger.warning(f'Autostart: Failed to parse YAML config: {e}')
    except Exception as e:
        logger.warning(
            f'Autostart: Execution failed: {e}',
            extra={'session_id': sid},
        )
