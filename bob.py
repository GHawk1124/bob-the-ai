"""
Bob - An AI Agent with Cognitive Loop Architecture

This module implements Bob's core loop:
1. OBSERVE - Receive messages, tool results, heartbeat
2. RETRIEVE - Pull relevant memories from GraphRAG
3. THINK/PLAN - LLM decides next actions
4. ACT - Execute tool calls
5. CONSOLIDATE - Curate what gets stored, reply or schedule next loop
"""
import asyncio
import os
import sys
import ssl
import threading
import json
import urllib.request
import urllib.error
from typing import Optional, Dict, Any, List
from datetime import datetime
from contextlib import asynccontextmanager

# FastAPI and HTTP
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
from sse_starlette.sse import EventSourceResponse
import uvicorn

# LangChain
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain.tools import tool
from langchain.agents.middleware import SummarizationMiddleware, TodoListMiddleware

# Import tools
from tools.say import say, set_message_queue, get_message_queue
from tools.search import web_search, crawl_url
from tools.graphrag import store_memory, retrieve_memory
from tools.modify_system_prompt import modify_system_prompt, read_system_prompt
from tools.request_user_input import request_user_input, set_response_queue
from tools.shell import execute_shell
from tools.filesystem import (
    create_directory, remove_directory, list_directory,
    create_file, view_file, remove_file, edit_file, append_to_file
)
from tools.wolfram import wolfram_query


# ============================================================================
# Configuration
# ============================================================================

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://spark-bcce.hlab:8080/api")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "not-needed")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-oss:120b")
SYSTEM_PROMPT_PATH = "/app/SYSTEM_PROMPT.md"
HTTP_PORT = 8000
HTTP_PORT = 8000
CONTEXT_WINDOW = 128000  # Default, will be updated dynamically


def fetch_model_context_window() -> int:
    """Fetch the context window for the configured model from the API."""
    print(f"[BOB] Fetching context window for {MODEL_NAME}...")
    try:
        # Construct URL - assume standard Ollama/OpenAI-like endpoint
        # If OPENAI_BASE_URL ends with /api or /v1, strip it or append /models
        base = OPENAI_BASE_URL.rstrip("/")
        url = f"{base}/models"
        
        req = urllib.request.Request(url)
        if OPENAI_API_KEY and OPENAI_API_KEY != "not-needed":
            req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
        
        # Disable SSL verification if needed (local network)
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            
        # Parse data to find our model
        # OpenWebUI /api/models returns list of models in 'data'
        for model in data.get("data", []):
            if model.get("id") == MODEL_NAME:
                # OpenWebUI: info -> num_ctx or context_length
                info = model.get("info", {})
                params = info.get("params", {})
                ctx = info.get("context_length") or params.get("num_ctx") or model.get("context_window")
                
                if ctx:
                    print(f"[BOB] Found context window: {ctx}")
                    return int(ctx)
                    
        print(f"[BOB] Model {MODEL_NAME} not found in API response, using default.")
        return 128000
    except Exception as e:
        print(f"[BOB] Error fetching model context: {e}")
        return 128000


# ============================================================================
# HTTP Server & Message Queues
# ============================================================================

# Queues for async communication
import queue  # Thread-safe queue for agent activity

message_queue: asyncio.Queue = asyncio.Queue(maxsize=100)  # Bob -> Users (say tool)
user_input_queue: asyncio.Queue = asyncio.Queue(maxsize=10)  # Users -> Bob (messages)
response_queue: asyncio.Queue = asyncio.Queue(maxsize=10)  # Users -> Bob (input responses)
activity_queue: queue.Queue = queue.Queue(maxsize=200)  # Agent activity (thread-safe)


# Control flags
PAUSED = False

