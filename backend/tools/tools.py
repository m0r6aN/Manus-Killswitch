# Local Tool Implementations
import ast
import aiofiles


async def web_search(tool_input: dict) -> dict:
    query = tool_input.get("query", "")
    if not query:
        return {"status": "error", "error": "No query provided"}
    mock_results = [{"title": f"Result for {query}", "url": "http://google.com"}]
    return {"status": "success", "query": query, "results": mock_results}

async def web_scrape(tool_input: dict) -> dict:
    url = tool_input.get("url", "")
    if not url:
        return {"status": "error", "error": "No URL provided"}
    mock_content = f"Mocked content from {url}"
    return {"status": "success", "url": url, "content": mock_content}

async def file_rw(tool_input: dict) -> dict:
    mode = tool_input.get("mode", "read")
    path = tool_input.get("path", "")
    content = tool_input.get("content", "") if mode == "write" else None
    if not path:
        return {"status": "error", "error": "No file path provided"}
    try:
        if mode == "read":
            async with aiofiles.open(path, "r") as f:
                file_content = await f.read()
            return {"status": "success", "mode": "read", "path": path, "content": file_content}
        elif mode == "write":
            if not content:
                return {"status": "error", "error": "No content provided for write"}
            async with aiofiles.open(path, "w") as f:
                await f.write(content)
            return {"status": "success", "mode": "write", "path": path, "content": content}
        return {"status": "error", "error": f"Invalid mode: {mode}"}
    except Exception as e:
        return {"status": "error", "error": f"File operation failed: {str(e)}"}

async def local_file_retriever(tool_input: dict) -> dict:
    path = tool_input.get("path", "")
    if not path:
        return {"status": "error", "error": "No file path provided"}
    try:
        async with aiofiles.open(path, "r") as f:
            content = await f.read()
        parsed = {}
        if path.endswith(".py"):
            tree = ast.parse(content)
            parsed = {
                "functions": [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)],
                "imports": [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]
            }
        return {"status": "success", "path": path, "content": content, "parsed": parsed}
    except Exception as e:
        return {"status": "error", "error": f"Failed to process file: {str(e)}"}