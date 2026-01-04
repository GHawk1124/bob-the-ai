"""
GraphRAG Memory Tool - Stores and retrieves memories using graph traversal.
Uses InMemoryVectorStore with GraphRetriever for connected memory retrieval.
"""
import os
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from langchain.tools import tool
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from langgraph.config import get_stream_writer

try:
    from graph_retriever.strategies import Eager
    from langchain_graph_retriever import GraphRetriever
    GRAPH_RETRIEVER_AVAILABLE = True
except ImportError:
    GRAPH_RETRIEVER_AVAILABLE = False

# Persistence path for memories
MEMORY_PATH = "/app/data/memories.json"

# Global stores
_vector_store: Optional[InMemoryVectorStore] = None
_embeddings: Optional[OpenAIEmbeddings] = None


def get_embeddings() -> OpenAIEmbeddings:
    """Get or create embeddings instance."""
    global _embeddings
    if _embeddings is None:
        _embeddings = OpenAIEmbeddings(
            model=os.environ.get("EMBEDDING_MODEL", "embeddinggemma:300m"),
            openai_api_base=os.environ.get("OPENAI_BASE_URL", "http://spark-bcce.hlab:8080/api"),
            openai_api_key=os.environ.get("OPENAI_API_KEY", "not-needed"),
        )
    return _embeddings


def get_vector_store() -> InMemoryVectorStore:
    """Get or create vector store, loading from disk if available."""
    global _vector_store
    if _vector_store is None:
        _vector_store = InMemoryVectorStore(embedding=get_embeddings())
        # Try to load existing memories
        _load_memories()
    return _vector_store


def _load_memories():
    """Load memories from disk."""
    global _vector_store
    if os.path.exists(MEMORY_PATH):
        try:
            with open(MEMORY_PATH, 'r') as f:
                data = json.load(f)
            documents = [
                Document(
                    page_content=item['content'],
                    metadata=item.get('metadata', {}),
                    id=item.get('id')
                )
                for item in data
            ]
            if documents:
                _vector_store.add_documents(documents)
        except Exception as e:
            print(f"[MEMORY] Failed to load memories: {e}")


def _save_memories():
    """Save all memories to disk."""
    # Note: InMemoryVectorStore doesn't have a direct way to iterate all docs
    # We'll maintain a separate list for persistence
    pass  # TODO: Implement proper persistence


@tool
def store_memory(content: str, memory_type: str = "episodic", tags: str = "") -> str:
    """
    Store a memory in Bob's knowledge graph.
    
    Use this to remember:
    - Important facts or information learned
    - User preferences or instructions
    - Task outcomes and what was learned
    - Useful procedures or techniques
    
    Args:
        content: The memory content to store
        memory_type: Type of memory - 'episodic' (events/experiences), 
                     'semantic' (facts/knowledge), or 'procedural' (how-to)
        tags: Comma-separated tags for categorization and graph traversal
              (e.g., "user_preference,finance" or "procedure,coding,python")
    
    Returns:
        Confirmation that the memory was stored.
    """
    writer = get_stream_writer()
    writer(f"[MEMORY] Storing {memory_type} memory...")
    
    store = get_vector_store()
    
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    
    metadata = {
        "type": memory_type,
        "tags": ",".join(tag_list),
        "timestamp": datetime.now().isoformat(),
    }
    # Add each tag as its own metadata field for graph edges
    for tag in tag_list:
        metadata[f"tag_{tag}"] = tag
    
    doc = Document(
        page_content=content,
        metadata=metadata,
        id=f"memory_{datetime.now().timestamp()}"
    )
    
    store.add_documents([doc])
    
    writer(f"[MEMORY] Stored: {content[:50]}...")
    return f"Memory stored successfully with tags: {tags or 'none'}"


@tool
def retrieve_memory(query: str, k: int = 5, use_graph: bool = True) -> str:
    """
    Retrieve relevant memories using semantic search and graph traversal.
    
    The graph traversal finds connected memories through shared tags,
    allowing discovery of related information even if not directly similar.
    
    Args:
        query: What to search for in memories
        k: Maximum number of memories to retrieve (default 5)
        use_graph: If True, use graph traversal to find connected memories.
                   If False, use simple vector similarity.
    
    Returns:
        Retrieved memories formatted as text.
    """
    writer = get_stream_writer()
    writer(f"[MEMORY] Searching for: {query}")
    
    store = get_vector_store()
    
    if use_graph and GRAPH_RETRIEVER_AVAILABLE:
        # Build edges from tag metadata
        # This connects memories that share the same tags
        tag_edges = []
        # Common tag types we use
        for tag_type in ["type", "tags"]:
            tag_edges.append((tag_type, tag_type))
        
        retriever = GraphRetriever(
            store=store,
            edges=tag_edges,
            strategy=Eager(k=k, start_k=2, max_depth=2),
        )
        results = retriever.invoke(query)
    else:
        # Fallback to simple similarity search
        results = store.similarity_search(query, k=k)
    
    if not results:
        writer("[MEMORY] No relevant memories found")
        return "No relevant memories found."
    
    output = []
    for i, doc in enumerate(results, 1):
        mem_type = doc.metadata.get('type', 'unknown')
        timestamp = doc.metadata.get('timestamp', 'unknown')
        tags = doc.metadata.get('tags', '')
        
        output.append(f"### Memory {i} ({mem_type})")
        output.append(f"**Stored:** {timestamp}")
        if tags:
            output.append(f"**Tags:** {tags}")
        output.append(f"\n{doc.page_content}\n")
    
    writer(f"[MEMORY] Found {len(results)} relevant memories")
    return "\n".join(output)
