import asyncio
import queue
from typing import List, Dict, Any

# Queues for async communication
message_queue: asyncio.Queue = asyncio.Queue(maxsize=100)  # Bob -> Users (say tool)
user_input_queue: asyncio.Queue = asyncio.Queue(maxsize=10)  # Users -> Bob (messages)
response_queue: asyncio.Queue = asyncio.Queue(maxsize=10)  # Users -> Bob (input responses)
activity_queue: queue.Queue = queue.Queue(maxsize=200)  # Agent activity (thread-safe)

# Control flags
PAUSED = False

# Global context window (can be updated)
CONTEXT_WINDOW = 128000

# Pending messages for users to consume
outgoing_messages: List[Dict[str, Any]] = []
