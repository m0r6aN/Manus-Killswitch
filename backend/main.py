from fastapi import FastAPI
from backend.tools.api_integration import register_execute_routes
from backend.tools.tool_core import tool_core_api  # Optional Redis listener

app = FastAPI(title="Manus Killswitch API", version="1.0.0")

# Register ToolCore routes
register_execute_routes(app)

# Optional: Start Redis listener
@app.on_event("startup")
async def startup_event():
    await tool_core_api.start()  # If using Redis tool_requests

@app.on_event("shutdown")
async def shutdown_event():
    await tool_core_api.shutdown()  # If using Redis tool_requests

# Example root endpoint (optional)
@app.get("/")
async def root():
    return {"message": "Welcome to Manus Killswitch!"}