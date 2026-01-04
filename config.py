import os
import urllib.request
import ssl
import json

OPENAI_BASE_URL = os.environ.get("OPENAI_BASE_URL", "http://spark-bcce.hlab:8080/api")
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "not-needed")
MODEL_NAME = os.environ.get("MODEL_NAME", "gpt-oss:120b")
SYSTEM_PROMPT_PATH = "/app/SYSTEM_PROMPT.md"
HTTP_PORT = 8000

def fetch_model_context_window() -> int:
    """Fetch the context window for the configured model from the API."""
    print(f"[BOB] Fetching context window for {MODEL_NAME}...")
    try:
        base = OPENAI_BASE_URL.rstrip("/")
        url = f"{base}/models"
        
        req = urllib.request.Request(url)
        if OPENAI_API_KEY and OPENAI_API_KEY != "not-needed":
            req.add_header("Authorization", f"Bearer {OPENAI_API_KEY}")
        
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        
        with urllib.request.urlopen(req, context=ctx, timeout=5) as resp:
            data = json.loads(resp.read().decode())
            
        for model in data.get("data", []):
            if model.get("id") == MODEL_NAME:
                info = model.get("info", {})
                params = info.get("params", {})
                ctx_len = info.get("context_length") or params.get("num_ctx") or model.get("context_window")
                
                if ctx_len:
                    print(f"[BOB] Found context window: {ctx_len}")
                    return int(ctx_len)
                    
        print(f"[BOB] Model {MODEL_NAME} not found in API response, using default.")
        return 128000
    except Exception as e:
        print(f"[BOB] Error fetching model context: {e}")
        return 128000
