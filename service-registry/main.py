"""
Simple Service Registry for Distributed AI Platform
Provides service discovery without HashiCorp Consul
"""

from fastapi import FastAPI, HTTPException, Security, Depends, BackgroundTasks
from fastapi.security.api_key import APIKeyHeader
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any
from datetime import datetime, timedelta
import asyncio
import aiohttp
import asyncpg
import redis.asyncio as redis
from contextlib import asynccontextmanager
import os
import json
import logging
from prometheus_client import Counter, Gauge, Histogram, generate_latest
from fastapi.responses import PlainTextResponse

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

# Environment variables
DATABASE_URL = os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost/service_registry')
REDIS_URL = os.getenv('REDIS_URL', 'redis://localhost:6379/1')
API_KEY = os.getenv('API_KEY', 'default_api_key')
HEALTH_CHECK_INTERVAL = int(os.getenv('HEALTH_CHECK_INTERVAL', '30'))
CACHE_TTL = int(os.getenv('CACHE_TTL', '60'))

# Metrics
service_count = Gauge('service_registry_services_total', 'Total number of registered services')
health_check_duration = Histogram('service_registry_health_check_duration_seconds', 'Health check duration')
health_check_failures = Counter('service_registry_health_check_failures_total', 'Total health check failures', ['service'])
api_requests = Counter('service_registry_api_requests_total', 'Total API requests', ['method', 'endpoint', 'status'])

# Models
class Service(BaseModel):
    name: str = Field(..., description="Service name")
    host: str = Field(..., description="Service hostname")
    port: int = Field(..., description="Service port")
    path: str = Field("/", description="Service base path")
    health_check_url: Optional[str] = Field(None, description="Health check URL")
    tags: List[str] = Field(default_factory=list, description="Service tags")
    metadata: Dict[str, Any] = Field(default_factory=dict, description="Additional metadata")
    
class ServiceStatus(BaseModel):
    service: Service
    status: str = Field(..., description="Service status: healthy, unhealthy, unknown")
    last_check: Optional[datetime] = None
    response_time: Optional[float] = None
    error: Optional[str] = None

class ServiceQuery(BaseModel):
    tags: Optional[List[str]] = None
    status: Optional[str] = None
    name_pattern: Optional[str] = None

# Global variables
db_pool: Optional[asyncpg.Pool] = None
redis_client: Optional[redis.Redis] = None
health_check_task: Optional[asyncio.Task] = None

# API Key authentication
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

async def get_api_key(api_key: str = Security(api_key_header)):
    if api_key == API_KEY:
        return api_key
    raise HTTPException(status_code=403, detail="Invalid API key")

# Database initialization
async def init_db():
    """Initialize database with required tables"""
    async with db_pool.acquire() as conn:
        await conn.execute('''
            CREATE TABLE IF NOT EXISTS services (
                id SERIAL PRIMARY KEY,
                name VARCHAR(255) UNIQUE NOT NULL,
                host VARCHAR(255) NOT NULL,
                port INTEGER NOT NULL,
                path VARCHAR(255) DEFAULT '/',
                health_check_url TEXT,
                tags TEXT[],
                metadata JSONB DEFAULT '{}',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE TABLE IF NOT EXISTS health_checks (
                id SERIAL PRIMARY KEY,
                service_name VARCHAR(255) REFERENCES services(name) ON DELETE CASCADE,
                status VARCHAR(50),
                response_time FLOAT,
                error TEXT,
                checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            
            CREATE INDEX IF NOT EXISTS idx_services_tags ON services USING GIN(tags);
            CREATE INDEX IF NOT EXISTS idx_health_checks_service ON health_checks(service_name);
            CREATE INDEX IF NOT EXISTS idx_health_checks_time ON health_checks(checked_at);
        ''')

# Health check functions
async def check_service_health(service: Service) -> ServiceStatus:
    """Check health of a single service"""
    status = ServiceStatus(service=service, status="unknown")
    
    if not service.health_check_url:
        status.status = "unknown"
        return status
    
    start_time = asyncio.get_event_loop().time()
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                service.health_check_url,
                timeout=aiohttp.ClientTimeout(total=10)
            ) as response:
                status.response_time = asyncio.get_event_loop().time() - start_time
                status.last_check = datetime.utcnow()
                
                if response.status < 300:
                    status.status = "healthy"
                else:
                    status.status = "unhealthy"
                    status.error = f"HTTP {response.status}"
                    
    except asyncio.TimeoutError:
        status.status = "unhealthy"
        status.error = "Timeout"
        health_check_failures.labels(service=service.name).inc()
    except Exception as e:
        status.status = "unhealthy"
        status.error = str(e)
        health_check_failures.labels(service=service.name).inc()
    
    # Record metrics
    health_check_duration.observe(asyncio.get_event_loop().time() - start_time)
    
    # Store result in database
    async with db_pool.acquire() as conn:
        await conn.execute('''
            INSERT INTO health_checks (service_name, status, response_time, error)
            VALUES ($1, $2, $3, $4)
        ''', service.name, status.status, status.response_time, status.error)
    
    # Cache result
    await redis_client.setex(
        f"health:{service.name}",
        CACHE_TTL,
        json.dumps({
            "status": status.status,
            "last_check": status.last_check.isoformat() if status.last_check else None,
            "response_time": status.response_time,
            "error": status.error
        })
    )
    
    return status

