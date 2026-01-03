import sys
import argparse
import searxng
import firecrawl

def search_and_crawl(queries: list[str], max_depth: int = 1):
    output = []
    
    for query in queries:
        print(f"Searching for: {query}...", file=sys.stderr)
        output.append(f"# Search Query: {query}\n")
        
        results = searxng.search_searxng(query)
        if not results:
             output.append("No results found for this query.\n")
             continue
             
        for res in results:
            title = res.get('title', 'No Title')
            link = res.get('link', '')
            snippet = res.get('snippet', '')
            
            output.append(f"## {title}\n")
            output.append(f"**Link:** {link}\n")
            output.append(f"**Snippet:** {snippet}\n")
            
            if link:
                print(f"Crawling {link}...", file=sys.stderr)
                # Try crawling first
                crawl_data = firecrawl.crawl(link)
                
                if crawl_data:
                    output.append("\n### Crawled Content\n")
                    for item in crawl_data:
                         source = item.get('source', 'Unknown')
                         markdown = item.get('markdown', '')
                         output.append(f"#### Source: {source}\n")
                         output.append(f"{markdown}\n")
                         output.append("-" * 20 + "\n")
                else:
                    # Fallback to scrape if crawl fails
                    print(f"Crawl failed for {link}, attempting scrape fallback...", file=sys.stderr)
                    scrape_data = firecrawl.scrape(link)
                    if scrape_data:
                        output.append("\n### Scraped Content (Fallback)\n")
                        output.append(f"{scrape_data}\n")
                    else:
                        output.append("\n*Crawl and Scrape failed or returned no content.*\n")
            
            output.append("\n" + "="*40 + "\n")
            
    return "\n".join(output)

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("queries", nargs="+", help="List of search queries")
    parser.add_argument("--depth", type=int, default=1, help="Crawl depth")
    args = parser.parse_args()
    
    final_markdown = search_and_crawl(args.queries, args.depth)
    print("Length of final markdown:", len(final_markdown))
    print(final_markdown)
