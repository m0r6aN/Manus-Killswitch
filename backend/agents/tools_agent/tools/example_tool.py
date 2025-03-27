import sys
import json
import time
import random

def run_tool(params: dict) -> dict:
    """
    An example tool function that takes parameters, simulates work,
    and returns a result dictionary.

    Args:
        params: A dictionary containing input parameters defined by the tool's schema.
                Expected: {"input_arg": "some string"}

    Returns:
        A dictionary containing the results.
    """
    input_arg = params.get("input_arg", "default value")
    operation = params.get("operation", "process") # Example optional param

    # Simulate some work
    time.sleep(random.uniform(0.5, 2.0))

    if operation == "fail":
         # Simulate a failure
         return {"status": "error", "message": "Simulated failure requested."}

    # Process the input
    processed_data = f"Processed '{input_arg}' using example_tool (operation: {operation}). Random number: {random.randint(1, 100)}"

    result = {
        "status": "success",
        "input_received": input_arg,
        "operation_performed": operation,
        "output": processed_data,
        "timestamp": time.time()
    }
    return result

if __name__ == "__main__":
    # This block allows the script to be executed directly by the executor.
    # It reads parameters from stdin (as JSON) and prints results to stdout (as JSON).
    try:
        input_json = sys.stdin.read()
        parameters = json.loads(input_json)

        # Call the main tool logic function
        tool_result = run_tool(parameters)

        # Print the result as JSON to stdout
        print(json.dumps(tool_result))
        sys.exit(0) # Success exit code

    except json.JSONDecodeError as e:
        error_output = {"status": "error", "message": f"Failed to decode input JSON: {e}"}
        print(json.dumps(error_output), file=sys.stderr) # Error to stderr
        sys.exit(1) # Failure exit code
    except Exception as e:
        error_output = {"status": "error", "message": f"An unexpected error occurred: {e}"}
        print(json.dumps(error_output), file=sys.stderr) # Error to stderr
        sys.exit(1) # Failure exit code