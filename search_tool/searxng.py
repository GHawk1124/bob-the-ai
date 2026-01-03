import urllib.request
import urllib.parse
import json
import sys

SEARXNG_URL = "http://localhost:9005"

def search_searxng(query: str, num_results: int = 5):
    """
    Search SearXNG for the given query.
    Returns a list of dictionaries with 'title', 'link', 'snippet'.
    """
    params = {
        "q": query,
        "format": "json",
        "engines": "google,bing,duckduckgo,wikipedia", # Explicitly asking for general engines might help, or let searxng decide
    }
    encoded_params = urllib.parse.urlencode(params)
    url = f"{SEARXNG_URL}/search?{encoded_params}"
    
    try:
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req) as response:
            data = json.loads(response.read().decode("utf-8"))
            
            results = []
            if "results" in data:
                for res in data["results"][:num_results]:
                    results.append({
                        "title": res.get("title"),
                        "link": res.get("url"),
                        "snippet": res.get("content", "")
                    })
            return results
    except Exception as e:
        print(f"Error searching SearXNG: {e}", file=sys.stderr)
        return []

if __name__ == "__main__":
    # Test
    if len(sys.argv) > 1:
        q = sys.argv[1]
    else:
        q = "rust programming"
    print(json.dumps(search_searxng(q), indent=2))
