import ast
import aiofiles

async def local_file_retriever(tool_input: dict) -> dict:
    path = tool_input.get("path", "")
    if not path:
        return {"status": "error", "error": "No file path provided"}
    
    try:
        async with aiofiles.open(path, "r") as f:
            content = await f.read()
        
        # Parse Python code with AST
        if path.endswith(".py"):
            tree = ast.parse(content)
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            imports = [node.names[0].name for node in ast.walk(tree) if isinstance(node, ast.Import)]
            parsed = {"functions": functions, "imports": imports}
        else:
            parsed = {}  # Non-Python files get raw content only
        
        return {
            "status": "success",
            "path": path,
            "content": content,
            "parsed": parsed
        }
    except FileNotFoundError:
        return {"status": "error", "error": f"File not found: {path}"}
    except SyntaxError:
        return {"status": "error", "error": f"Syntax error in {path}"}
    except Exception as e:
        return {"status": "error", "error": f"Failed to process file: {str(e)}"}