"""
Request User Input Tool - Human-in-the-loop for getting user responses.
"""
import asyncio
from typing import Optional
from langchain.tools import tool
from langgraph.config import get_stream_writer

# Response queue - populated when user responds
_response_queue: Optional[asyncio.Queue] = None
_pending_request: Optional[str] = None


def set_response_queue(queue: asyncio.Queue):
    """Set the response queue from the HTTP server."""
    global _response_queue
    _response_queue = queue


def get_pending_request() -> Optional[str]:
    """Get the pending request ID if any."""
    return _pending_request


def clear_pending_request():
    """Clear any pending request."""
    global _pending_request
    _pending_request = None


@tool
def request_user_input(question: str, timeout_seconds: int = 300) -> str:
    """
    Ask the connected user(s) for input and wait for their response.
    
    Use this tool when you need:
    - Clarification on an ambiguous request
    - User confirmation before taking an action
    - User decision between multiple options
    - Any information only the user can provide
    
    This tool will block until the user responds or the timeout is reached.
    
    Args:
        question: The question to ask the user. Be clear and specific.
        timeout_seconds: How long to wait for a response (default 5 minutes).
    
    Returns:
        The user's response, or a timeout message.
    """
    global _pending_request
    writer = get_stream_writer()
    
    # Import here to avoid circular import
    from tools.say import get_message_queue
    
    writer(f"[INPUT] Requesting user input: {question}")
    
    # Send the question via the say mechanism
    msg_queue = get_message_queue()
    if msg_queue is not None:
        try:
            request_id = f"req_{asyncio.get_event_loop().time()}"
            _pending_request = request_id
            msg_queue.put_nowait({
                "type": "input_request",
                "content": question,
                "request_id": request_id
            })
        except asyncio.QueueFull:
            return "Could not send question - message queue full."
    else:
        return "No users connected to receive the question."
    
    # Wait for response
    if _response_queue is not None:
        try:
            response = asyncio.get_event_loop().run_until_complete(
                asyncio.wait_for(_response_queue.get(), timeout=timeout_seconds)
            )
            clear_pending_request()
            writer(f"[INPUT] Received response: {response[:100]}...")
            return response
        except asyncio.TimeoutError:
            clear_pending_request()
            writer("[INPUT] Timeout waiting for user response")
            return f"Timeout: No response received within {timeout_seconds} seconds."
    else:
        return "Response queue not initialized. Cannot receive user input."
