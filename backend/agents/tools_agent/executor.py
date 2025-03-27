# Tool execution logic
import subprocess
import sys
import os
import json
import importlib
import traceback
from typing import Dict, Any, Tuple
import asyncio
from jsonschema import validate, ValidationError

from backend.core.config import settings, logger
from . import models

# Get the configured tools directory
TOOLS_BASE_DIR = settings.TOOLS_DIR
logger.info(f"Tool Executor initialized. Base directory for tools: {TOOLS_BASE_DIR}")

def validate_parameters(schema: Dict[str, Any], parameters: Dict[str, Any]) -> Tuple[bool, Dict[str, Any] | None]:
    """Validates input parameters against the tool's JSON schema."""
    if not schema: # No schema defined, assume valid
        return True, None
    try:
        validate(instance=parameters, schema=schema)
        logger.debug("Parameter validation successful.")
        return True, None
    except ValidationError as e:
        logger.warning(f"Parameter validation failed: {e.message}")
        # Provide more context about the error
        error_details = {
            "message": e.message,
            "path": list(e.path),
            "schema_path": list(e.schema_path),
            "validator": e.validator,
            "validator_value": e.validator_value,
            # "instance": e.instance, # Be careful logging potentially sensitive instance data
            # "schema": e.schema,     # Can be large
        }
        return False, error_details
    except Exception as e:
        logger.error(f"Unexpected error during parameter validation: {e}")
        return False, {"message": f"Unexpected validation error: {e}"}

async def execute_script_tool(
    tool: models.Tool,
    parameters: Dict[str, Any]
) -> Tuple[bool, Any, str | None]:
    """
    Executes a tool defined as a Python script using subprocess for isolation.
    Passes parameters as JSON via stdin. Expects JSON output via stdout.
    Returns (success: bool, result: Any, error: str | None).
    """
    if not tool.path:
        return False, None, "Tool path is not defined for script execution."

    script_path = os.path.join(TOOLS_BASE_DIR, tool.path)
    if not os.path.exists(script_path):
        logger.error(f"Script file not found at resolved path: {script_path}")
        return False, None, f"Script file not found: {tool.path}"
    if not os.path.isfile(script_path):
         return False, None, f"Tool path is not a file: {tool.path}"


    logger.info(f"Executing script tool: {script_path}")
    logger.debug(f"Parameters (sent via stdin): {parameters}")

    try:
        # Prepare parameters as JSON string
        input_json = json.dumps(parameters)

        # Execute the script in a separate process
        process = await asyncio.create_subprocess_exec(
            sys.executable, # Use the same Python interpreter
            script_path,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        # Send parameters via stdin and capture output/error
        stdout_data, stderr_data = await process.communicate(input=input_json.encode())

        # Decode output and error streams
        stdout = stdout_data.decode().strip()
        stderr = stderr_data.decode().strip()

        logger.debug(f"Script stdout: {stdout[:500]}...") # Log truncated stdout
        if stderr:
             logger.warning(f"Script stderr: {stderr}")

        if process.returncode == 0:
            logger.success(f"Script '{tool.name}' executed successfully (return code 0).")
            try:
                # Assume script outputs JSON result to stdout
                result = json.loads(stdout) if stdout else None
                return True, result, None
            except json.JSONDecodeError:
                logger.error(f"Script '{tool.name}' stdout was not valid JSON: {stdout[:100]}...")
                # Return raw stdout as error or content? Let's return error.
                return False, None, f"Script output was not valid JSON. Raw output: {stdout}"
        else:
            logger.error(f"Script '{tool.name}' failed with return code {process.returncode}.")
            error_message = f"Script execution failed (code {process.returncode})."
            if stderr:
                error_message += f" Stderr: {stderr}"
            elif stdout: # If error message is on stdout
                 error_message += f" Stdout: {stdout}"
            return False, None, error_message

    except FileNotFoundError:
         logger.error(f"Python executable '{sys.executable}' not found.")
         return False, None, "Python executable not found."
    except Exception as e:
        logger.exception(f"Unexpected error executing script tool '{tool.name}': {e}")
        return False, None, f"Unexpected execution error: {e}"

async def execute_tool(
    tool: models.Tool,
    parameters: Dict[str, Any],
    dry_run: bool = False
) -> Tuple[bool, Any, str | None, Dict[str, Any] | None]:
    """
    Executes a tool based on its type, performing validation first.

    Returns:
        Tuple[bool, Any, str | None, Dict[str, Any] | None]:
        - success: bool - True if validation passed and execution (if not dry_run) was successful.
        - result: Any - The output from the tool execution (or None).
        - error: str | None - Error message if validation or execution failed.
        - validation_errors: Dict | None - Detailed validation errors if they occurred.
    """
    logger.info(f"Attempting to execute tool '{tool.name}' (ID: {tool.id}, Type: {tool.type}). Dry run: {dry_run}")

    # 1. Validate Parameters
    schema = tool.parameter_schema
    is_valid, validation_errors = validate_parameters(schema, parameters)

    if not is_valid:
        logger.warning(f"Parameter validation failed for tool '{tool.name}'.")
        return False, None, "Parameter validation failed.", validation_errors

    logger.debug(f"Parameter validation successful for tool '{tool.name}'.")

    if dry_run:
        logger.info(f"Dry run for tool '{tool.name}'. Execution skipped.")
        return True, {"message": "Dry run successful: Parameters are valid."}, None, None

    # 2. Execute based on type
    success = False
    result = None
    error = None

    if tool.type == 'script':
        success, result, error = await execute_script_tool(tool, parameters)
    elif tool.type == 'function':
        # Placeholder for function execution (requires importlib, security considerations)
        error = f"Tool type 'function' execution not yet implemented."
        logger.warning(error)
        success = False
    elif tool.type == 'module':
        # Placeholder for module execution
        error = f"Tool type 'module' execution not yet implemented."
        logger.warning(error)
        success = False
    else:
        error = f"Unsupported tool type: {tool.type}"
        logger.error(error)
        success = False

    if success:
        logger.success(f"Tool '{tool.name}' executed successfully.")
    else:
        logger.error(f"Tool '{tool.name}' execution failed. Error: {error}")

    return success, result, error, None # No validation errors at this stage if dry_run=False