# Pending messages for users to consume
outgoing_messages: List[Dict[str, Any]] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize queues and start agent on startup."""
    # Update context window dynamically
    global CONTEXT_WINDOW
    CONTEXT_WINDOW = fetch_model_context_window()

    set_message_queue(message_queue)
    set_response_queue(response_queue)
    
    # Start the agent loop in a background thread
    agent_thread = threading.Thread(target=run_agent_loop, daemon=True)
    agent_thread.start()
    
    print(f"[BOB] Server starting on 0.0.0.0:{HTTP_PORT}")
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
    request_id = data.get("request_id")  # For input responses
    
    if request_id:
        # This is a response to an input request
        await response_queue.put(content)
        return {"status": "response_received", "request_id": request_id}
    else:
        # Regular message
        await user_input_queue.put(content)
        return {"status": "message_queued"}


@app.get("/stream")
async def stream_messages(request: Request):
    """SSE endpoint for streaming Bob's output to users."""
    async def event_generator():
        # Send configuration first
        yield {
            "event": "config",
            "data": json.dumps({
                "max_tokens": CONTEXT_WINDOW,
                "model_name": MODEL_NAME
            })
        }

        while True:
            if await request.is_disconnected():
                break
            
            # Check thread-safe activity queue first (non-blocking)
            try:
                while True:
                    activity = activity_queue.get_nowait()
                    yield {
                        "event": activity.get("type", "activity"),
                        "data": activity.get("content", "")
                    }
            except queue.Empty:
                pass
            
            try:
                # Check for new messages from Bob (say tool)
                msg = await asyncio.wait_for(message_queue.get(), timeout=0.5)
                yield {
                    "event": msg.get("type", "message"),
                    "data": msg.get("content", "")
                }
            except asyncio.TimeoutError:
                # Send heartbeat
                yield {"event": "heartbeat", "data": ""}
    
    return EventSourceResponse(event_generator())



@app.post("/control")
async def control_agent(request: Request):
    """Control agent state (pause/resume)."""
    global PAUSED
    data = await request.json()
    action = data.get("action")
    
    if action == "pause":
        PAUSED = True
        print("[BOB] Paused by user command", flush=True)
        return {"status": "paused"}
    elif action == "resume":
        PAUSED = False
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
        # Run in executor to not block async loop
        loop = asyncio.get_running_loop()
        output = await loop.run_in_executor(None, lambda: execute_shell(command))
        return {"status": "success", "output": output}
    except Exception as e:
        return {"status": "error", "output": str(e)}


# ============================================================================
# Load System Prompt
# ============================================================================

def load_system_prompt() -> str:
    """Load the system prompt from file."""
    try:
        with open(SYSTEM_PROMPT_PATH, 'r') as f:
            return f.read()
    except FileNotFoundError:
        return "You are Bob, an AI assistant."


# ============================================================================
# Agent Setup
# ============================================================================

def create_bob_agent():
    """Create the LangChain agent with all tools and middleware."""
    
    # Initialize LLM
    # Note: Context window (128k for gpt-oss:120b) is configured on the LLM server
    llm = ChatOpenAI(
        model=MODEL_NAME,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        use_responses_api=False,
        streaming=True,
    )
    
    # Summarization LLM (same local model)
    summarization_llm = ChatOpenAI(
        model=MODEL_NAME,
        api_key=OPENAI_API_KEY,
        base_url=OPENAI_BASE_URL,
        use_responses_api=False,
    )
    
    # All tools
    tools = [
        say,
        web_search,
        crawl_url,
        wolfram_query,
        store_memory,
        retrieve_memory,
        modify_system_prompt,
        read_system_prompt,
        request_user_input,
        execute_shell,
        # File system tools
        create_directory,
        remove_directory,
        list_directory,
        create_file,
        view_file,
        remove_file,
        edit_file,
        append_to_file,
    ]
    
    # Create agent with middleware
    agent = create_agent(
        model=llm,
        tools=tools,
        middleware=[
            SummarizationMiddleware(
                model=summarization_llm,
                trigger=("tokens", 4000),
                keep=("messages", 20),
            ),
            TodoListMiddleware(),
        ],
    )
    
    return agent


# ============================================================================
# Cognitive Loop
# ============================================================================

