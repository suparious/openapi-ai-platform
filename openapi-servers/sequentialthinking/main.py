"""
Sequential Thinking OpenAPI Server
Provides a tool for breaking down complex problems into sequential thoughts
"""

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime
import asyncio
import uuid
import redis.asyncio as redis
import json
import os
import logging
from contextlib import asynccontextmanager

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

# Configuration
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/2')
MAX_THOUGHTS = int(os.getenv('MAX_THOUGHTS', '100'))
TIMEOUT_SECONDS = int(os.getenv('TIMEOUT_SECONDS', '600'))
THOUGHT_CACHE_TTL = int(os.getenv('THOUGHT_CACHE_TTL', '3600'))

# Global Redis client
redis_client: Optional[redis.Redis] = None

# Models
class ThoughtInput(BaseModel):
    thought: str = Field(..., description="Current thinking step")
    next_thought_needed: bool = Field(..., description="Whether another thought step is needed")
    thought_number: int = Field(..., description="Current thought number", ge=1)
    total_thoughts: int = Field(..., description="Estimated total thoughts needed", ge=1)
    is_revision: Optional[bool] = Field(False, description="Whether this revises previous thinking")
    revises_thought: Optional[int] = Field(None, description="Which thought is being reconsidered", ge=1)
    branch_from_thought: Optional[int] = Field(None, description="Branching point thought number", ge=1)
    branch_id: Optional[str] = Field(None, description="Branch identifier")
    needs_more_thoughts: Optional[bool] = Field(False, description="If more thoughts are needed")

class ThoughtResponse(BaseModel):
    thought_number: int
    total_thoughts: int
    next_thought_needed: bool
    branches: List[str] = Field(default_factory=list)
    thought_history_length: int

class ThinkingSession(BaseModel):
    session_id: str
    created_at: datetime
    updated_at: datetime
    thoughts: List[ThoughtInput]
    branches: Dict[str, List[ThoughtInput]]
    status: str  # active, completed, timeout
    result: Optional[str] = None

# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global redis_client
    
    # Startup
    logger.info("Starting Sequential Thinking Server...")
    redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    logger.info("Connected to Redis")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Sequential Thinking Server...")
    if redis_client:
        await redis_client.close()

# Create FastAPI app
app = FastAPI(
    title="Sequential Thinking OpenAPI Server",
    description="Tool for breaking down complex problems into sequential thoughts",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv('CORS_ORIGINS', '*').split(','),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Helper functions
async def get_session(session_id: str) -> Optional[ThinkingSession]:
    """Retrieve a thinking session from Redis"""
    data = await redis_client.get(f"session:{session_id}")
    if data:
        session_dict = json.loads(data)
        # Convert datetime strings back to datetime objects
        session_dict['created_at'] = datetime.fromisoformat(session_dict['created_at'])
        session_dict['updated_at'] = datetime.fromisoformat(session_dict['updated_at'])
        return ThinkingSession(**session_dict)
    return None

async def save_session(session: ThinkingSession):
    """Save a thinking session to Redis"""
    # Convert to dict and handle datetime serialization
    session_dict = session.model_dump()
    session_dict['created_at'] = session.created_at.isoformat()
    session_dict['updated_at'] = session.updated_at.isoformat()
    
    await redis_client.setex(
        f"session:{session.session_id}",
        THOUGHT_CACHE_TTL,
        json.dumps(session_dict)
    )

async def cleanup_old_sessions():
    """Background task to cleanup old sessions"""
    # This would be more complex in production, but for now we rely on Redis TTL
    pass

# Routes
@app.get("/health")
async def health():
    """Health check endpoint"""
    try:
        await redis_client.ping()
        return {"status": "healthy", "service": "sequential-thinking"}
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=503, detail="Service unhealthy")

@app.get("/openapi.json", include_in_schema=False)
async def get_openapi():
    """Get OpenAPI schema"""
    return app.openapi()

