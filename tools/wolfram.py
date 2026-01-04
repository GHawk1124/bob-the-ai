"""
Wolfram Alpha Tool - Query Wolfram Alpha for calculations, data, and facts.
"""
import urllib.request
import urllib.parse
import ssl
from langchain.tools import tool
from langgraph.config import get_stream_writer

# Wolfram AppID
WOLFRAM_APP_ID = "V9VLHPR3QK"


def _query_wolfram_api(query: str, app_id: str = WOLFRAM_APP_ID) -> str | None:
    """Query the Wolfram Alpha LLM API."""
    base_url = "https://www.wolframalpha.com/api/v1/llm-api"
    params = {
        "appid": app_id,
        "input": query
    }
    encoded_params = urllib.parse.urlencode(params)
    url = f"{base_url}?{encoded_params}"
    
    # Create unverified SSL context (needed for some environments)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ctx, timeout=30) as response:
            return response.read().decode("utf-8")
    except Exception as e:
        return f"Wolfram Alpha error: {e}"


@tool
def wolfram_query(query: str) -> str:
    """
    Query Wolfram Alpha for mathematical calculations, unit conversions,
    scientific data, and factual information.
    
    Use this for:
    - Math calculations and equations (solve x^2 + 2x - 3 = 0)
    - Unit conversions (convert 5 miles to km)
    - Scientific constants and formulas
    - Factual data (population of France, distance to moon)
    - Date/time calculations
    - Weather data
    
    Args:
        query: Natural language query or math expression
    
    Returns:
        Wolfram Alpha's response with calculations/data.
    """
    writer = get_stream_writer()
    writer(f"[WOLFRAM] Querying: {query}")
    
    result = _query_wolfram_api(query)
    
    if result:
        writer(f"[WOLFRAM] Got response ({len(result)} chars)")
        return result
    else:
        return "Wolfram Alpha query failed. Try rephrasing."
