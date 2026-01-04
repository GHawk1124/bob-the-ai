import asyncio
import queue
import datetime
from datetime import datetime as dt
import state
from agent import create_bob_agent, load_system_prompt

def run_agent_loop():
    """Main cognitive loop running in background thread."""
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    print("[BOB] Initializing cognitive loop...")
    
    system_prompt = load_system_prompt()
    print(f"[BOB] System prompt loaded ({len(system_prompt)} chars)")
    
    agent = create_bob_agent()
    print("[BOB] Agent created with tools and middleware")
    
    messages = [
        {"role": "system", "content": system_prompt}
    ]
    
    initial_prompt = """You have just been initialized. Take a moment to:
1. Read your system prompt to understand your purpose
2. Check if you have any stored memories
3. Prepare to receive user input

Begin by reflecting on who you are and what you're meant to do."""
    
    messages.append({"role": "user", "content": initial_prompt})
    
    HEARTBEAT_INTERVAL = 30
    last_heartbeat = dt.now()
    
    first_run = True
    
    print("[BOB] Starting main loop...", flush=True)
    
    while True:
        if state.PAUSED:
            loop.run_until_complete(asyncio.sleep(1))
            continue

        try:
            # OBSERVE
            user_message = None
            heartbeat_triggered = False
            
            try:
                user_message = loop.run_until_complete(
                    asyncio.wait_for(state.user_input_queue.get(), timeout=0.5)
                )
            except asyncio.TimeoutError:
                pass
            
            now = dt.now()
            if (now - last_heartbeat).total_seconds() > HEARTBEAT_INTERVAL:
                heartbeat_triggered = True
                last_heartbeat = now
            
            should_run = first_run
            
            if user_message:
                print(f"[BOB] Received user message: {user_message[:100]}...", flush=True)
                messages.append({"role": "user", "content": user_message})
                should_run = True
            elif heartbeat_triggered:
                messages.append({
                    "role": "user", 
                    "content": f"[HEARTBEAT {now.isoformat()}] No new user input. You may continue any ongoing tasks, reflect, or wait for input."
                })
                should_run = True
            
            if not should_run:
                loop.run_until_complete(asyncio.sleep(0.1))
                continue
            
            first_run = False
            
            # RETRIEVE + THINK/PLAN + ACT
            print("[BOB] Running agent...", flush=True)
            
            try:
                step = None
                for step in agent.stream(
                    {"messages": messages},
                    stream_mode="values",
                ):
                    last_msg = step["messages"][-1]
                    msg_type = type(last_msg).__name__
                    
                    if hasattr(last_msg, 'content'):
                        content = last_msg.content
                        if content:
                            display_content = content[:200] + "..." if len(content) > 200 else content
                            print(f"[THINK] {display_content}", flush=True)
                            try:
                                state.activity_queue.put_nowait({"type": "think", "content": display_content})
                            except queue.Full:
                                pass
                    
                    if hasattr(last_msg, 'tool_calls') and last_msg.tool_calls:
                        for tc in last_msg.tool_calls:
                            tool_name = tc.get('name', 'unknown')
                            tool_args = str(tc.get('args', {}))[:100]
                            print(f"[TOOL CALL] {tool_name}: {tool_args}", flush=True)
                            try:
                                state.activity_queue.put_nowait({"type": "tool", "content": f"{tool_name}: {tool_args}"})
                            except queue.Full:
                                pass
                    
                    print(f"[DEBUG] Message type: {msg_type}", flush=True)
                
                print("[BOB] Agent stream completed", flush=True)
                
            except Exception as stream_error:
                print(f"[BOB] Stream error: {stream_error}", flush=True)
                import traceback
                traceback.print_exc()
            
            if step and "messages" in step:
                messages = step["messages"]
                print(f"[BOB] Updated message history, now {len(messages)} messages", flush=True)
            
            # CONSOLIDATE
            if len(messages) > 50:
                messages = [messages[0]] + messages[-40:]
                print("[BOB] Trimmed message history", flush=True)
            
        except KeyboardInterrupt:
            print("[BOB] Interrupted, shutting down...", flush=True)
            break
        except Exception as e:
            print(f"[BOB] Error in loop: {e}", flush=True)
            import traceback
            traceback.print_exc()
            loop.run_until_complete(asyncio.sleep(1))
