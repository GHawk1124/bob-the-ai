import asyncio
import json
import threading
import queue
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from sse_starlette.sse import EventSourceResponse

import config
import state
from loop import run_agent_loop
from tools.say import set_message_queue
from tools.request_user_input import set_response_queue
from tools.shell import execute_shell

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize queues and start agent on startup."""
    state.CONTEXT_WINDOW = config.fetch_model_context_window()

    set_message_queue(state.message_queue)
    set_response_queue(state.response_queue)
    
    agent_thread = threading.Thread(target=run_agent_loop, daemon=True)
    agent_thread.start()
    
    print(f"[BOB] Server starting on 0.0.0.0:{config.HTTP_PORT}")
    yield
    print("[BOB] Server shutting down")

app = FastAPI(lifespan=lifespan)

@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "timestamp": datetime.now().isoformat()}

@app.post("/message")
async def receive_message(request: Request):
    """Receive a message from a user."""
    data = await request.json()
    content = data.get("content", "")
    request_id = data.get("request_id")
    
    if request_id:
        await state.response_queue.put(content)
        return {"status": "response_received", "request_id": request_id}
    else:
        await state.user_input_queue.put(content)
        return {"status": "message_queued"}

@app.get("/stream")
async def stream_messages(request: Request):
    """SSE endpoint for streaming Bob's output to users."""
    async def event_generator():
        yield {
            "event": "config",
            "data": json.dumps({
                "max_tokens": state.CONTEXT_WINDOW,
                "model_name": config.MODEL_NAME
            })
        }

        while True:
            if await request.is_disconnected():
                break
            
            try:
                while True:
                    activity = state.activity_queue.get_nowait()
                    yield {
                        "event": activity.get("type", "activity"),
                        "data": activity.get("content", "")
                    }
            except queue.Empty:
                pass
            
            try:
                msg = await asyncio.wait_for(state.message_queue.get(), timeout=0.5)
                yield {
                    "event": msg.get("type", "message"),
                    "data": msg.get("content", "")
                }
            except asyncio.TimeoutError:
                yield {"event": "heartbeat", "data": ""}
    
    return EventSourceResponse(event_generator())

@app.post("/control")
async def control_agent(request: Request):
    """Control agent state (pause/resume)."""
    data = await request.json()
    action = data.get("action")
    
    if action == "pause":
        state.PAUSED = True
        print("[BOB] Paused by user command", flush=True)
        return {"status": "paused"}
    elif action == "resume":
        state.PAUSED = False
        print("[BOB] Resumed by user command", flush=True)
        return {"status": "resumed"}
    
    return {"status": "error", "message": "Invalid action"}

@app.post("/shell")
async def run_shell_command(request: Request):
    """Execute a shell command directly."""
    data = await request.json()
    command = data.get("command")
    
    if not command:
        return {"status": "error", "message": "No command provided"}
        
    print(f"[BOB] direct shell command: {command}", flush=True)
    try:
        loop = asyncio.get_running_loop()
        output = await loop.run_in_executor(None, lambda: execute_shell(command))
        return {"status": "success", "output": output}
    except Exception as e:
        return {"status": "error", "output": str(e)}
