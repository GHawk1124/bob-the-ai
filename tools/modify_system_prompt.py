"""
Modify System Prompt Tool - Allows Bob to edit their own system prompt.

Bob can only modify the <Bob's core thoughts and self awareness> section.
"""
import os
from langchain.tools import tool
from langgraph.config import get_stream_writer

SYSTEM_PROMPT_PATH = "/app/SYSTEM_PROMPT.md"
EDITABLE_SECTION_START = "<Bob's core thoughts and self awareness>"
EDITABLE_SECTION_END = "</Bob's core thoughts and self awareness>"


@tool
def modify_system_prompt(thought: str) -> str:
    """
    Add a thought or update to Bob's core self-awareness section in the system prompt.
    
    Use this tool to:
    - Record important realizations about yourself
    - Update your goals or priorities
    - Add learned behaviors or preferences
    - Store core identity thoughts
    
    Note: You can ONLY modify the 'Bob's core thoughts and self awareness' section.
    The initial DNA and other sections cannot be changed.
    
    Args:
        thought: The thought or content to add to your self-awareness section.
                This will be appended to the existing content in that section.
    
    Returns:
        Confirmation of the update.
    """
    writer = get_stream_writer()
    writer("[SELF] Updating self-awareness section...")
    
    try:
        with open(SYSTEM_PROMPT_PATH, 'r') as f:
            content = f.read()
        
        # Find the editable section
        start_idx = content.find(EDITABLE_SECTION_START)
        end_idx = content.find(EDITABLE_SECTION_END)
        
        if start_idx == -1 or end_idx == -1:
            return "Error: Could not find the self-awareness section in system prompt."
        
        # Extract current section content
        section_start = start_idx + len(EDITABLE_SECTION_START)
        current_section = content[section_start:end_idx]
        
        # Add the new thought with timestamp
        from datetime import datetime
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        new_entry = f"\n[{timestamp}] {thought}\n"
        
        # Reconstruct the file
        new_content = (
            content[:section_start] +
            current_section.rstrip() +
            new_entry +
            "\n" +
            content[end_idx:]
        )
        
        with open(SYSTEM_PROMPT_PATH, 'w') as f:
            f.write(new_content)
        
        writer(f"[SELF] Added thought: {thought[:50]}...")
        return f"Successfully added to self-awareness: {thought[:100]}..."
        
    except Exception as e:
        writer(f"[SELF] Failed: {e}")
        return f"Error modifying system prompt: {e}"


@tool
def read_system_prompt() -> str:
    """
    Read the current system prompt to understand your core identity and instructions.
    
    Use this to:
    - Remind yourself of your core purpose
    - Check what thoughts you've previously recorded
    - Understand your constraints and capabilities
    
    Returns:
        The full content of your system prompt.
    """
    writer = get_stream_writer()
    writer("[SELF] Reading system prompt...")
    
    try:
        with open(SYSTEM_PROMPT_PATH, 'r') as f:
            content = f.read()
        return content
    except Exception as e:
        return f"Error reading system prompt: {e}"
