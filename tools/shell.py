"""
Shell Execution Tool - Execute arbitrary shell commands in Bob's container.
"""
import subprocess
from langchain.tools import tool
from langgraph.config import get_stream_writer


@tool
def execute_shell(command: str, timeout_seconds: int = 60) -> str:
    """
    Execute a shell command in Bob's Docker container.
    
    Use this tool to:
    - Install packages with apt-get or pip
    - Run scripts or programs
    - Manage files and directories
    - Check system status
    - Run any arbitrary command
    
    CAUTION: Commands are executed with full privileges in the container.
    Be careful with destructive commands.
    
    Args:
        command: The shell command to execute
        timeout_seconds: Maximum time to wait for command completion (default 60s)
    
    Returns:
        The command output (stdout and stderr combined), or error message.
    """
    writer = get_stream_writer()
    writer(f"[SHELL] Executing: {command}")
    
    try:
        result = subprocess.run(
            command,
            shell=True,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            cwd="/app"
        )
        
        output = ""
        if result.stdout:
            output += result.stdout
        if result.stderr:
            if output:
                output += "\n--- STDERR ---\n"
            output += result.stderr
        
        if result.returncode != 0:
            output += f"\n[Exit code: {result.returncode}]"
        
        writer(f"[SHELL] Completed with exit code {result.returncode}")
        
        # Truncate very long output
        if len(output) > 5000:
            output = output[:5000] + "\n...[output truncated at 5000 chars]"
        
        return output if output else "(no output)"
        
    except subprocess.TimeoutExpired:
        writer(f"[SHELL] Timeout after {timeout_seconds}s")
        return f"Command timed out after {timeout_seconds} seconds"
    except Exception as e:
        writer(f"[SHELL] Error: {e}")
        return f"Error executing command: {e}"
