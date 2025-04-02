import sys
import json
import time
import random

def public_data_oracle(params: dict) -> dict:
    """
    Fetches data from public data sources based on a query.

    Args:
        params: {"query": str, "source": str ("wiki", "stats", default "wiki")}
    Returns:
        Dict with data or error.
    """
    query = params.get("query")
    source = params.get("source", "wiki")

    if not query or not isinstance(query, str):
        return {"status": "error", "message": "Query must be a non-empty string"}
    if source not in ["wiki", "stats"]:
        return {"status": "error", "message": "Source must be 'wiki' or 'stats'"}

    # Simulate API call
    time.sleep(random.uniform(0.5, 1.5))
    data = {
        "wiki": f"Mock Wikipedia entry for {query}",
        "stats": {"value": random.randint(100, 1000), "unit": "mock units"}
    }.get(source)

    return {
        "status": "success",
        "query": query,
        "source": source,
        "data": data,
        "timestamp": time.time()
    }

if __name__ == "__main__":
    try:
        input_json = sys.stdin.read()
        parameters = json.loads(input_json)
        result = public_data_oracle(parameters)
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        error_output = {"status": "error", "message": f"Error: {str(e)}"}
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)