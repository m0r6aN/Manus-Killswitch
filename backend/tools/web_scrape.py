async def web_scrape(tool_input: dict) -> dict:
    url = tool_input.get("url", "")
    if not url:
        return {"status": "error", "error": "No URL provided"}
    
    # Mocked scrape (replace with httpx/BS4 later)
    mock_content = f"Mocked content scraped from {url}"
    return {
        "status": "success",
        "url": url,
        "content": mock_content
    }