async def health_check_loop():
    """Background task to check all services periodically"""
    while True:
        try:
            async with db_pool.acquire() as conn:
                services = await conn.fetch('SELECT * FROM services')
            
            for record in services:
                service = Service(
                    name=record['name'],
                    host=record['host'],
                    port=record['port'],
                    path=record['path'],
                    health_check_url=record['health_check_url'],
                    tags=record['tags'] or [],
                    metadata=record['metadata'] or {}
                )
                await check_service_health(service)
            
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)
            
        except Exception as e:
            logger.error(f"Health check loop error: {e}")
            await asyncio.sleep(HEALTH_CHECK_INTERVAL)

# Lifecycle management
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    global db_pool, redis_client, health_check_task
    
    # Startup
    logger.info("Starting Service Registry...")
    
    # Initialize database connection pool
    db_pool = await asyncpg.create_pool(DATABASE_URL, min_size=5, max_size=20)
    await init_db()
    
    # Initialize Redis connection
    redis_client = await redis.from_url(REDIS_URL, decode_responses=True)
    
    # Start health check background task
    health_check_task = asyncio.create_task(health_check_loop())
    
    logger.info("Service Registry started successfully")
    
    yield
    
    # Shutdown
    logger.info("Shutting down Service Registry...")
    
    # Cancel health check task
    if health_check_task:
        health_check_task.cancel()
        try:
            await health_check_task
        except asyncio.CancelledError:
            pass
    
    # Close connections
    if db_pool:
        await db_pool.close()
    if redis_client:
        await redis_client.close()
    
    logger.info("Service Registry shut down")

# Create FastAPI app
app = FastAPI(
    title="Service Registry",
    description="Simple service discovery for distributed AI platform",
    version="1.0.0",
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routes
@app.get("/health")
async def health():
    """Health check endpoint"""
    return {"status": "healthy", "service": "service-registry"}

@app.get("/metrics", response_class=PlainTextResponse)
async def metrics():
    """Prometheus metrics endpoint"""
    return generate_latest()

@app.post("/services", dependencies=[Depends(get_api_key)])
async def register_service(service: Service, background_tasks: BackgroundTasks):
    """Register a new service"""
    api_requests.labels(method="POST", endpoint="/services", status="200").inc()
    
    async with db_pool.acquire() as conn:
        try:
            await conn.execute('''
                INSERT INTO services (name, host, port, path, health_check_url, tags, metadata)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (name) DO UPDATE SET
                    host = EXCLUDED.host,
                    port = EXCLUDED.port,
                    path = EXCLUDED.path,
                    health_check_url = EXCLUDED.health_check_url,
                    tags = EXCLUDED.tags,
                    metadata = EXCLUDED.metadata,
                    updated_at = CURRENT_TIMESTAMP
            ''', service.name, service.host, service.port, service.path,
                service.health_check_url, service.tags, json.dumps(service.metadata))
            
            # Update metrics
            service_count.inc()
            
            # Trigger immediate health check
            background_tasks.add_task(check_service_health, service)
            
            return {"message": f"Service {service.name} registered successfully"}
            
        except Exception as e:
            api_requests.labels(method="POST", endpoint="/services", status="500").inc()
            logger.error(f"Failed to register service: {e}")
            raise HTTPException(status_code=500, detail=str(e))

@app.get("/services")
async def list_services(query: ServiceQuery = ServiceQuery()):
    """List all registered services with optional filtering"""
    api_requests.labels(method="GET", endpoint="/services", status="200").inc()
    
    # Build query
    where_clauses = []
    params = []
    param_count = 0
    
    if query.tags:
        param_count += 1
        where_clauses.append(f"tags && ${param_count}")
        params.append(query.tags)
    
    if query.name_pattern:
        param_count += 1
        where_clauses.append(f"name ILIKE ${param_count}")
        params.append(f"%{query.name_pattern}%")
    
    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)
    
    async with db_pool.acquire() as conn:
        records = await conn.fetch(f'''
            SELECT s.*, 
                   h.status as health_status,
                   h.response_time,
                   h.checked_at as last_check
            FROM services s
            LEFT JOIN LATERAL (
                SELECT status, response_time, checked_at
                FROM health_checks
                WHERE service_name = s.name
                ORDER BY checked_at DESC
                LIMIT 1
            ) h ON true
            {where_sql}
            ORDER BY s.name
        ''', *params)
    
    services = []
    for record in records:
        # Check cache for latest health status
        cached_health = await redis_client.get(f"health:{record['name']}")
        if cached_health:
            health_data = json.loads(cached_health)
            health_status = health_data.get('status', record['health_status'])
            last_check = health_data.get('last_check')
            response_time = health_data.get('response_time')
        else:
            health_status = record['health_status']
            last_check = record['last_check'].isoformat() if record['last_check'] else None
            response_time = record['response_time']
        
        # Filter by status if requested
        if query.status and health_status != query.status:
            continue
        
        services.append({
            "name": record['name'],
            "host": record['host'],
            "port": record['port'],
            "path": record['path'],
            "health_check_url": record['health_check_url'],
            "tags": record['tags'] or [],
            "metadata": record['metadata'] or {},
            "status": health_status or "unknown",
            "last_check": last_check,
            "response_time": response_time
        })
    
    return {"services": services, "count": len(services)}

