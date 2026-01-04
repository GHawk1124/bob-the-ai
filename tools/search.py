"""
Web Search Tool - Wraps existing search_tool for LangChain integration.
Uses SearXNG for search and Firecrawl for crawling/scraping.
"""
from langchain.tools import tool
from langgraph.config import get_stream_writer
import sys
import os

# Add parent directory to path for search_tool imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search_tool import searxng, firecrawl


@tool
def web_search(query: str, crawl_results: bool = False) -> str:
    """
    Search the web using SearXNG and optionally crawl the top results.
    
    Use this tool when you need to:
    - Find current information about a topic
    - Research something you don't know
    - Verify facts with up-to-date sources
    - Find news or recent events
    
    Args:
        query: The search query string
        crawl_results: If True, also crawl/scrape the top result pages for full content.
                      This is slower but provides more detailed information.
    
    Returns:
        Search results as formatted text. If crawl_results is True, includes full page content.
    """
    writer = get_stream_writer()
    writer(f"[SEARCH] Searching for: {query}")
    
    results = searxng.search_searxng(query, num_results=5)
    
    if not results:
        writer("[SEARCH] No results found")
        return "No search results found for this query."
    
    output = []
    for i, res in enumerate(results, 1):
        title = res.get('title', 'No Title')
        link = res.get('link', '')
        snippet = res.get('snippet', '')
        
        output.append(f"## Result {i}: {title}")
        output.append(f"**URL:** {link}")
        output.append(f"**Summary:** {snippet}")
        
        if crawl_results and link:
            writer(f"[SEARCH] Crawling: {link}")
            content = firecrawl.scrape(link)
            if content:
                # Truncate to avoid token explosion
                if len(content) > 3000:
                    content = content[:3000] + "\n...[truncated]"
                output.append(f"\n### Full Content:\n{content}")
        
        output.append("")
    
    writer(f"[SEARCH] Found {len(results)} results")
    return "\n".join(output)


@tool  
def crawl_url(url: str) -> str:
    """
    Crawl a specific URL and extract its content as markdown.
    
    Use this when you have a specific URL you want to read in full.
    
    Args:
        url: The URL to crawl
        
    Returns:
        The page content as markdown, or an error message if crawling failed.
    """
    writer = get_stream_writer()
    writer(f"[CRAWL] Fetching: {url}")
    
    content = firecrawl.scrape(url)
    
    if content:
        writer(f"[CRAWL] Successfully fetched {len(content)} characters")
        # Truncate very long content
        if len(content) > 10000:
            content = content[:10000] + "\n\n...[Content truncated at 10000 characters]"
        return content
    else:
        writer("[CRAWL] Failed to fetch content")
        return f"Failed to crawl URL: {url}"
