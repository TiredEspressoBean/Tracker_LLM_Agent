"""Simple, focused tools for Ambac Tracker RAG + ORM operations."""

import requests
from typing import Any, Dict, List, Optional
from langchain.tools import tool

from react_agent.configuration import Configuration


class APIError(Exception):
    """Exception raised when API calls fail"""
    pass


def _make_api_request(endpoint: str, method: str = "GET", data: Optional[Dict] = None, params: Optional[Dict] = None) -> Dict[str, Any]:
    """Make authenticated request to Django API"""
    config = Configuration.from_context()
    
    url = f"{config.django_api_base_url.rstrip('/')}/{endpoint.lstrip('/')}"
    headers = {
        "Authorization": f"Token {config.django_api_token}",
        "Content-Type": "application/json"
    }
    
    try:
        if method.upper() == "GET":
            response = requests.get(url, headers=headers, params=params, timeout=30)
        elif method.upper() == "POST":
            response = requests.post(url, headers=headers, json=data, timeout=30)
        else:
            raise APIError(f"Unsupported HTTP method: {method}")
        
        response.raise_for_status()
        return response.json()
    
    except requests.exceptions.RequestException as e:
        raise APIError(f"API request failed: {str(e)}")


@tool
def get_schema() -> str:
    """
    Get information about available database models and their fields.
    Use this to understand what data is available before making queries.
    
    Returns:
        Available models, fields, and example queries
    """
    try:
        result = _make_api_request("ai/query/schema_info/", "GET")
        
        models = result.get("allowed_models", {})
        operations = result.get("allowed_operations", [])
        examples = result.get("examples", {})
        
        # Format for LLM
        schema_info = ["Available Models and Fields:"]
        for model, fields in models.items():
            schema_info.append(f"\n{model}:")
            schema_info.append(f"  Fields: {', '.join(fields)}")
        
        schema_info.append(f"\nAllowed Filter Operations: {', '.join(operations)}")
        
        if examples:
            schema_info.append("\nExample Queries:")
            for name, example in examples.items():
                schema_info.append(f"  {name}: {example}")
        
        return "\n".join(schema_info)
        
    except Exception as e:
        return f"Error getting schema: {str(e)}"


@tool
def query_database(model: str, filters: Optional[Dict] = None, fields: Optional[List[str]] = None, 
                  limit: int = 10, aggregate: Optional[str] = None) -> str:
    """
    Query the manufacturing database for current information.
    
    Args:
        model: Model name (e.g., "Orders", "Parts", "WorkOrder", "QualityReports", "User", "Companies")
        filters: Dictionary of filters (e.g., {"order_status": "PENDING", "customer__name__icontains": "John"})  
        fields: List of specific fields to return (optional, returns all if not specified)
        limit: Maximum number of results (default 10, max 100)
        aggregate: Type of aggregation - "count" to just get the count
    
    Returns:
        Query results from the database
    """
    try:
        request_data = {
            "model": model,
            "filters": filters or {},
            "fields": fields or [],
            "limit": min(limit, 100)
        }
        
        if aggregate:
            request_data["aggregate"] = aggregate
        
        result = _make_api_request("ai/query/execute_read_only/", "POST", request_data)
        
        if aggregate == "count":
            count = result.get("result", 0)
            return f"Count: {count} {model} records"
        
        if "results" not in result or not result["results"]:
            return f"No {model} records found with the given filters"
        
        # Format results
        count = len(result["results"])
        formatted_results = [f"Found {count} {model} records:"]
        
        for item in result["results"]:
            # Create a readable summary of each item
            item_parts = []
            for key, value in item.items():
                if value is not None and str(value).strip():
                    item_parts.append(f"{key}: {value}")
            
            formatted_results.append("  " + " | ".join(item_parts[:5]))  # Limit to first 5 fields
        
        if count >= limit:
            formatted_results.append(f"... (showing first {limit} results)")
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        return f"Error querying {model}: {str(e)}"


