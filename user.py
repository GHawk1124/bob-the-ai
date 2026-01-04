#!/usr/bin/env python3
"""
Bob TUI - Textual-based terminal UI for interacting with Bob.

Layout:
- Left panel (70%): MarkdownViewer showing AI context
- Right panel (30%): Log on top, Input at bottom
- Header: Context usage
"""
import asyncio
import json
import io
import threading
from urllib.request import Request, urlopen
from urllib.error import URLError
import textwrap

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Input, Log, MarkdownViewer, Static
from textual.binding import Binding

# Configuration
BOB_HOST = "localhost"
BOB_PORT = 8000


class ContextHeader(Static):
    """Header showing context usage."""
    
    def __init__(self, **kwargs):
        super().__init__("Context: 0 / ? (0%)", **kwargs)
        self.token_count = 0
        self.max_tokens = 128000  # Default to 128k
        self.model_name = "Unknown"
    
    def set_config(self, max_tokens: int, model_name: str):
        self.max_tokens = max_tokens
        self.model_name = model_name
        self.update_context(self.token_count)

    def update_context(self, count: int):
        self.token_count = count
        pct = min(100, int(100 * count / self.max_tokens)) if self.max_tokens else 0
        self.update(f"[{self.model_name}] Context: {count} / {self.max_tokens} tokens ({pct}%)")


