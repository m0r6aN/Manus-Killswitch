async def web_search(tool_input: dict) -> dict:
    query = tool_input.get("query", "")
    if not query:
        return {"status": "error", "error": "No query provided"}
    
    # Mocked search (replace with real API like SerpAPI/Google later)
    mock_results = [
        {"title": f"Result 1 for {query}", "url": "http://mocked.com/1"},
        {"title": f"Result 2 for {query}", "url": "http://mocked.com/2"}
    ]
    return {
        "status": "success",
        "query": query,
        "results": mock_results
    }