def run_agent_loop():
    """Main cognitive loop running in background thread."""
    
    # Create event loop for this thread
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    print("[BOB] Initializing cognitive loop...")
    
    # Load system prompt
    system_prompt = load_system_prompt()
    print(f"[BOB] System prompt loaded ({len(system_prompt)} chars)")
    
    # Create agent
    agent = create_bob_agent()
    print("[BOB] Agent created with tools and middleware")
    
    # Message history
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    # Initial self-prompt (Bob prompts itself to start)
    initial_prompt = """You have just been initialized. Take a moment to:
1. Read your system prompt to understand your purpose
2. Check if you have any stored memories
3. Prepare to receive user input

Begin by reflecting on who you are and what you're meant to do."""
    
    messages.append({"role": "user", "content": initial_prompt})
    
    # Heartbeat interval (seconds)
    HEARTBEAT_INTERVAL = 30
    last_heartbeat = datetime.now()
    
    # Flag to run agent immediately on first iteration
    first_run = True
    
    print("[BOB] Starting main loop...", flush=True)
    
    while True:
        # Check pause state
        if PAUSED:
            loop.run_until_complete(asyncio.sleep(1))
            continue

        try:
            # ================================================================
            # OBSERVE - Check for new inputs
            # ================================================================
            
            user_message = None
            heartbeat_triggered = False
            
            # Check for user messages (non-blocking with short timeout)
            try:
                user_message = loop.run_until_complete(
                    asyncio.wait_for(user_input_queue.get(), timeout=0.5)
                )
            except asyncio.TimeoutError:
                pass
            
            # Check heartbeat
            now = datetime.now()
            if (now - last_heartbeat).total_seconds() > HEARTBEAT_INTERVAL:
                heartbeat_triggered = True
                last_heartbeat = now
            
            # Determine if we should run the agent
            should_run = first_run  # Run if this is the first iteration
            
            if user_message:
                print(f"[BOB] Received user message: {user_message[:100]}...", flush=True)
                messages.append({"role": "user", "content": user_message})
                should_run = True
            elif heartbeat_triggered:
                # Heartbeat - agent can check state, run maintenance
                messages.append({
                    "role": "user", 
                    "content": f"[HEARTBEAT {now.isoformat()}] No new user input. You may continue any ongoing tasks, reflect, or wait for input."
                })
                should_run = True
            
            if not should_run:
                # Nothing to do, short sleep
                loop.run_until_complete(asyncio.sleep(0.1))
                continue
            
            # Clear first_run flag
            first_run = False
            
            # ================================================================
            # RETRIEVE + THINK/PLAN + ACT
            # ================================================================
            # The agent handles retrieval, planning, and action internally
            # through tool calls (retrieve_memory, etc.)
            
            print("[BOB] Running agent...", flush=True)
            
            try:
                step = None
                for step in agent.stream(
                    {"messages": messages},
                    stream_mode="values",
                ):
                    # Get the last message
                    last_msg = step["messages"][-1]
                    msg_type = type(last_msg).__name__
                    
                    # Stream to console AND to activity queue for user.py
                    if hasattr(last_msg, 'content'):
                        content = last_msg.content
                        if content:
                            display_content = content[:200] + "..." if len(content) > 200 else content
                            print(f"[THINK] {display_content}", flush=True)
                            # Stream to user.py via thread-safe queue
                            try:
                                activity_queue.put_nowait({"type": "think", "content": display_content})
                            except queue.Full:
                                pass
                    
                    # Check for tool calls
                    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                        for tc in last_msg.tool_calls:
                            tool_name = tc.get('name', 'unknown')
                            tool_args = str(tc.get('args', {}))[:100]
                            print(f"[TOOL CALL] {tool_name}: {tool_args}", flush=True)
                            # Stream to user.py via thread-safe queue
                            try:
                                activity_queue.put_nowait({"type": "tool", "content": f"{tool_name}: {tool_args}"})
                            except queue.Full:
                                pass
                    
                    print(f"[DEBUG] Message type: {msg_type}", flush=True)
                
                print("[BOB] Agent stream completed", flush=True)
                
            except Exception as stream_error:
                print(f"[BOB] Stream error: {stream_error}", flush=True)
                import traceback
                traceback.print_exc()
            
            # Update message history with assistant response
            if step and "messages" in step:
                # Keep the conversation going
                messages = step["messages"]
                print(f"[BOB] Updated message history, now {len(messages)} messages", flush=True)
            
            # ================================================================
            # CONSOLIDATE
            # ================================================================
            # The agent decides what to store via store_memory tool
            # Here we just trim history if too long
            
            if len(messages) > 50:
                # Keep system prompt + last 40 messages
                messages = [messages[0]] + messages[-40:]
                print("[BOB] Trimmed message history", flush=True)
            
        except KeyboardInterrupt:
            print("[BOB] Interrupted, shutting down...", flush=True)
            break
        except Exception as e:
            print(f"[BOB] Error in loop: {e}", flush=True)
            import traceback
            traceback.print_exc()
            # Continue after error
            loop.run_until_complete(asyncio.sleep(1))


# ============================================================================
# Main Entry Point
# ============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("BOB - Cognitive Loop AI Agent")
    print("=" * 60)
    print(f"Model: {MODEL_NAME}")
    print(f"API Base: {OPENAI_BASE_URL}")
    print(f"HTTP Port: {HTTP_PORT}")
    print("=" * 60)
    
    # Run the HTTP server (agent loop starts in lifespan)
    uvicorn.run(app, host="0.0.0.0", port=HTTP_PORT)