@tool 
def search_documents_semantic(query: str, limit: int = 5, threshold: float = 0.7) -> str:
    """
    Search documents using semantic/vector similarity.
    Best for finding conceptually related content, procedures, and specifications.
    
    Args:
        query: What you're looking for (e.g., "quality inspection procedures", "tolerance requirements")
        limit: Maximum number of results (default 5)
        threshold: Similarity threshold 0-1, higher = more strict (default 0.7)
    
    Returns:
        Relevant document excerpts with similarity scores
    """
    try:
        # First embed the query
        embed_result = _make_api_request("ai/embedding/embed_query/", "POST", {"query": query})
        embedding = embed_result.get("embedding")
        
        if not embedding:
            return f"Failed to create embedding for query: {query}"
        
        # Then search
        search_result = _make_api_request("ai/search/vector_search/", "POST", {
            "embedding": embedding,
            "limit": limit,
            "threshold": threshold
        })
        
        if "results" not in search_result or not search_result["results"]:
            return f"No documents found for: '{query}'"
        
        # Format results
        formatted_results = []
        for i, chunk in enumerate(search_result["results"], 1):
            similarity = chunk.get("similarity", 0)
            doc_name = chunk.get("doc_name", "Unknown document")
            content = chunk.get("preview_text", chunk.get("full_text", "No content"))
            
            # Truncate long content
            if len(content) > 400:
                content = content[:400] + "..."
            
            formatted_results.append(f"""
Result {i} (similarity: {similarity:.2f}):
Document: {doc_name}
Content: {content}
""")
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        return f"Error in semantic search: {str(e)}"


@tool
def search_documents_keyword(query: str, limit: int = 5) -> str:
    """
    Search documents using keyword/text matching.
    Best for finding exact terms, part numbers, and specific phrases.
    
    Args:
        query: Keywords to search for (e.g., "ABC-123", "step 5", "temperature 350")
        limit: Maximum number of results (default 5)
    
    Returns:
        Document excerpts containing the keywords
    """
    try:
        result = _make_api_request("ai/search/keyword_search/", "GET", params={
            "q": query,
            "limit": limit
        })
        
        if "results" not in result or not result["results"]:
            return f"No documents found containing: '{query}'"
        
        # Format results
        formatted_results = []
        for i, chunk in enumerate(result["results"], 1):
            rank = chunk.get("rank", 0)
            doc_name = chunk.get("doc_name", "Unknown document")
            content = chunk.get("preview_text", chunk.get("full_text", "No content"))
            
            # Truncate long content
            if len(content) > 400:
                content = content[:400] + "..."
            
            formatted_results.append(f"""
Result {i} (rank: {rank:.2f}):
Document: {doc_name}  
Content: {content}
""")
        
        return "\n".join(formatted_results)
        
    except Exception as e:
        return f"Error in keyword search: {str(e)}"


@tool
def get_context(chunk_id: int, window_size: int = 2) -> str:
    """
    Get additional context around a specific document chunk.
    Use this when you find a relevant piece of information and need more context.
    
    Args:
        chunk_id: ID of the document chunk (from search results)
        window_size: Number of chunks before and after to include (default 2)
    
    Returns:
        Extended context around the chunk
    """
    try:
        result = _make_api_request("ai/search/get_context_window/", "POST", {
            "chunk_id": chunk_id,
            "window_size": window_size
        })
        
        if "chunks" not in result or not result["chunks"]:
            return f"No context found for chunk ID: {chunk_id}"
        
        doc_name = result.get("doc_name", "Unknown document")
        center_index = result.get("center_index", 0)
        
        # Format context
        formatted_chunks = [f"Context from document: {doc_name}"]
        formatted_chunks.append(f"Center chunk index: {center_index}\n")
        
        for chunk in result["chunks"]:
            index = chunk.get("index", 0)
            is_center = chunk.get("is_center", False)
            content = chunk.get("full_text", chunk.get("preview_text", "No content"))
            
            marker = ">>> " if is_center else "    "
            formatted_chunks.append(f"{marker}[{index}] {content}")
        
        return "\n".join(formatted_chunks)
        
    except Exception as e:
        return f"Error getting context for chunk {chunk_id}: {str(e)}"


# List of all available tools
TOOLS = [
    get_schema,
    query_database,
    search_documents_semantic,
    search_documents_keyword,
    get_context
]