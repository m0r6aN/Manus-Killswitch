import sys
import json
import time
import random

def sentiment_analyzer(params: dict) -> dict:
    """
    Analyzes the sentiment of a text input.

    Args:
        params: {"text": str}
    Returns:
        Dict with sentiment score or error.
    """
    text = params.get("text")

    if not text or not isinstance(text, str):
        return {"status": "error", "message": "Text must be a non-empty string"}

    # Simulate sentiment analysis (could use NLTK or TextBlob IRL)
    time.sleep(random.uniform(0.2, 0.8))
    score = random.uniform(-1.0, 1.0)  # -1 (negative) to 1 (positive)
    sentiment = "positive" if score > 0.3 else "negative" if score < -0.3 else "neutral"

    return {
        "status": "success",
        "text": text[:50] + ("..." if len(text) > 50 else ""),
        "sentiment": sentiment,
        "score": score,
        "timestamp": time.time()
    }

if __name__ == "__main__":
    try:
        input_json = sys.stdin.read()
        parameters = json.loads(input_json)
        result = sentiment_analyzer(parameters)
        print(json.dumps(result))
        sys.exit(0)
    except Exception as e:
        error_output = {"status": "error", "message": f"Error: {str(e)}"}
        print(json.dumps(error_output), file=sys.stderr)
        sys.exit(1)