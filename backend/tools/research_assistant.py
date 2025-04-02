import sys
import json
import time
import random
import requests  # Mocked here; could integrate SerpAPI or Google Search

def research_assistant(params: dict) -> dict:
    """
    Conducts research by searching the web and summarizing findings.

    Args:
        params: {"topic": str, "depth": str ("light", "deep", default "light"), "max_sources": int (default 3)}
    Returns:
        Dict with research summary or error.
    """
    topic = params.get("topic")
    depth = params.get("depth", "light")
    max_sources = params.get("max_sources", 3)

    if not topic or not isinstance(topic, str):
        return {"status": "error", "message": "Topic must be a non-empty string"}
    if depth not in ["light", "deep"]:
        return {"status": "error", "message": "Depth must be 'light' or 'deep'"}

    # Simulate research process
    time.sleep(random.uniform(1.0, 2.0 if depth == "light" else 4.0))
    sources = [
        {"url": f"http://mocksource.com/{i}", "snippet": f"Info about {topic} from source {i}"}
        for i in range(1, min(max_sources + 1, 4))
    ]
    summary = f"Research on '{topic}': {len(sources)} sources found. " + \
             ("Quick overview." if depth == "light" else "Detailed analysis.")

    return {
        "status": "success",
        "topic": topic,
        "depth": depth,
        "sources": sources,
        "summary": summary,
        "timestamp": time.time()
    }

if __name__ == "__main__":
    try:
        input_json = sys.stdin.read()
        parameters = json.loads(input_json)
        result = research_assistant(parameters)
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        error_output = {"status": "error", "message": f"Error: {str(e)}"}
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)