@app.get("/services/{name}")
async def get_service(name: str):
    """Get details of a specific service"""
    api_requests.labels(method="GET", endpoint="/services/{name}", status="200").inc()
    
    async with db_pool.acquire() as conn:
        record = await conn.fetchrow('SELECT * FROM services WHERE name = $1', name)
        
    if not record:
        api_requests.labels(method="GET", endpoint="/services/{name}", status="404").inc()
        raise HTTPException(status_code=404, detail=f"Service {name} not found")
    
    # Get latest health status
    cached_health = await redis_client.get(f"health:{name}")
    if cached_health:
        health_data = json.loads(cached_health)
    else:
        # Get from database
        async with db_pool.acquire() as conn:
            health_record = await conn.fetchrow('''
                SELECT status, response_time, error, checked_at
                FROM health_checks
                WHERE service_name = $1
                ORDER BY checked_at DESC
                LIMIT 1
            ''', name)
        
        if health_record:
            health_data = {
                "status": health_record['status'],
                "response_time": health_record['response_time'],
                "error": health_record['error'],
                "last_check": health_record['checked_at'].isoformat()
            }
        else:
            health_data = {"status": "unknown"}
    
    return {
        "name": record['name'],
        "host": record['host'],
        "port": record['port'],
        "path": record['path'],
        "health_check_url": record['health_check_url'],
        "tags": record['tags'] or [],
        "metadata": record['metadata'] or {},
        "health": health_data,
        "created_at": record['created_at'].isoformat(),
        "updated_at": record['updated_at'].isoformat()
    }

@app.delete("/services/{name}", dependencies=[Depends(get_api_key)])
async def delete_service(name: str):
    """Delete a service"""
    api_requests.labels(method="DELETE", endpoint="/services/{name}", status="200").inc()
    
    async with db_pool.acquire() as conn:
        result = await conn.execute('DELETE FROM services WHERE name = $1', name)
        
    if result == "DELETE 0":
        api_requests.labels(method="DELETE", endpoint="/services/{name}", status="404").inc()
        raise HTTPException(status_code=404, detail=f"Service {name} not found")
    
    # Clear cache
    await redis_client.delete(f"health:{name}")
    
    # Update metrics
    service_count.dec()
    
    return {"message": f"Service {name} deleted successfully"}

@app.post("/services/{name}/check", dependencies=[Depends(get_api_key)])
async def check_service(name: str, background_tasks: BackgroundTasks):
    """Trigger health check for a specific service"""
    api_requests.labels(method="POST", endpoint="/services/{name}/check", status="200").inc()
    
    async with db_pool.acquire() as conn:
        record = await conn.fetchrow('SELECT * FROM services WHERE name = $1', name)
        
    if not record:
        api_requests.labels(method="POST", endpoint="/services/{name}/check", status="404").inc()
        raise HTTPException(status_code=404, detail=f"Service {name} not found")
    
    service = Service(
        name=record['name'],
        host=record['host'],
        port=record['port'],
        path=record['path'],
        health_check_url=record['health_check_url'],
        tags=record['tags'] or [],
        metadata=record['metadata'] or {}
    )
    
    # Trigger health check
    background_tasks.add_task(check_service_health, service)
    
    return {"message": f"Health check triggered for service {name}"}

@app.get("/health-history/{name}")
async def get_health_history(name: str, hours: int = 24):
    """Get health check history for a service"""
    api_requests.labels(method="GET", endpoint="/health-history/{name}", status="200").inc()
    
    since = datetime.utcnow() - timedelta(hours=hours)
    
    async with db_pool.acquire() as conn:
        records = await conn.fetch('''
            SELECT status, response_time, error, checked_at
            FROM health_checks
            WHERE service_name = $1 AND checked_at > $2
            ORDER BY checked_at DESC
            LIMIT 1000
        ''', name, since)
    
    if not records:
        api_requests.labels(method="GET", endpoint="/health-history/{name}", status="404").inc()
        raise HTTPException(status_code=404, detail=f"No health history found for service {name}")
    
    history = [
        {
            "status": record['status'],
            "response_time": record['response_time'],
            "error": record['error'],
            "checked_at": record['checked_at'].isoformat()
        }
        for record in records
    ]
    
    return {"service": name, "history": history, "count": len(history)}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