@app.post("/sequentialthinking", response_model=ThoughtResponse)
async def sequential_thinking(
    thought_input: ThoughtInput,
    session_id: Optional[str] = None,
    background_tasks: BackgroundTasks = BackgroundTasks()
) -> ThoughtResponse:
    """
    Process a sequential thinking step
    
    This tool helps analyze problems through a flexible thinking process that can adapt and evolve.
    Each thought can build on, question, or revise previous insights as understanding deepens.
    """
    try:
        # Get or create session
        if session_id:
            session = await get_session(session_id)
            if not session:
                raise HTTPException(status_code=404, detail="Session not found")
        else:
            # Create new session
            session = ThinkingSession(
                session_id=str(uuid.uuid4()),
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
                thoughts=[],
                branches={},
                status="active"
            )
        
        # Validate thought number
        if thought_input.thought_number > MAX_THOUGHTS:
            raise HTTPException(
                status_code=400, 
                detail=f"Maximum thoughts ({MAX_THOUGHTS}) exceeded"
            )
        
        # Handle branching
        current_branch = thought_input.branch_id or "main"
        if current_branch not in session.branches:
            session.branches[current_branch] = []
        
        # Add thought to appropriate branch
        if current_branch == "main":
            session.thoughts.append(thought_input)
        else:
            session.branches[current_branch].append(thought_input)
        
        # Update session
        session.updated_at = datetime.utcnow()
        
        # Check if completed
        if not thought_input.next_thought_needed:
            session.status = "completed"
            # Compile final result from all thoughts
            all_thoughts = session.thoughts.copy()
            for branch_thoughts in session.branches.values():
                all_thoughts.extend(branch_thoughts)
            
            session.result = "\n\n".join([
                f"Thought {t.thought_number}: {t.thought}"
                for t in sorted(all_thoughts, key=lambda x: x.thought_number)
            ])
        
        # Save session
        await save_session(session)
        
        # Prepare response
        response = ThoughtResponse(
            thought_number=thought_input.thought_number,
            total_thoughts=thought_input.total_thoughts,
            next_thought_needed=thought_input.next_thought_needed,
            branches=list(session.branches.keys()),
            thought_history_length=len(session.thoughts)
        )
        
        # Add session_id to response headers
        background_tasks.add_task(
            logger.info, 
            f"Session {session.session_id}: Thought {thought_input.thought_number} processed"
        )
        
        return response
        
    except Exception as e:
        logger.error(f"Error in sequential thinking: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/sessions/{session_id}")
async def get_thinking_session(session_id: str) -> ThinkingSession:
    """Retrieve a complete thinking session"""
    session = await get_session(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session

@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """Delete a thinking session"""
    exists = await redis_client.exists(f"session:{session_id}")
    if not exists:
        raise HTTPException(status_code=404, detail="Session not found")
    
    await redis_client.delete(f"session:{session_id}")
    return {"message": "Session deleted successfully"}

@app.get("/sessions")
async def list_sessions(limit: int = 10, offset: int = 0):
    """List all thinking sessions"""
    # Get all session keys
    keys = []
    async for key in redis_client.scan_iter(match="session:*"):
        keys.append(key)
    
    # Sort by modification time (would need to fetch all to sort properly)
    # For now, just return the requested slice
    session_ids = [k.replace("session:", "") for k in keys[offset:offset + limit]]
    
    sessions = []
    for session_id in session_ids:
        session = await get_session(session_id)
        if session:
            sessions.append({
                "session_id": session.session_id,
                "created_at": session.created_at.isoformat(),
                "updated_at": session.updated_at.isoformat(),
                "status": session.status,
                "thought_count": len(session.thoughts),
                "branch_count": len(session.branches)
            })
    
    return {
        "sessions": sessions,
        "total": len(keys),
        "limit": limit,
        "offset": offset
    }

# Example endpoint to demonstrate usage
@app.post("/example")
async def example_usage():
    """Example of how to use the sequential thinking tool"""
    return {
        "description": "Sequential thinking helps break down complex problems",
        "example_sequence": [
            {
                "step": 1,
                "request": {
                    "thought": "First, I need to understand the problem scope",
                    "next_thought_needed": True,
                    "thought_number": 1,
                    "total_thoughts": 5
                }
            },
            {
                "step": 2,
                "request": {
                    "thought": "Now I'll identify the key components",
                    "next_thought_needed": True,
                    "thought_number": 2,
                    "total_thoughts": 5
                }
            },
            {
                "step": 3,
                "request": {
                    "thought": "Wait, I need to reconsider the first assumption",
                    "next_thought_needed": True,
                    "thought_number": 3,
                    "total_thoughts": 6,
                    "is_revision": True,
                    "revises_thought": 1
                }
            }
        ],
        "features": [
            "Flexible thought progression",
            "Revision and branching support",
            "Session management",
            "Persistent storage in Redis"
        ]
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
