from restrictedpython import compile_restricted, safe_globals, limited_builtins
import io
from contextlib import redirect_stdout

async def python_exec(tool_input: dict) -> dict:
    code = tool_input.get("code", "")
    if not code:
        return {"status": "error", "error": "No code provided"}
    
    try:
        # Compile with RestrictedPython
        byte_code = compile_restricted(code, "<inline>", "exec")
        
        # Sandboxed environment
        restricted_globals = safe_globals.copy()
        restricted_globals["__builtins__"] = limited_builtins
        output = io.StringIO()
        
        # Execute with stdout redirection
        with redirect_stdout(output):
            exec(byte_code, restricted_globals)
        
        return {
            "status": "success",
            "code": code,
            "output": output.getvalue()
        }
    except SyntaxError as e:
        return {"status": "error", "error": f"Syntax error: {str(e)}"}
    except Exception as e:
        return {"status": "error", "error": f"Execution failed: {str(e)}"}