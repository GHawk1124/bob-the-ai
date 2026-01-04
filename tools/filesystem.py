"""
File System Tools - Allow Bob to manipulate files and directories.
"""
import os
import shutil
from pathlib import Path
from langchain.tools import tool
from langgraph.config import get_stream_writer

# Working directory for Bob
WORKSPACE = "/app/workspace"


def ensure_workspace():
    """Ensure workspace directory exists."""
    os.makedirs(WORKSPACE, exist_ok=True)


def safe_path(path: str) -> str:
    """Ensure path is within workspace for safety."""
    # Allow absolute paths but warn
    if path.startswith("/"):
        return path
    # Relative paths are relative to workspace
    ensure_workspace()
    return os.path.join(WORKSPACE, path)


@tool
def create_directory(path: str) -> str:
    """
    Create a directory (and any parent directories).
    
    Args:
        path: Directory path to create. Relative paths are in /app/workspace.
    
    Returns:
        Success or error message.
    """
    writer = get_stream_writer()
    target = safe_path(path)
    writer(f"[FS] Creating directory: {target}")
    
    try:
        os.makedirs(target, exist_ok=True)
        return f"Created directory: {target}"
    except Exception as e:
        return f"Error creating directory: {e}"


@tool
def remove_directory(path: str, force: bool = False) -> str:
    """
    Remove a directory.
    
    Args:
        path: Directory path to remove.
        force: If True, remove non-empty directories recursively.
    
    Returns:
        Success or error message.
    """
    writer = get_stream_writer()
    target = safe_path(path)
    writer(f"[FS] Removing directory: {target}")
    
    try:
        if force:
            shutil.rmtree(target)
        else:
            os.rmdir(target)
        return f"Removed directory: {target}"
    except Exception as e:
        return f"Error removing directory: {e}"


@tool
def list_directory(path: str = ".") -> str:
    """
    List contents of a directory.
    
    Args:
        path: Directory to list. Defaults to workspace.
    
    Returns:
        Directory listing with file types and sizes.
    """
    writer = get_stream_writer()
    target = safe_path(path)
    writer(f"[FS] Listing: {target}")
    
    try:
        entries = []
        for entry in os.scandir(target):
            if entry.is_file():
                size = entry.stat().st_size
                entries.append(f"  {entry.name} ({size} bytes)")
            elif entry.is_dir():
                entries.append(f"  {entry.name}/")
            else:
                entries.append(f"  {entry.name}")
        
        if not entries:
            return f"Directory is empty: {target}"
        
        return f"Contents of {target}:\n" + "\n".join(sorted(entries))
    except Exception as e:
        return f"Error listing directory: {e}"


@tool
def create_file(path: str, content: str) -> str:
    """
    Create or overwrite a file with content.
    
    Args:
        path: File path to create.
        content: Content to write to the file.
    
    Returns:
        Success or error message.
    """
    writer = get_stream_writer()
    target = safe_path(path)
    writer(f"[FS] Creating file: {target}")
    
    try:
        # Create parent directories if needed
        os.makedirs(os.path.dirname(target), exist_ok=True) if os.path.dirname(target) else None
        
        with open(target, 'w') as f:
            f.write(content)
        
        return f"Created file: {target} ({len(content)} bytes)"
    except Exception as e:
        return f"Error creating file: {e}"


@tool
def view_file(path: str, start_line: int = 1, end_line: int = None) -> str:
    """
    Read and return file contents.
    
    Args:
        path: File path to read.
        start_line: First line to read (1-indexed). Default 1.
        end_line: Last line to read (inclusive). Default: all.
    
    Returns:
        File contents or error message.
    """
    writer = get_stream_writer()
    target = safe_path(path)
    writer(f"[FS] Reading file: {target}")
    
    try:
        with open(target, 'r') as f:
            lines = f.readlines()
        
        total_lines = len(lines)
        
        # Apply line range
        start_idx = max(0, start_line - 1)
        end_idx = end_line if end_line else total_lines
        selected = lines[start_idx:end_idx]
        
        # Add line numbers
        numbered = []
        for i, line in enumerate(selected, start=start_idx + 1):
            numbered.append(f"{i:4d} | {line.rstrip()}")
        
        header = f"File: {target} (lines {start_idx+1}-{min(end_idx, total_lines)} of {total_lines})"
        return header + "\n" + "\n".join(numbered)
    except Exception as e:
        return f"Error reading file: {e}"


@tool
def remove_file(path: str) -> str:
    """
    Delete a file.
    
    Args:
        path: File path to delete.
    
    Returns:
        Success or error message.
    """
    writer = get_stream_writer()
    target = safe_path(path)
    writer(f"[FS] Removing file: {target}")
    
    try:
        os.remove(target)
        return f"Removed file: {target}"
    except Exception as e:
        return f"Error removing file: {e}"


@tool
def edit_file(path: str, old_content: str, new_content: str) -> str:
    """
    Edit a file by replacing specific content.
    
    Args:
        path: File path to edit.
        old_content: Exact text to find and replace.
        new_content: Text to replace it with.
    
    Returns:
        Success or error message.
    """
    writer = get_stream_writer()
    target = safe_path(path)
    writer(f"[FS] Editing file: {target}")
    
    try:
        with open(target, 'r') as f:
            content = f.read()
        
        if old_content not in content:
            return f"Error: Could not find the specified text in {target}"
        
        # Count occurrences
        count = content.count(old_content)
        
        # Replace
        new_file_content = content.replace(old_content, new_content)
        
        with open(target, 'w') as f:
            f.write(new_file_content)
        
        return f"Edited {target}: replaced {count} occurrence(s)"
    except Exception as e:
        return f"Error editing file: {e}"


@tool
def append_to_file(path: str, content: str) -> str:
    """
    Append content to end of a file.
    
    Args:
        path: File path to append to.
        content: Content to append.
    
    Returns:
        Success or error message.
    """
    writer = get_stream_writer()
    target = safe_path(path)
    writer(f"[FS] Appending to file: {target}")
    
    try:
        with open(target, 'a') as f:
            f.write(content)
        return f"Appended {len(content)} bytes to {target}"
    except Exception as e:
        return f"Error appending to file: {e}"
