import aiofiles

async def file_rw(tool_input: dict) -> dict:
    mode = tool_input.get("mode", "read")
    path = tool_input.get("path", "")
    content = tool_input.get("content", "") if mode == "write" else None
    if not path or "../" in path or path.startswith("/"):  # Basic safety
        return {"status": "error", "error": "Invalid or unsafe file path"}
        
    try:
        if mode == "read":
            async with aiofiles.open(path, "r") as f:
                file_content = await f.read()
            return {
                "status": "success",
                "mode": "read",
                "path": path,
                "content": file_content
            }
        elif mode == "write":
            if not content:
                return {"status": "error", "error": "No content provided for write"}
            async with aiofiles.open(path, "w") as f:
                await f.write(content)
            return {
                "status": "success",
                "mode": "write",
                "path": path,
                "content": content
            }
        else:
            return {"status": "error", "error": f"Invalid mode: {mode}"}
    except FileNotFoundError:
        return {"status": "error", "error": f"File not found: {path}"}
    except Exception as e:
        return {"status": "error", "error": f"File operation failed: {str(e)}"}