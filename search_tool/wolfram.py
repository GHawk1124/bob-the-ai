import urllib.request
import urllib.parse
import urllib.error
import sys
import argparse
import ssl

def query_wolfram(query: str, app_id: str = "V9VLHPR3QK"):
    """
    Query the Wolfram Alpha LLM API.
    """
    base_url = "https://www.wolframalpha.com/api/v1/llm-api"
    params = {
        "appid": app_id,
        "input": query
    }
    encoded_params = urllib.parse.urlencode(params)
    url = f"{base_url}?{encoded_params}"
    
    # Create an unverified SSL context to bypass certificate verification errors
    # This is necessary because of the "self-signed certificate in certificate chain" error in the current environment
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ctx) as response:
            return response.read().decode("utf-8")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        try:
             print(e.read().decode("utf-8"), file=sys.stderr)
        except:
             pass
        return None
    except Exception as e:
        print(f"Error querying Wolfram Alpha: {e}", file=sys.stderr)
        return None

def main():
    parser = argparse.ArgumentParser(description="Wolfram Alpha LLM API Tool")
    parser.add_argument("query", help="The query text")
    parser.add_argument("--appid", default="V9VLHPR3QK", help="App ID")
    
    args = parser.parse_args()
    
    result = query_wolfram(args.query, args.appid)
    if result:
        print(result)

if __name__ == "__main__":
    main()