class BobTUI(App):
    """Textual app for Bob interaction."""
    
    CSS = """
    Screen {
        layout: horizontal;
    }
    
    #left-panel {
        width: 70%;
        height: 100%;
        border: solid green;
    }
    
    #right-panel {
        width: 30%;
        height: 100%;
    }
    
    #log-panel {
        height: 1fr;
        border: solid cyan;
    }
    
    #input-container {
        height: auto;
        border: solid blue;
        padding: 0 1;
    }
    
    #context-header {
        dock: top;
        height: 1;
        background: $primary-background;
        color: $text;
        text-align: center;
    }
    
    MarkdownViewer {
        height: 100%;
    }
    
    Log {
        height: 100%;
        text-wrap: wrap;
    }
    
    Input {
        width: 100%;
    }
    """
    
    BINDINGS = [
        Binding("ctrl+c", "quit", "Quit"),
        Binding("ctrl+q", "quit", "Quit"),
    ]
    
    def __init__(self):
        super().__init__()
        self.base_url = f"http://{BOB_HOST}:{BOB_PORT}"
        self.context_md = "# Bob AI Context\n\nConnecting..."
        self.stop_event = threading.Event()
    
    def compose(self) -> ComposeResult:
        yield Header()
        
        with Horizontal():
            # Left panel - Markdown context viewer
            with Vertical(id="left-panel"):
                yield ContextHeader(id="context-header")
                yield MarkdownViewer(self.context_md, show_table_of_contents=False, id="context-viewer")
            
            # Right panel - Log and Input
            with Vertical(id="right-panel"):
                with Vertical(id="log-panel"):
                    yield Log(id="log")
                with Vertical(id="input-container"):
                    yield Input(placeholder="Type message and press Enter...", id="user-input")
        
        yield Footer()
    
    async def on_mount(self):
        """Start streaming when app mounts."""
        self.log_widget = self.query_one("#log", Log)
        self.context_viewer = self.query_one("#context-viewer", MarkdownViewer)
        self.context_header = self.query_one("#context-header", ContextHeader)
        self.user_input = self.query_one("#user-input", Input)
        
        # Check health
        if not self.check_health():
            self.write_log("[ERROR] Cannot connect to Bob!")
            self.write_log(f"Make sure Bob is running at {self.base_url}")
            return
        
        self.write_log("[OK] Connected to Bob!")
        
        # Set initial context
        self.context_md = "# Bob AI Context\n\n*Connected and streaming...*\n"
        await self.refresh_context()
        
        # Start streaming in background
        self.stream_task = asyncio.create_task(self.stream_loop())
    
    async def refresh_context(self):
        """Refresh the markdown viewer with current context."""
        try:
            await self.context_viewer.document.update(self.context_md)
            self.context_viewer.scroll_end(animate=False)
        except Exception:
            pass  # Ignore update errors
    
    def check_health(self) -> bool:
        """Check if Bob is healthy."""
        try:
            req = Request(f"{self.base_url}/health")
            with urlopen(req, timeout=5) as resp:
                return json.loads(resp.read().decode()).get("status") == "ok"
        except:
            return False
    
    async def on_input_submitted(self, event: Input.Submitted):
        """Handle user input submission."""
        message = event.value.strip()
        if not message:
            return
        
        # Clear input
        self.user_input.value = ""
        
        # Check for slash commands
        if message.startswith("/"):
            if message == "/pause":
                self.write_log("[CMD] Pausing Bob...")
                await self.send_control("pause")
                return
            elif message == "/start":
                self.write_log("[CMD] Resuming Bob...")
                await self.send_control("resume")
                return
            elif message.startswith("/command "):
                cmd = message[9:].strip()
                self.write_log(f"[CMD] Shell: {cmd}")
                await self.send_shell_command(cmd)
                return
            else:
                self.write_log(f"[ERROR] Unknown command: {message}")
                return
        
        # Log it
        self.write_log(f"[YOU] {message}")
        
        # Send to Bob
        await self.send_message(message)
    
    async def send_control(self, action: str):
        """Send control action to Bob."""
        try:
            req = Request(
                f"{self.base_url}/control",
                data=json.dumps({"action": action}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: urlopen(req, timeout=5))
            data = json.loads(resp.read().decode())
            self.write_log(f"[CTRL] {data.get('status', 'ok')}")
        except Exception as e:
            self.write_log(f"[ERROR] Control failed: {e}")

    async def send_shell_command(self, command: str):
        """Send shell command to Bob."""
        try:
            req = Request(
                f"{self.base_url}/shell",
                data=json.dumps({"command": command}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            loop = asyncio.get_event_loop()
            resp = await loop.run_in_executor(None, lambda: urlopen(req, timeout=30))
            data = json.loads(resp.read().decode())
            if data.get("status") == "success":
                output = data.get("output", "")
                self.write_log(f"[SHELL] Output:\n{output}")
            else:
                self.write_log(f"[SHELL] Error: {data.get('output')}")
        except Exception as e:
            self.write_log(f"[ERROR] Shell command failed: {e}")
    
    def write_log(self, message: str):
        """Write a message to the log with wrapping."""
        # Estimate width (conservative)
        width = 40
        if self.log_widget.size.width:
             # Subtract padding/border
             width = max(20, self.log_widget.size.width - 4)
        
        # indent subsequent lines
        wrapped = textwrap.fill(message, width=width, subsequent_indent="  ")
        self.log_widget.write(wrapped + "\n")

    async def send_message(self, content: str):
        """Send message to Bob."""
        try:
            req = Request(
                f"{self.base_url}/message",
                data=json.dumps({"content": content}).encode(),
                headers={"Content-Type": "application/json"},
                method="POST"
            )
            # Run in thread to not block
            loop = asyncio.get_event_loop()
            await loop.run_in_executor(None, lambda: urlopen(req, timeout=10))
            self.write_log("[OK] Message sent")
        except Exception as e:
            self.write_log(f"[ERROR] Send failed: {e}")
    
    async def stream_loop(self):
        """Stream SSE events from Bob."""
        url = f"{self.base_url}/stream"
        
        while not self.stop_event.is_set():
            try:
                req = Request(url)
                
                # Run blocking urlopen in executor
                loop = asyncio.get_event_loop()
                resp = await loop.run_in_executor(None, lambda: urlopen(req))
                
                reader = io.TextIOWrapper(resp, encoding='utf-8', errors='replace')
                buffer = ""
                
                while not self.stop_event.is_set():
                    # Read chunk in executor
                    chunk = await loop.run_in_executor(None, lambda: reader.read(128))
                    if not chunk:
                        break
                    
                    buffer += chunk
                    
                    while "\n\n" in buffer:
                        event_str, buffer = buffer.split("\n\n", 1)
                        await self.handle_sse_event(event_str)
                
            except Exception as e:
                if not self.stop_event.is_set():
                    self.write_log(f"[STREAM] Error: {e}")
                    await asyncio.sleep(2)
    
    async def handle_sse_event(self, event_str: str):
        """Handle an SSE event."""
        event_type = ""
        event_data = ""
        
        for line in event_str.split("\n"):
            if line.startswith("event:"):
                event_type = line[6:].strip()
            elif line.startswith("data:"):
                event_data = line[5:].strip()
        
        if event_type == "heartbeat":
            return
        
        if event_type == "say":
            self.write_log(f"[BOB] {event_data}")
            await self.update_context(event_data, "SAY")
        elif event_type == "think":
            # self.write_log(f"[THINK] {event_data[:50]}")
            await self.update_context(event_data, "THINK")
        elif event_type == "tool":
            # self.write_log(f"[TOOL] {event_data[:50]}")
            await self.update_context(event_data, "TOOL")
        elif event_type == "context":
            # Full context update
            self.context_md = event_data
            await self.context_viewer.document.update(event_data)
        elif event_type == "config":
            try:
                config = json.loads(event_data)
                self.context_header.set_config(
                    config.get("max_tokens", 128000),
                    config.get("model_name", "Unknown")
                )
            except:
                pass
        elif event_data:
            pass
            # self.write_log(f"[{event_type.upper()[:5]}] {event_data[:50]}")
    
    async def update_context(self, text: str, event_type: str = "THINK"):
        """Update context display with FULL text (no truncation)."""
        import time
        ts = time.strftime("%H:%M:%S")
        
        # Show FULL content - no truncation
        self.context_md += f"\n\n---\n### {ts} [{event_type}]\n\n{text}\n"
        
        # Estimate tokens (rough: 4 chars per token)
        tokens = len(self.context_md) // 4
        self.context_header.update_context(tokens)
        
        # Refresh the markdown viewer
        await self.refresh_context()
    
    def action_quit(self):
        """Quit the app."""
        self.stop_event.set()
        self.exit()


def main():
    app = BobTUI()
    app.run()


if __name__ == "__main__":
    main()
