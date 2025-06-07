"""
Context7 Documentation OpenAPI Server
Provides access to library documentation and code examples
This is a simplified implementation that can be extended to use the actual Context7 API
"""

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, List, Dict, Any
import aiohttp
import asyncio
import os
import logging
import json
from datetime import datetime, timedelta
import hashlib

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

# Configuration
CONTEXT7_API_KEY = os.getenv('CONTEXT7_API_KEY', '')
CONTEXT7_API_URL = os.getenv('CONTEXT7_API_URL', 'https://api.context7.ai/v1')
CACHE_TTL = int(os.getenv('CACHE_TTL', '3600'))  # 1 hour default
MAX_TOKENS = int(os.getenv('MAX_TOKENS', '10000'))
REQUEST_TIMEOUT = int(os.getenv('REQUEST_TIMEOUT', '30'))

# Create FastAPI app
app = FastAPI(
    title="Context7 Documentation Server",
    description="Provides access to up-to-date library documentation and code examples",
    version="1.0.0"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models
class LibrarySearchRequest(BaseModel):
    library_name: str = Field(..., description="Name of the library to search for")
    language: Optional[str] = Field("python", description="Programming language")
    version: Optional[str] = Field(None, description="Specific version to search for")

class LibraryInfo(BaseModel):
    id: str
    name: str
    organization: str
    version: Optional[str]
    description: str
    language: str
    documentation_coverage: float
    trust_score: float
    last_updated: str

class DocumentationRequest(BaseModel):
    library_id: str = Field(..., description="Context7-compatible library ID (e.g., '/mongodb/docs')")
    topic: Optional[str] = Field(None, description="Specific topic to focus on")
    tokens: Optional[int] = Field(5000, description="Maximum tokens to retrieve")

class DocumentationResponse(BaseModel):
    library_id: str
    library_name: str
    version: Optional[str]
    content: str
    sections: List[Dict[str, Any]]
    examples: List[Dict[str, Any]]
    last_updated: str

# In-memory cache (in production, use Redis)
cache: Dict[str, Dict[str, Any]] = {}

def get_cache_key(params: Dict[str, Any]) -> str:
    """Generate cache key from parameters"""
    param_str = json.dumps(params, sort_keys=True)
    return hashlib.md5(param_str.encode()).hexdigest()

def is_cache_valid(cached_item: Dict[str, Any]) -> bool:
    """Check if cached item is still valid"""
    if 'timestamp' not in cached_item:
        return False
    cache_time = datetime.fromisoformat(cached_item['timestamp'])
    return datetime.utcnow() - cache_time < timedelta(seconds=CACHE_TTL)

# Fallback data for when Context7 API is not available
FALLBACK_LIBRARIES = {
    "fastapi": {
        "id": "/tiangolo/fastapi",
        "name": "FastAPI",
        "organization": "tiangolo",
        "version": "0.110.0",
        "description": "FastAPI framework, high performance, easy to learn, fast to code, ready for production",
        "language": "python",
        "documentation_coverage": 0.95,
        "trust_score": 9.5,
        "content": """
# FastAPI Documentation

FastAPI is a modern, fast web framework for building APIs with Python 3.7+.

## Quick Start

```python
from fastapi import FastAPI

app = FastAPI()

@app.get("/")
async def root():
    return {"message": "Hello World"}
```

## Key Features
- Fast performance
- Easy to use
- Automatic API documentation
- Type hints support
- Async support
""",
        "sections": [
            {"title": "Installation", "content": "pip install fastapi"},
            {"title": "Basic Usage", "content": "Create an app instance and define routes"},
            {"title": "Request Handling", "content": "Use path parameters, query parameters, and request bodies"}
        ],
        "examples": [
            {
                "title": "Hello World",
                "code": 'from fastapi import FastAPI\n\napp = FastAPI()\n\n@app.get("/")\nasync def root():\n    return {"message": "Hello World"}'
            }
        ]
    },
    "pandas": {
        "id": "/pandas-dev/pandas",
        "name": "pandas",
        "organization": "pandas-dev",
        "version": "2.2.0",
        "description": "Powerful data structures for data analysis, time series, and statistics",
        "language": "python",
        "documentation_coverage": 0.98,
        "trust_score": 9.8,
        "content": """
# Pandas Documentation

pandas is a fast, powerful, flexible and easy to use open source data analysis tool.

## Quick Start

```python
import pandas as pd

# Create a DataFrame
df = pd.DataFrame({
    'A': [1, 2, 3],
    'B': ['a', 'b', 'c']
})
```

## Key Features
- DataFrame and Series objects
- Reading/writing various formats
- Data manipulation and analysis
- Time series functionality
""",
        "sections": [
            {"title": "Installation", "content": "pip install pandas"},
            {"title": "Data Structures", "content": "DataFrame and Series are the core data structures"},
            {"title": "IO Operations", "content": "Read and write CSV, Excel, SQL, and more"}
        ],
        "examples": [
            {
                "title": "Create DataFrame",
                "code": "import pandas as pd\n\ndf = pd.DataFrame({'A': [1, 2, 3], 'B': ['a', 'b', 'c']})"
            }
        ]
    }
}

# Routes
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "context7-docs"}

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi():
    """Get OpenAPI schema"""
    return app.openapi()

