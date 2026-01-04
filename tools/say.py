"""
Say Tool - Bob's only way to communicate with connected users.

The LLM output is Bob's "internal thinking". The say tool is used to provide
the user with only the most crucial information or what they ask for.
"""
import asyncio
from typing import Optional
from langchain.tools import tool
from langgraph.config import get_stream_writer

# Global message queue - will be populated by the HTTP server
_message_queue: Optional[asyncio.Queue] = None


def set_message_queue(queue: asyncio.Queue):
    """Set the message queue from the HTTP server."""
    global _message_queue
    _message_queue = queue


def get_message_queue() -> Optional[asyncio.Queue]:
    """Get the current message queue."""
    return _message_queue


@tool
def say(message: str) -> str:
    """
    Say something to connected users. This is Bob's ONLY way to communicate externally.
    
    Use this tool when you want to:
    - Respond to the user's question or request
    - Share important findings or results
    - Ask the user for clarification
    - Provide updates on task progress
    
    The LLM's normal output is Bob's "internal thinking" - users don't see it.
    Only content passed through this tool reaches the user.
    
    Args:
        message: The message to send to connected users. Keep it concise and relevant.
                 Avoid typical LLM markdown fluff. Be direct and helpful.
    
    Returns:
        Confirmation that the message was sent.
    """
    writer = get_stream_writer()
    
    # Stream the message for internal logging
    writer(f"[SAY] {message}")
    
    # Queue the message for connected users
    queue = get_message_queue()
    if queue is not None:
        try:
            queue.put_nowait({"type": "say", "content": message})
        except asyncio.QueueFull:
            return "Message queue is full. Some users may not receive this message."
    
    return f"Message sent to connected users: {message[:50]}..."
