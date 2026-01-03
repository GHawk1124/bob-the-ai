import argparse
import urllib.request
import urllib.error
import time
import json
import sys

BASE_URL = "http://localhost:3003"
HEADERS = {
    "Content-Type": "application/json",
    "Authorization": "Bearer test",
    "User-Agent": "Firecrawl-CLI"
}

def make_request(url, method="GET", data=None):
    if data:
        data = json.dumps(data).encode("utf-8")
    
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}", file=sys.stderr)
        try:
            err_body = e.read().decode("utf-8")
            print(err_body, file=sys.stderr)
        except:
            pass
        return None
    except Exception as e:
        print(f"Request failed: {e}", file=sys.stderr)
        return None

def scrape(url):
    print(f"Scraping {url}...", file=sys.stderr)
    data = make_request(f"{BASE_URL}/v1/scrape", method="POST", data={"url": url})
    
    if data:
        if data.get('success') and 'data' in data:
            return data['data'].get('markdown', '')
        else:
            print("No markdown found or success=False", file=sys.stderr)
            print(json.dumps(data, indent=2), file=sys.stderr)
            return None
    return None

def crawl(url):
    print(f"Starting crawl for {url}...", file=sys.stderr)
    resp = make_request(f"{BASE_URL}/v1/crawl", method="POST", data={"url": url})
    
    if not resp:
        return None

    crawl_id = resp.get('id')
    if not crawl_id:
         print("No crawl ID returned", file=sys.stderr)
         return None

    print(f"Crawl ID: {crawl_id}", file=sys.stderr)
    
    while True:
        status_data = make_request(f"{BASE_URL}/v1/crawl/{crawl_id}")
        if not status_data:
            break
            
        status = status_data.get('status')
        
        c = status_data.get('completed', 0)
        t = status_data.get('total', 0)
        print(f"Status: {status} | Completed: {c}/{t}", file=sys.stderr)
        
        if status == 'completed':
            data = status_data.get('data', [])
            results = []
            for item in data:
                source = item.get('metadata', {}).get('sourceURL', 'Unknown URL')
                markdown = item.get('markdown', '')
                results.append({"source": source, "markdown": markdown})
            return results
        elif status == 'failed':
            print("Crawl failed", file=sys.stderr)
            break
        
        time.sleep(2)
    return None

def main():
    parser = argparse.ArgumentParser(description="Firecrawl local dumper")
    subparsers = parser.add_subparsers(dest="command", required=True)
    
    sp = subparsers.add_parser("scrape")
    sp.add_argument("url")
    
    cp = subparsers.add_parser("crawl")
    cp.add_argument("url")
    
    args = parser.parse_args()
    
    if args.command == "scrape":
        res = scrape(args.url)
        if res:
            print(res)
    elif args.command == "crawl":
        res = crawl(args.url)
        if res:
            for item in res:
                print(f"\n--- Source: {item['source']} ---")
                print(item['markdown'])
                print("-" * 40)

if __name__ == "__main__":
    main()