@app.post("/resolve-library-id", response_model=List[LibraryInfo])
async def resolve_library_id(request: LibrarySearchRequest):
    """
    Search for libraries and get Context7-compatible IDs
    
    This endpoint helps find the correct library ID to use with get-library-docs
    """
    cache_key = get_cache_key({"action": "search", **request.model_dump()})
    
    # Check cache
    if cache_key in cache and is_cache_valid(cache[cache_key]):
        return cache[cache_key]['data']
    
    # If we have a Context7 API key, try to use the real API
    if CONTEXT7_API_KEY:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {CONTEXT7_API_KEY}"}
                params = {
                    "q": request.library_name,
                    "language": request.language,
                    "version": request.version
                }
                
                async with session.get(
                    f"{CONTEXT7_API_URL}/libraries/search",
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        # Transform to our model
                        libraries = []
                        for lib in data.get('libraries', []):
                            libraries.append(LibraryInfo(
                                id=lib['id'],
                                name=lib['name'],
                                organization=lib.get('organization', ''),
                                version=lib.get('version'),
                                description=lib.get('description', ''),
                                language=lib.get('language', request.language),
                                documentation_coverage=lib.get('coverage', 0.0),
                                trust_score=lib.get('trust_score', 0.0),
                                last_updated=lib.get('last_updated', datetime.utcnow().isoformat())
                            ))
                        
                        # Cache the result
                        cache[cache_key] = {
                            'data': libraries,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        return libraries
                        
        except Exception as e:
            logger.error(f"Context7 API error: {e}")
    
    # Fallback to local data
    matching_libraries = []
    search_term = request.library_name.lower()
    
    for name, lib_data in FALLBACK_LIBRARIES.items():
        if search_term in name.lower() or search_term in lib_data['description'].lower():
            matching_libraries.append(LibraryInfo(
                id=lib_data['id'],
                name=lib_data['name'],
                organization=lib_data['organization'],
                version=lib_data['version'],
                description=lib_data['description'],
                language=lib_data['language'],
                documentation_coverage=lib_data['documentation_coverage'],
                trust_score=lib_data['trust_score'],
                last_updated=datetime.utcnow().isoformat()
            ))
    
    if not matching_libraries:
        # Return a generic result
        matching_libraries.append(LibraryInfo(
            id=f"/{request.library_name}/{request.library_name}",
            name=request.library_name,
            organization=request.library_name,
            version="latest",
            description=f"Documentation for {request.library_name}",
            language=request.language,
            documentation_coverage=0.5,
            trust_score=5.0,
            last_updated=datetime.utcnow().isoformat()
        ))
    
    # Cache the result
    cache[cache_key] = {
        'data': matching_libraries,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    return matching_libraries

@app.post("/get-library-docs", response_model=DocumentationResponse)
async def get_library_docs(request: DocumentationRequest):
    """
    Retrieve documentation for a specific library
    
    Requires a Context7-compatible library ID obtained from resolve-library-id
    """
    cache_key = get_cache_key({"action": "docs", **request.model_dump()})
    
    # Check cache
    if cache_key in cache and is_cache_valid(cache[cache_key]):
        return cache[cache_key]['data']
    
    # Limit tokens
    tokens = min(request.tokens or MAX_TOKENS, MAX_TOKENS)
    
    # If we have a Context7 API key, try to use the real API
    if CONTEXT7_API_KEY:
        try:
            async with aiohttp.ClientSession() as session:
                headers = {"Authorization": f"Bearer {CONTEXT7_API_KEY}"}
                params = {
                    "tokens": tokens,
                    "topic": request.topic
                }
                
                async with session.get(
                    f"{CONTEXT7_API_URL}/libraries{request.library_id}/docs",
                    headers=headers,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=REQUEST_TIMEOUT)
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        
                        result = DocumentationResponse(
                            library_id=request.library_id,
                            library_name=data.get('library_name', request.library_id.split('/')[-1]),
                            version=data.get('version'),
                            content=data.get('content', ''),
                            sections=data.get('sections', []),
                            examples=data.get('examples', []),
                            last_updated=data.get('last_updated', datetime.utcnow().isoformat())
                        )
                        
                        # Cache the result
                        cache[cache_key] = {
                            'data': result,
                            'timestamp': datetime.utcnow().isoformat()
                        }
                        return result
                        
        except Exception as e:
            logger.error(f"Context7 API error: {e}")
    
    # Fallback to local data
    # Extract library name from ID
    lib_name = request.library_id.split('/')[-1].lower()
    
    # Find matching library
    for name, lib_data in FALLBACK_LIBRARIES.items():
        if name.lower() in lib_name or lib_name in name.lower():
            # Filter content based on topic if specified
            content = lib_data['content']
            sections = lib_data['sections']
            examples = lib_data['examples']
            
            if request.topic:
                # Simple topic filtering (in production, use better NLP)
                topic_lower = request.topic.lower()
                filtered_sections = [s for s in sections if topic_lower in s['title'].lower() or topic_lower in s['content'].lower()]
                filtered_examples = [e for e in examples if topic_lower in e['title'].lower() or topic_lower in e.get('code', '').lower()]
                
                if filtered_sections:
                    sections = filtered_sections
                if filtered_examples:
                    examples = filtered_examples
            
            # Truncate content to token limit (rough approximation)
            if len(content) > tokens * 4:  # Rough token estimation
                content = content[:tokens * 4] + "\n\n... (truncated)"
            
            result = DocumentationResponse(
                library_id=request.library_id,
                library_name=lib_data['name'],
                version=lib_data['version'],
                content=content,
                sections=sections,
                examples=examples,
                last_updated=datetime.utcnow().isoformat()
            )
            
            # Cache the result
            cache[cache_key] = {
                'data': result,
                'timestamp': datetime.utcnow().isoformat()
            }
            return result
    
    # If no match found, return a generic response
    result = DocumentationResponse(
        library_id=request.library_id,
        library_name=request.library_id.split('/')[-1],
        version="unknown",
        content=f"Documentation for {request.library_id} is not available in the local cache. Please ensure you have a valid Context7 API key configured.",
        sections=[],
        examples=[],
        last_updated=datetime.utcnow().isoformat()
    )
    
    # Cache even the fallback
    cache[cache_key] = {
        'data': result,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    return result

@app.get("/supported-libraries")
async def list_supported_libraries():
    """List libraries available in the local cache"""
    libraries = []
    for name, lib_data in FALLBACK_LIBRARIES.items():
        libraries.append({
            "id": lib_data['id'],
            "name": lib_data['name'],
            "language": lib_data['language'],
            "version": lib_data['version'],
            "description": lib_data['description']
        })
    
    return {
        "libraries": libraries,
        "total": len(libraries),
        "note": "This is a subset of available libraries. With a Context7 API key, many more libraries are accessible."
    }

@app.delete("/cache")
async def clear_cache():
    """Clear the documentation cache"""
    cache.clear()
    return {"message": "Cache cleared successfully"}

@app.get("/cache/stats")
async def cache_stats():
    """Get cache statistics"""
    valid_items = sum(1 for item in cache.values() if is_cache_valid(item))
    return {
        "total_items": len(cache),
        "valid_items": valid_items,
        "expired_items": len(cache) - valid_items,
        "cache_ttl_seconds": CACHE_TTL
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
