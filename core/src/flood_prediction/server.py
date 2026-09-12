import json
import os
import uuid
import jwt
import requests
import time
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Annotated, Dict, Any, List

import rq
from fastapi.responses import FileResponse, StreamingResponse
from fastapi import (
    FastAPI,
    HTTPException,
    Depends,
    Request,
    Response
)
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from redis import Redis
from rq.exceptions import InvalidJobOperationError
from pydantic import BaseModel
from .settings import settings, server_dir, log
from .settings import configure_logging, initialize_app
from . import db
from .api import llm_call_stream, get_available_llm_models, get_provider_info, get_all_providers_info
from .evaluator import evaluator, EvaluationResult
from .data_sources import fetch_and_update_usgs_data, fetch_and_store_imd_alerts
from .agents import AgentManager
from .agents.nat_base import FloodPredictionRunner

configure_logging()
initialize_app()
# Set environment variable to fix fork() issues on macOS
os.environ.setdefault('OBJC_DISABLE_INITIALIZE_FORK_SAFETY', 'YES')

# Redis and job queue setup
_redis = Redis.from_url(settings.redis_url)
_job_queue = rq.Queue(connection=_redis, default_timeout=settings.job_timeout)

# Database setup
_db_path = Path(settings.app_data_dir) / "flood_prediction.db"
db.init_app_db(str(_db_path))

# Initialize Agent Manager
_agent_manager = None
if settings.agents_enabled:
    _agent_manager = AgentManager(str(_db_path))
    log.info("AgentManager initialized")

# Initialize NAT Agent Runner
_nat_runner = None
try:
    _nat_runner = FloodPredictionRunner()
    log.info("NAT FloodPredictionRunner initialized")
except Exception as e:
    log.warning(f"NAT FloodPredictionRunner not available: {e}")

# Lifespan context manager for startup/shutdown events
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifespan events"""
    # Startup
    log.info("Application starting up...")
    
    # Start AI agents if enabled and auto-start is configured
    if _agent_manager and settings.agents_auto_start:
        try:
            log.info("Auto-starting AI agents...")
            await _agent_manager.start_all_agents()
            log.info("All AI agents started successfully")
        except Exception as e:
            log.error(f"Failed to auto-start AI agents: {str(e)}")
    
    # Generate initial insights if agent manager is available
    if _agent_manager:
        try:
            log.info("Generating initial agent insights...")
            await _agent_manager._generate_initial_insights()
            log.info("Initial agent insights generated successfully")
        except Exception as e:
            log.error(f"Failed to generate initial agent insights: {str(e)}")
    
    yield
    
    # Shutdown
    log.info("Application shutting down...")
    
    # Stop AI agents if running
    if _agent_manager:
        try:
            log.info("Stopping AI agents...")
            await _agent_manager.stop_all_agents()
            log.info("All AI agents stopped successfully")
        except Exception as e:
            log.error(f"Failed to stop AI agents: {str(e)}")

app = FastAPI(title="Generic API Server", version="1.0.0", lifespan=lifespan)
security = HTTPBearer()

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request timing and logging middleware
# @app.middleware("http")
# async def logging_middleware(request: Request, call_next):
#     start_time = time.time()
    
#     # Log request start
#     log.info("Request started", extra={
#         "method": request.method,
#         "url": str(request.url),
#         "client_ip": request.client.host if request.client else "unknown",
#         "user_agent": request.headers.get("user-agent", ""),
#         "request_id": str(uuid.uuid4())[:8],
#     })
    
#     # Process request
#     try:
#         response = await call_next(request)
        
#         # Calculate duration
#         process_time = time.time() - start_time
#         duration_ms = round(process_time * 1000, 2)
        
#         # Log request completion
#         log.info("Request completed", extra={
#             "method": request.method,
#             "url": str(request.url),
#             "status_code": response.status_code,
#             "duration_ms": duration_ms,
#             "client_ip": request.client.host if request.client else "unknown",
#         })
        
#         # Add timing header
#         response.headers["X-Process-Time"] = str(process_time)
        
#         return response
        
#     except Exception as e:
#         # Calculate duration for failed requests
#         process_time = time.time() - start_time
#         duration_ms = round(process_time * 1000, 2)
        
#         # Log request error
#         log.error("Request failed", extra={
#             "method": request.method,
#             "url": str(request.url),
#             "duration_ms": duration_ms,
#             "error": str(e),
#             "client_ip": request.client.host if request.client else "unknown",
#         })
        
#         raise e

# Cache for JWKS (JSON Web Key Set)
_jwks_cache: Dict = {}


# =============================================================================
# Authentication
# =============================================================================

async def get_jwks():
    """Fetch JSON Web Key Set from the OIDC provider"""
    if not _jwks_cache.get("keys"):
        jwks_uri = f"{settings.oidc_authority}/.well-known/openid-configuration"
        try:
            openid_config = requests.get(jwks_uri).json()
            jwks_url = openid_config.get("jwks_uri")
            if jwks_url:
                jwks = requests.get(jwks_url).json()
                _jwks_cache["keys"] = jwks.get("keys", [])
        except Exception as e:
            print(f"Error fetching JWKS: {e}")
    return _jwks_cache.get("keys", [])


def get_token_endpoint(auth_url: str) -> str:
    """Get token endpoint from OIDC discovery"""
    try:
        discovery_url = f"{auth_url}/.well-known/openid-configuration"
        response = requests.get(discovery_url)
        return response.json().get("token_endpoint")
    except Exception:
        return f"{auth_url}/oauth/token"


async def refresh_access_token(user_id: str) -> Optional[str]:
    """Attempt to refresh the access token using the stored refresh token"""
    refresh_token = _redis.get(f"refresh_token:{user_id}")
    if not refresh_token:
        print(f"No refresh token found for user {user_id}")
        return None

    try:
        refresh_token = refresh_token.decode('utf-8')
        token_endpoint = get_token_endpoint(settings.oidc_authority)

        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.oidc_client_id,
        }

        if settings.oidc_client_secret:
            data["client_secret"] = settings.oidc_client_secret

        response = requests.post(token_endpoint, headers=headers, data=data)
        if response.status_code == 200:
            token_data = response.json()
            if "access_token" in token_data:
                # Store the new access token
                expires_in = token_data.get("expires_in", 300)
                access_token = token_data["access_token"]
                _redis.setex(f"access_token:{user_id}", expires_in, access_token)

                # Update refresh token if provided
                if "refresh_token" in token_data:
                    _redis.setex(f"refresh_token:{user_id}", 86400, token_data["refresh_token"])

                print(f"Successfully refreshed access token for user {user_id}")
                return access_token

        print(f"Failed to refresh token: {response.status_code}, {response.text}")
        return None
    except Exception as e:
        print(f"Error refreshing token: {str(e)}")
        return None


async def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
) -> str:
    """Validate JWT token and extract user information with auto-refresh"""
    token = credentials.credentials

    if settings.oidc_authority == "":  # local development mode
        if token == "local-token":
            return "local-user"
        raise HTTPException(status_code=401, detail="Invalid local token")

    try:
        # Simple decode without verification (for development)
        # In production, you should properly verify the token signature
        decoded = jwt.decode(token, options={"verify_signature": False})

        # Extract user identifier
        user_id = decoded.get(settings.oidc_user_id_claim)
        if not user_id:
            raise HTTPException(
                status_code=401,
                detail=f"Invalid token: missing {settings.oidc_user_id_claim} claim"
            )

        # Store the token temporarily
        _redis.setex(f"access_token:{user_id}", 300, token)
        return user_id

    except jwt.ExpiredSignatureError:
        try:
            decoded = jwt.decode(token, options={"verify_signature": False, "verify_exp": False})
            user_id = decoded.get(settings.oidc_user_id_claim)

            if user_id:
                print(f"Token expired for user {user_id}, attempting refresh")
                new_token = await refresh_access_token(user_id)
                if new_token:
                    return user_id
        except Exception as e:
            print(f"Error handling expired token: {str(e)}")

        raise HTTPException(status_code=401, detail="Token has expired and refresh failed")

    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")


# Define the dependency for getting authenticated user ID
UserID = Annotated[str, Depends(get_current_user)]


# =============================================================================
# Utility Functions
# =============================================================================

def _api(url: str) -> str:
    """Helper to construct API URLs"""
    return f"{settings.base_url}api/{url}"


def _format_utc(dt: datetime) -> str:
    """Format datetime as UTC string"""
    return dt.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def uid() -> str:
    """Generate a unique ID"""
    return str(uuid.uuid4())


def get_user_access_token(user_id: str) -> Optional[bytes]:
    """Get stored access token for user"""
    return _redis.get(f"access_token:{user_id}")


def get_user_refresh_token(user_id: str) -> Optional[bytes]:
    """Get stored refresh token for user"""
    return _redis.get(f"refresh_token:{user_id}")


# =============================================================================
# Background Job Processing
# =============================================================================

class JobContext:
    """Context manager for background jobs"""
    def __init__(self, job: Optional[rq.job.Job] = None):
        self.job = job or rq.get_current_job()
        self._last_checkpoint_time = datetime.now()

    @property
    def status(self) -> Optional[str]:
        return self.job.get_meta(refresh=True).get("status")

    @status.setter
    def status(self, message: str):
        print(f"Job status: {message}")
        self.job.meta["status"] = message
        self.job.save_meta()

    @property
    def aborted(self) -> bool:
        return self.job.get_meta(refresh=True).get("abort") == 1

    def abort(self):
        self.job.meta["abort"] = 1
        self.job.save_meta()

    def checkpoint(self):
        """Check if job should be aborted"""
        now = datetime.now()
        if (now - self._last_checkpoint_time).total_seconds() > 5:
            self._last_checkpoint_time = now
            if self.aborted:
                raise Exception("Job was aborted")

    def delete(self):
        self.job.delete()


def sample_background_task(user_id: str, task_data: Dict[str, Any]):
    """Sample background task - customize this for your needs"""
    ctx = JobContext()
    try:
        ctx.status = "Starting task..."
        
        # Simulate some work
        import time
        for i in range(10):
            ctx.checkpoint()  # Check for abort
            time.sleep(1)
            ctx.status = f"Processing step {i+1}/10"
        
        ctx.status = "Task completed successfully"
        return {"result": "success", "processed_data": task_data}
        
    except Exception as e:
        ctx.status = f"Task failed: {str(e)}"
        raise e


def update_flood_data_task(user_id: str = "system", site_codes: Optional[List[str]] = None):
    """Background task to update flood prediction data from USGS API"""
    ctx = JobContext()
    try:
        ctx.status = "Starting River discharge data update..."
        
        # Use the global database path
        db_path = str(_db_path)
        
        ctx.status = "Fetching river discharge data from Open-Meteo API..."
        results = fetch_and_update_usgs_data(db_path, site_codes)
        
        ctx.checkpoint()  # Check for abort
        
        if results["success"]:
            ctx.status = f"Successfully updated {results['updated_count']} watersheds"
            log.info("River discharge data update job completed", **results)
        else:
            ctx.status = f"Data update failed: {results['message']}"
            log.error("River discharge data update job failed", **results)
        
        return results
        
    except Exception as e:
        error_msg = f"River discharge data update task failed: {str(e)}"
        ctx.status = error_msg
        log.error("River discharge data update task error", error=str(e))
        raise Exception(error_msg)


# =============================================================================
# API Models
# =============================================================================

class JobRequest(BaseModel):
    """Request model for creating a job"""
    name: str
    data: Dict[str, Any] = {}


class JobResponse(BaseModel):
    """Response model for job creation"""
    job_id: str


class Job(BaseModel):
    """Job status model"""
    id: str
    state: str
    aborted: bool
    name: str
    status: Optional[str] = None
    enqueued_at: Optional[str] = None
    started_at: Optional[str] = None
    ended_at: Optional[str] = None


class JobListResponse(BaseModel):
    """Response model for job list"""
    jobs: list[Job]


class JobUpdateRequest(BaseModel):
    """Request model for updating a job"""
    name: Optional[str] = None
    priority: Optional[int] = None


class RefreshTokenRequest(BaseModel):
    """Request model for refresh token"""
    refresh_token: str


class LogEntry(BaseModel):
    """Frontend log entry"""
    timestamp: str
    level: str
    message: str
    data: Optional[Dict[str, Any]] = None
    component: Optional[str] = None
    userId: Optional[str] = None
    sessionId: Optional[str] = None
    duration: Optional[float] = None
    url: Optional[str] = None
    userAgent: Optional[str] = None


class AnalyticsEvent(BaseModel):
    """Analytics event from frontend"""
    event_type: str
    event_data: Dict[str, Any]
    timestamp: str
    userId: Optional[str] = None
    sessionId: Optional[str] = None


# =============================================================================
# Dashboard Models  
# =============================================================================

class DashboardSummary(BaseModel):
    """Dashboard summary statistics"""
    total_watersheds: int
    active_alerts: int
    high_risk_watersheds: int
    moderate_risk_watersheds: int
    low_risk_watersheds: int
    last_updated: str


class Watershed(BaseModel):
    """Watershed information"""
    id: int
    name: str
    region: Optional[str] = "Ganga Basin"
    region_code: Optional[str] = "IN-GANGA"
    location_lat: Optional[float] = None
    location_lng: Optional[float] = None
    basin_size_sqmi: Optional[float] = None
    current_streamflow_cfs: float
    current_risk_level: str
    risk_score: float
    flood_stage_cfs: Optional[float] = None
    trend: Optional[str] = None
    trend_rate_cfs_per_hour: Optional[float] = None
    last_updated: str


class Alert(BaseModel):
    """Alert information"""
    alert_id: int
    alert_type: str
    watershed: str
    message: str
    severity: str
    issued_time: str
    expires_time: Optional[str] = None
    affected_counties: Optional[List[str]] = None
    data_source: Optional[str] = "sample"


class RiskTrendPoint(BaseModel):
    """Risk trend data point"""
    time: str
    risk: float
    watersheds: int


class DashboardData(BaseModel):
    """Complete dashboard data"""
    summary: DashboardSummary
    watersheds: List[Watershed]
    alerts: List[Alert]
    risk_trends: List[RiskTrendPoint]


# =============================================================================
# Helper Functions
# =============================================================================

def _make_job_id(user_id: str, job_id: str) -> str:
    """Create a composite job ID that includes the user ID"""
    return f"{user_id}/{job_id}"


def _parse_job_id(composite_id: str) -> tuple[str, str]:
    """Parse composite job ID to extract user ID and job ID"""
    user_id, job_id = composite_id.split("/", maxsplit=1)
    return user_id, job_id


def _is_job_owned_by(composite_id: str, expected_user_id: str) -> bool:
    """Check if a job is owned by the expected user"""
    user_id, _ = _parse_job_id(composite_id)
    return user_id == expected_user_id


def _to_job_status(job: rq.job.Job) -> Job:
    """Convert RQ job to our Job model"""
    meta = job.get_meta()
    _, job_id = _parse_job_id(job.id)
    return Job(
        id=job_id,
        state=job.get_status(),
        aborted=meta.get("abort") == 1,
        name=meta.get("name", "Unknown"),
        status=meta.get("status"),
        enqueued_at=_format_utc(job.enqueued_at) if job.enqueued_at else None,
        started_at=_format_utc(job.started_at) if job.started_at else None,
        ended_at=_format_utc(job.ended_at) if job.ended_at else None,
    )


# =============================================================================
# API Endpoints
# =============================================================================

@app.get(_api("config"))
async def get_config():
    config = dict(
        oidc_authority=settings.oidc_authority,
        oidc_client_id=settings.oidc_client_id,
        oidc_client_secret=settings.oidc_client_secret,
        oidc_scope=settings.oidc_scope,
        base_url=settings.base_url,
    )

    headers = {
        "Cache-Control": "no-store, max-age=0",
        "Content-Type": "application/json",
    }

    return Response(
        content=json.dumps(config), media_type="application/json", headers=headers
    )


@app.post(_api("logs"))
async def receive_frontend_logs(request: LogEntry):
    """Receive logs from frontend"""
    try:
        # Log frontend entry with backend logger
        log_level = getattr(log, request.level.lower(), log.info)
        log_level(f"Frontend: {request.message}", extra={
            "component": request.component,
            "user_id": request.userId,
            "session_id": request.sessionId,
            "frontend_url": request.url,
            "duration_ms": request.duration,
            "frontend_data": request.data,
            "source": "frontend"
        })
        
        # Store in Redis for real-time monitoring (optional)
        if settings.enable_metrics:
            log_key = f"frontend_logs:{request.sessionId}"
            _redis.lpush(log_key, json.dumps(request.dict()))
            _redis.expire(log_key, 3600)  # Keep for 1 hour
            
        return {"status": "logged"}
        
    except Exception as e:
        log.error(f"Failed to process frontend log: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process log")


@app.post(_api("analytics"))
async def receive_analytics(request: AnalyticsEvent):
    """Receive analytics events from frontend"""
    try:
        # Log analytics event
        log.info(f"Analytics: {request.event_type}", extra={
            "user_id": request.userId,
            "session_id": request.sessionId,
            "event_data": request.event_data,
            "source": "frontend_analytics"
        })
        
        # Store analytics data (you might want to use a dedicated analytics service)
        if settings.enable_metrics:
            analytics_key = f"analytics:{request.event_type}"
            _redis.lpush(analytics_key, json.dumps(request.dict()))
            _redis.expire(analytics_key, 86400)  # Keep for 24 hours
            
        return {"status": "tracked"}
        
    except Exception as e:
        log.error(f"Failed to process analytics event: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process analytics")


@app.post(_api("auth/refresh"))
async def refresh_token(
    user_id: UserID,
    request: RefreshTokenRequest,
):
    """Store and use refresh token to get new access token"""
    refresh_token = request.refresh_token
    if not refresh_token:
        raise HTTPException(status_code=400, detail="Missing refresh token")

    # Store refresh token
    _redis.setex(f"refresh_token:{user_id}", 86400, refresh_token)
    print(f"Stored refresh token for user {user_id}")

    try:
        token_endpoint = get_token_endpoint(settings.oidc_authority)
        headers = {"Content-Type": "application/x-www-form-urlencoded"}
        data = {
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
            "client_id": settings.oidc_client_id,
        }

        if settings.oidc_client_secret:
            data["client_secret"] = settings.oidc_client_secret

        response = requests.post(token_endpoint, headers=headers, data=data)
        if response.status_code == 200:
            token_data = response.json()
            if "access_token" in token_data:
                expires_in = token_data.get("expires_in", 300)
                _redis.setex(
                    f"access_token:{user_id}", 
                    expires_in,
                    token_data["access_token"]
                )

                if "refresh_token" in token_data:
                    _redis.setex(
                        f"refresh_token:{user_id}", 
                        86400,
                        token_data["refresh_token"]
                    )

                return {"status": "success", "message": "Tokens refreshed successfully"}

        print(f"Failed to refresh token: {response.status_code}")
    except Exception as e:
        print(f"Error refreshing token: {str(e)}")

    return {"status": "stored", "message": "Refresh token stored"}


@app.post(_api("jobs"), response_model=JobResponse)
async def create_job(user_id: UserID, request: JobRequest):
    """Create a new background job"""
    job_id = _make_job_id(user_id, uid())
    
    meta = {"name": request.name}
    
    _job_queue.enqueue(
        sample_background_task,
        job_id=job_id,
        timeout=-1,  # No timeout
        ttl=604800,  # 1 week TTL
        failure_ttl=604800,  # 1 week failure TTL
        meta=meta,
        kwargs={
            "user_id": user_id,
            "task_data": request.data,
        },
    )
    
    _, simple_job_id = _parse_job_id(job_id)
    return JobResponse(job_id=simple_job_id)


@app.get(_api("jobs"), response_model=JobListResponse)
async def list_jobs(user_id: UserID):
    """Get all jobs for the current user"""
    # Get jobs from different registries
    started_job_ids = _job_queue.started_job_registry.get_job_ids()
    failed_job_ids = _job_queue.failed_job_registry.get_job_ids()
    queued_job_ids = _job_queue.job_ids
    finished_job_ids = _job_queue.finished_job_registry.get_job_ids()
    
    all_ids = started_job_ids + failed_job_ids + queued_job_ids + finished_job_ids
    
    # Filter jobs owned by current user
    job_ids = [job_id for job_id in all_ids if _is_job_owned_by(job_id, user_id)]
    jobs = [_job_queue.fetch_job(job_id) for job_id in job_ids if _job_queue.fetch_job(job_id)]
    
    return JobListResponse(jobs=[_to_job_status(job) for job in jobs])


@app.get(_api("jobs/{job_id}"), response_model=Job)
async def get_job(user_id: UserID, job_id: str):
    """Get a specific job by ID"""
    full_job_id = _make_job_id(user_id, job_id)
    job = _job_queue.fetch_job(full_job_id)
    
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return _to_job_status(job)


@app.patch(_api("jobs/{job_id}"))
async def update_job(user_id: UserID, job_id: str, request: JobUpdateRequest):
    """Update job metadata"""
    full_job_id = _make_job_id(user_id, job_id)
    job = _job_queue.fetch_job(full_job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Update job metadata
    if request.name is not None:
        job.meta["name"] = request.name
        job.save_meta()
    
    return {"status": "success", "message": "Job updated"}


@app.delete(_api("jobs/{job_id}"))
async def delete_job(user_id: UserID, job_id: str):
    """Delete a job"""
    full_job_id = _make_job_id(user_id, job_id)
    job = _job_queue.fetch_job(full_job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    status = job.get_status()
    if status == "started":
        # Abort running job
        JobContext(job).abort()
        return {"status": "success", "message": "Job aborted"}
    
    try:
        job.delete()
        return {"status": "success", "message": "Job deleted"}
    except InvalidJobOperationError as e:
        message = f"Failed deleting job: {e}"
        print(message)
        raise HTTPException(status_code=500, detail=message)


# =============================================================================
# AI Chat API Models
# =============================================================================

class ChatMessage(BaseModel):
    """Chat message model"""
    message: str
    watershed_id: Optional[int] = None
    context: Optional[Dict[str, Any]] = None
    use_agent: bool = False
    model: Optional[str] = None

class ChatResponse(BaseModel):
    """AI chat response model"""
    response: str
    confidence: float
    recommendations: List[str] = []
    timestamp: str

# =============================================================================
# NAT Agent Chat API Models
# =============================================================================

class NATChatMessage(BaseModel):
    """NAT agent chat message model"""
    message: str
    agent_type: str = "risk_analyzer"  # data_collector, risk_analyzer, emergency_responder, predictor, all
    location: Optional[str] = "India"
    forecast_hours: Optional[int] = 24
    scenario: Optional[str] = "routine_check"
    custom_prompt: Optional[str] = None

class NATChatResponse(BaseModel):
    """NAT agent chat response model"""
    output: str
    agent_type: str
    status: str
    logs: List[Dict[str, Any]] = []
    timestamp: str

# =============================================================================
# Analytics API Models
# =============================================================================

class AnalyticsTimeRange(BaseModel):
    """Analytics time range request"""
    range: str = "7d"  # 7d, 30d, 90d
    metric: str = "risk_score"  # risk_score, flow, alerts

class HistoricalDataPoint(BaseModel):
    """Historical data point"""
    date: str
    time: str
    avg_risk_score: float
    avg_flow: float
    high_risk_count: int
    alerts_count: int

class RiskDistribution(BaseModel):
    """Risk distribution data"""
    name: str
    value: int
    color: str
    percentage: int

class WatershedComparison(BaseModel):
    """Watershed comparison data"""
    name: str
    risk_score: float
    flow_ratio: float
    current_flow: float

class FlowComparison(BaseModel):
    """Flow vs flood stage comparison"""
    name: str
    current_flow: float
    flood_stage: float
    capacity_used: float

class AnalyticsData(BaseModel):
    """Complete analytics data"""
    summary: Dict[str, Any]
    historical_data: List[HistoricalDataPoint]
    risk_distribution: List[RiskDistribution]
    watershed_comparison: List[WatershedComparison]
    flow_comparison: List[FlowComparison]

# =============================================================================
# Region API Models
# =============================================================================

class Region(BaseModel):
    """Region information"""
    code: str
    name: str
    description: str
    center_lat: float
    center_lng: float
    zoom: int
    watershed_count: int

# =============================================================================
# India Real-Time Context Builder (for chatbot)
# =============================================================================

def _build_india_context(message: str, db_path: str) -> str:
    """Build a rich real-time India flood context for the chatbot."""
    try:
        live_watersheds = db.get_watersheds(db_path)
        high_risk = [w for w in live_watersheds if w.get('risk_score', 0) >= 6]
        critical_risk = [w for w in live_watersheds if w.get('risk_score', 0) >= 8]
        alerts = db.get_active_alerts(db_path, limit=10)
        summary = db.get_dashboard_summary(db_path)

        high_risk_lines = "\n".join([
            f"• {w['name']} — Risk {w['risk_score']:.1f}/10, Flow {w['current_streamflow_cfs']:,.0f} CFS, Trend: {w.get('trend','stable')}"
            for w in high_risk[:8]
        ]) or "• No high risk areas currently"

        alert_lines = "\n".join([
            f"• {a.get('alert_type','Alert')} at {a.get('watershed','Unknown')} — {a.get('severity','?')} severity"
            for a in alerts[:5]
        ]) or "• No active alerts"

        india_context = f"""You are an expert India Flood Intelligence AI with access to LIVE data.

=== REAL-TIME INDIA FLOOD STATUS ===
Monitored river sites: {summary.get('total_watersheds', 0)}
Active flood alerts: {summary.get('active_alerts', 0)}
High risk sites (score ≥6): {len(high_risk)}
Critical sites (score ≥8): {len(critical_risk)}

HIGH RISK AREAS RIGHT NOW:
{high_risk_lines}

ACTIVE ALERTS:
{alert_lines}

DATA: Open-Meteo GloFAS API (updates every hour) | 45+ India river sites
IMD THRESHOLDS: Heavy Rain ≥64.5mm/day | Very Heavy ≥115.5mm/day | Extreme ≥204.5mm/day
BASINS: Ganga, Brahmaputra, Mahanadi, Godavari, Krishna, Narmada, Kaveri, Indus
EMERGENCY: NDMA 1078 | IMD: mausam.imd.gov.in | CWC: cwc.gov.in

Answer using real-time data above. Be specific and fast. For area-specific risk, reference the high risk list.

User Question: {message}"""
        return india_context
    except Exception:
        return f"""You are an India Flood Intelligence AI assistant.
Answer flood, weather and river risk questions for India using IMD/CWC/Open-Meteo data.
NDMA emergency helpline: 1078.

User Question: {message}"""


# =============================================================================
# Dashboard API Endpoints
# =============================================================================

@app.get(_api("regions"), response_model=List[Region])
async def get_available_regions():
    """Get list of all available regions"""
    try:
        from .data_sources import get_available_regions
        regions = get_available_regions()
        return [Region(**r) for r in regions]
    except Exception as e:
        log.error(f"Failed to get regions: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load regions")


@app.get(_api("regions/{region_code}"), response_model=Region)
async def get_region_details(region_code: str):
    """Get details for a specific region"""
    try:
        from .data_sources import get_region_config
        config = get_region_config(region_code)
        if not config:
            raise HTTPException(status_code=404, detail=f"Region {region_code} not found")

        return Region(
            code=config["code"],
            name=config["name"],
            description=config["description"],
            center_lat=config["center_lat"],
            center_lng=config["center_lng"],
            zoom=config["zoom"],
            watershed_count=len(config["sites"])
        )
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to get region details: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load region details")


@app.get(_api("dashboard"), response_model=DashboardData)
async def get_dashboard_data(response: Response, region: Optional[str] = None):
    """Get complete dashboard data, optionally filtered by region"""
    try:
        # Set cache control headers to prevent caching
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"

        # Get dashboard data (no auto-population of sample data)
        summary = db.get_dashboard_summary(str(_db_path))
        watersheds = db.get_watersheds(str(_db_path), region_code=region)

        # Initialize watersheds from USGS if database is empty
        if len(watersheds) == 0:
            from .data_sources import create_watersheds_from_usgs_sites
            log.info(f"No watersheds found for region {region or 'IN-GANGA'}, initializing from India river sites...")
            result = create_watersheds_from_usgs_sites(str(_db_path), limit=12, region_code=region or "IN-GANGA")
            if result['created_count'] > 0:
                watersheds = db.get_watersheds(str(_db_path), region_code=region)
                summary = db.get_dashboard_summary(str(_db_path))

        alerts = db.get_active_alerts(str(_db_path), limit=100)  # Increased limit to fetch more alerts
        risk_trends = db.get_risk_trend_data(str(_db_path))

        # Generate sample risk trend data if none exists
        if not risk_trends:
            # Pull from real risk_trends table instead of random values
            real_trends = db.get_historical_analytics_data(str(_db_path), time_range="7d")
            risk_trends = [
                {"time": r["time"], "risk": r["avg_risk_score"], "watersheds": r["high_risk_count"]}
                for r in real_trends
            ]

        return DashboardData(
            summary=DashboardSummary(**summary),
            watersheds=[Watershed(**w) for w in watersheds],
            alerts=[Alert(**a) for a in alerts],
            risk_trends=[RiskTrendPoint(**r) for r in risk_trends]
        )

    except Exception as e:
        log.error(f"Failed to get dashboard data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load dashboard data")


@app.get(_api("dashboard/summary"), response_model=DashboardSummary)
async def get_dashboard_summary():
    """Get dashboard summary statistics"""
    try:
        summary = db.get_dashboard_summary(str(_db_path))
        if summary['total_watersheds'] == 0:
            # Initialize watersheds from USGS if database is empty (no sample data)
            from .data_sources import create_watersheds_from_usgs_sites
            log.info("No watersheds found, initializing from USGS sites...")
            create_watersheds_from_usgs_sites(str(_db_path), limit=12)
            summary = db.get_dashboard_summary(str(_db_path))

        return DashboardSummary(**summary)
        
    except Exception as e:
        log.error(f"Failed to get dashboard summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load dashboard summary")


@app.get(_api("watersheds"), response_model=List[Watershed])
async def get_watersheds(region: Optional[str] = None):
    """Get all watersheds, optionally filtered by region"""
    try:
        watersheds = db.get_watersheds(str(_db_path), region_code=region)
        return [Watershed(**w) for w in watersheds]

    except Exception as e:
        log.error(f"Failed to get watersheds: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load watersheds")


@app.get(_api("alerts"), response_model=List[Alert])
async def get_alerts(limit: int = 100, response: Response = None):
    """Get active alerts"""
    try:
        # Set cache control headers to prevent caching
        if response:
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"

        alerts = db.get_active_alerts(str(_db_path), limit)
        return [Alert(**a) for a in alerts]

    except Exception as e:
        log.error(f"Failed to get alerts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load alerts")


@app.post(_api("alerts/refresh"))
async def refresh_alerts(user_id: UserID):
    """Manually trigger IMD/CWC alerts refresh from real-time API"""
    try:
        if not settings.enable_real_time_data:
            raise HTTPException(status_code=400, detail="Real-time data integration is disabled")

        # Clear expired alerts first
        db.clear_expired_alerts(str(_db_path))

        # Fetch and store IMD/CWC alerts
        imd_results = fetch_and_store_imd_alerts(str(_db_path))

        return {
            "status": "success" if imd_results["success"] else "partial",
            "message": imd_results["message"],
            "alerts_fetched": imd_results.get("alerts_fetched", 0),
            "alerts_stored": imd_results.get("alerts_stored", 0),
            "alerts_skipped": imd_results.get("alerts_skipped", 0),
            "timestamp": imd_results.get("timestamp")
        }

    except Exception as e:
        log.error(f"Failed to refresh alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to refresh alerts: {str(e)}")


@app.post(_api("alerts/clear-sample"))
async def clear_sample_alerts_endpoint():
    """Clear all sample alerts from the database"""
    try:
        deleted_count = db.clear_sample_alerts(str(_db_path))
        return {
            "status": "success",
            "message": f"Cleared {deleted_count} sample alerts",
            "deleted_count": deleted_count
        }
    except Exception as e:
        log.error(f"Failed to clear sample alerts: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to clear sample alerts: {str(e)}")


@app.post(_api("dashboard/populate-sample-data"))
async def populate_sample_data():
    """Populate database with sample flood prediction data"""
    try:
        db.populate_sample_data(str(_db_path))
        return {"status": "success", "message": "Sample data populated"}

    except Exception as e:
        log.error(f"Failed to populate sample data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to populate sample data")


@app.post(_api("dashboard/refresh-river-data"))
async def refresh_usgs_data(user_id: UserID):
    """Manually trigger River Discharge Data Refresh"""
    try:
        if not settings.enable_real_time_data:
            raise HTTPException(status_code=400, detail="Real-time data integration is disabled")
        
        # Create background job for River discharge data update
        job_id = _make_job_id(user_id, uid())
        
        meta = {"name": "River Discharge Data Refresh"}
        
        job = _job_queue.enqueue(
            update_flood_data_task,
            job_id=job_id,
            timeout=600,  # 10 minutes timeout
            ttl=3600,  # 1 hour TTL
            failure_ttl=3600,  # 1 hour failure TTL
            meta=meta,
            kwargs={
                "user_id": user_id,
                "site_codes": None  # Use default major river sites
            },
        )
        
        _, simple_job_id = _parse_job_id(job_id)
        return {
            "status": "success", 
            "message": "River Discharge Data Refresh started",
            "job_id": simple_job_id
        }
        
    except Exception as e:
        log.error(f"Failed to start River Discharge Data Refresh: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start River Discharge Data Refresh")


@app.post(_api("dashboard/update-single-watershed/{watershed_id}"))
async def update_single_watershed_data(watershed_id: int, user_id: UserID):
    """Update a single watershed with latest USGS data"""
    try:
        if not settings.enable_real_time_data:
            raise HTTPException(status_code=400, detail="Real-time data integration is disabled")
        
        # Get watershed info
        watersheds = db.get_watersheds(str(_db_path))
        target_watershed = next((w for w in watersheds if w['id'] == watershed_id), None)
        
        if not target_watershed:
            raise HTTPException(status_code=404, detail="Watershed not found")
        
        # Extract river site code — works for India sites (river_site_code column)
        # or falls back to parsing the watershed name
        site_code = target_watershed.get('river_site_code')
        if not site_code:
            # Try to extract any site-code-like token from the name
            import re
            # India site codes look like "brahmaputra_guwahati" or similar
            m = re.search(r'\(([A-Z0-9_\-]+)\)', target_watershed['name'])
            site_code = m.group(1) if m else None

        if not site_code:
            # No site code — trigger a full data refresh for just this watershed
            # by updating it directly from the Open-Meteo API
            from .data_sources import fetch_and_update_usgs_data
            results = fetch_and_update_usgs_data(str(_db_path), site_codes=None)
            return {
                "status": "refreshed",
                "watershed_id": watershed_id,
                "watershed_name": target_watershed['name'],
                "message": "Full data refresh triggered (no specific site code available)",
                "results": results,
            }
        
        # Create background job for single watershed update
        job_id = _make_job_id(user_id, uid())
        
        meta = {"name": f"Update Watershed {target_watershed['name']}"}
        
        job = _job_queue.enqueue(
            update_flood_data_task,
            job_id=job_id,
            timeout=300,  # 5 minutes timeout
            ttl=1800,  # 30 minutes TTL
            failure_ttl=1800,  # 30 minutes failure TTL
            meta=meta,
            kwargs={
                "user_id": user_id,
                "site_codes": [site_code]
            },
        )
        
        _, simple_job_id = _parse_job_id(job_id)
        return {
            "status": "success",
            "message": f"Watershed {target_watershed['name']} update started",
            "job_id": simple_job_id
        }
        
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to update single watershed: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to update watershed data")


# =============================================================================
# Analytics API Endpoints
# =============================================================================

@app.get(_api("analytics"), response_model=AnalyticsData)
async def get_analytics_data(
    time_range: str = "7d",
    metric: str = "risk_score"
):
    """Get complete analytics data"""
    try:
        # Initialize watersheds from USGS if database is empty (no sample data)
        summary = db.get_dashboard_summary(str(_db_path))
        if summary['total_watersheds'] == 0:
            from .data_sources import create_watersheds_from_usgs_sites
            log.info("No watersheds found, initializing from USGS sites...")
            create_watersheds_from_usgs_sites(str(_db_path), limit=12)

        # Get analytics data
        analytics_data = db.get_analytics_data(str(_db_path), time_range, metric)
        
        return AnalyticsData(**analytics_data)
        
    except Exception as e:
        log.error(f"Failed to get analytics data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load analytics data")

@app.get(_api("analytics/historical"), response_model=List[HistoricalDataPoint])
async def get_historical_data(
    time_range: str = "7d"
):
    """Get historical trend data"""
    try:
        historical_data = db.get_historical_analytics_data(str(_db_path), time_range)
        return [HistoricalDataPoint(**point) for point in historical_data]
        
    except Exception as e:
        log.error(f"Failed to get historical data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load historical data")

@app.get(_api("analytics/risk-distribution"), response_model=List[RiskDistribution])
async def get_risk_distribution():
    """Get current risk distribution"""
    try:
        distribution = db.get_risk_distribution_data(str(_db_path))
        return [RiskDistribution(**item) for item in distribution]
        
    except Exception as e:
        log.error(f"Failed to get risk distribution: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load risk distribution")

@app.get(_api("analytics/watershed-comparison"), response_model=List[WatershedComparison])
async def get_watershed_comparison():
    """Get watershed comparison data"""
    try:
        comparison = db.get_watershed_comparison_data(str(_db_path))
        return [WatershedComparison(**item) for item in comparison]
        
    except Exception as e:
        log.error(f"Failed to get watershed comparison: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load watershed comparison")

@app.get(_api("analytics/flow-comparison"), response_model=List[FlowComparison])
async def get_flow_comparison():
    """Get flow vs flood stage comparison"""
    try:
        comparison = db.get_flow_comparison_data(str(_db_path))
        return [FlowComparison(**item) for item in comparison]
        
    except Exception as e:
        log.error(f"Failed to get flow comparison: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load flow comparison")

@app.get(_api("dashboard/insights"))
async def get_dashboard_insights():
    """Get comprehensive dashboard insights and metrics"""
    try:
        # Get base data
        summary = db.get_dashboard_summary(str(_db_path))
        watersheds = db.get_watersheds(str(_db_path))
        analytics_data = db.get_analytics_data(str(_db_path), '24h', 'risk_score')
        
        # Calculate additional insights
        usgs_stations = len([w for w in watersheds if w.get('data_source') == 'usgs'])
        rising_trend_count = len([w for w in watersheds if w.get('trend') == 'rising'])
        average_flow = sum([w.get('current_streamflow_cfs', 0) for w in watersheds]) / len(watersheds) if watersheds else 0
        
        # Calculate model accuracy based on data quality
        total_stations = len(watersheds)
        accuracy_base = 75.0  # Base accuracy
        if usgs_stations > 0:
            accuracy_boost = min((usgs_stations / total_stations) * 15, 15)  # Up to 15% boost for real-time data
            model_accuracy = accuracy_base + accuracy_boost
        else:
            model_accuracy = accuracy_base
        
        # Confidence level based on data availability and risk distribution
        high_risk_ratio = summary['high_risk_watersheds'] / summary['total_watersheds'] if summary['total_watersheds'] > 0 else 0
        if usgs_stations / total_stations > 0.7 and high_risk_ratio < 0.3:
            confidence = "HIGH"
        elif usgs_stations / total_stations > 0.4:
            confidence = "MODERATE" 
        else:
            confidence = "LOW"
            
        return {
            "model_accuracy": round(model_accuracy, 1),
            "usgs_stations": usgs_stations,
            "total_stations": total_stations,
            "rising_trend_count": rising_trend_count,
            "average_flow": round(average_flow, 2),
            "confidence_level": confidence,
            "data_quality_score": round((usgs_stations / total_stations) * 100, 1) if total_stations > 0 else 0,
            "next_update": (datetime.now(timezone.utc) + timedelta(minutes=15)).isoformat(),
            "system_status": "operational",
            "alert_trend": "stable" if rising_trend_count < 3 else "increasing"
        }
        
    except Exception as e:
        log.error(f"Failed to get dashboard insights: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to load dashboard insights")

# =============================================================================
# User Settings API Models
# =============================================================================

class UserSettings(BaseModel):
    """User settings model"""
    notifications: Dict[str, Any]
    display: Dict[str, Any]
    data: Dict[str, Any]

class SettingsUpdateRequest(BaseModel):
    """Settings update request model"""
    settings: UserSettings

# =============================================================================
# User Settings API Endpoints
# =============================================================================

@app.get(_api("settings"), response_model=UserSettings)
async def get_user_settings(user_id: UserID):
    """Get current user's settings"""
    try:
        settings = db.get_user_settings(str(_db_path), user_id)
        return UserSettings(**settings)
    except Exception as e:
        log.error(f"Failed to get user settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to retrieve settings")

@app.post(_api("settings"))
async def update_user_settings(user_id: UserID, settings: UserSettings):
    """Update current user's settings"""
    try:
        db.save_user_settings(str(_db_path), user_id, settings.dict())
        return {"status": "success", "message": "Settings updated successfully"}
    except Exception as e:
        log.error(f"Failed to save user settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to save settings")

@app.delete(_api("settings"))
async def reset_user_settings(user_id: UserID):
    """Reset current user's settings to defaults"""
    try:
        db.delete_user_settings(str(_db_path), user_id)
        return {"status": "success", "message": "Settings reset to defaults"}
    except Exception as e:
        log.error(f"Failed to reset user settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to reset settings")

@app.get(_api("settings/export"))
async def export_user_settings(user_id: UserID):
    """Export current user's settings as JSON file"""
    try:
        settings = db.get_user_settings(str(_db_path), user_id)
        
        # Create JSON response
        import json
        from fastapi.responses import StreamingResponse
        import io
        
        json_str = json.dumps(settings, indent=2)
        json_bytes = io.BytesIO(json_str.encode('utf-8'))
        
        return StreamingResponse(
            json_bytes,
            media_type="application/json",
            headers={"Content-Disposition": "attachment; filename=flood-prediction-settings.json"}
        )
    except Exception as e:
        log.error(f"Failed to export user settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to export settings")

@app.post(_api("settings/import"))
async def import_user_settings(user_id: UserID, request: Request):
    """Import user settings from JSON"""
    try:
        import json
        
        # Read body as bytes
        body = await request.body()
        if not body:
            raise HTTPException(status_code=400, detail="No file content provided")
            
        # Parse JSON settings
        settings_data = json.loads(body.decode('utf-8'))
        
        # Validate structure (basic validation)
        required_keys = ['notifications', 'display', 'data']
        if not all(key in settings_data for key in required_keys):
            raise HTTPException(status_code=400, detail="Invalid settings file format")
            
        # Save settings
        db.save_user_settings(str(_db_path), user_id, settings_data)
        
        return {"status": "success", "message": "Settings imported successfully", "settings": settings_data}
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON format")
    except Exception as e:
        log.error(f"Failed to import user settings: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to import settings")

# =============================================================================
# AI Chat API Endpoints
# =============================================================================

@app.get(_api("ai/models"))
async def get_llm_models(provider: Optional[str] = None):
    """Get available LLM models from the specified provider"""
    try:
        models = get_available_llm_models(provider)
        provider_info = get_provider_info(provider)
        return {
            "models": models, 
            "default_model": provider_info.get("default_model"),
            "provider": provider_info.get("name")
        }
    except Exception as e:
        log.error(f"Failed to get LLM models: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get LLM models")

@app.post(_api("ai/chat"), response_model=ChatResponse)
async def chat_with_ai(user_id: UserID, request: ChatMessage):
    """Chat with AI assistant about flood conditions"""
    try:
        # Generate AI response based on the message and context
        response = db.generate_ai_response(
            str(_db_path), 
            request.message, 
            request.watershed_id,
            request.context or {}
        )
        
        return ChatResponse(
            response=response["content"],
            confidence=response["confidence"],
            recommendations=response.get("recommendations", []),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        log.error(f"Failed to process AI chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process chat message")


@app.post(_api("ai/chat/stream"))
async def stream_chat_with_ai(user_id: UserID, request: ChatMessage):
    """Stream chat with AI assistant about flood conditions"""
    try:
        import asyncio
        import json
        
        async def generate_stream():
            try:
                import threading
                import concurrent.futures
                from collections import deque
                
                # Use thread-safe deque and event for communication
                chunks_queue = deque()
                done_event = threading.Event()
                error_container = {'error': None}
                
                # Get provider info for evaluation
                provider_info = get_provider_info(None)  # Use default provider
                
                def sync_callback(chunk: str):
                    chunks_queue.append(chunk)
                
                def run_llm_sync():
                    try:
                        # Create a new event loop for this thread
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        final_response = loop.run_until_complete(llm_call_stream(
                            _build_india_context(request.message, str(_db_path)),
                            sync_callback, 
                            request.model, 
                            request.use_agent
                        ))
                        chunks_queue.append("__DONE__")
                        done_event.set()
                        return final_response
                    except Exception as e:
                        error_container['error'] = str(e)
                        chunks_queue.append(f"__ERROR__:{str(e)}")
                        done_event.set()
                        return ""
                
                # Start the LLM in a background thread
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    llm_future = executor.submit(run_llm_sync)
                    
                    # Stream chunks as they arrive
                    while not done_event.is_set() or chunks_queue:
                        if chunks_queue:
                            chunk = chunks_queue.popleft()
                            if chunk == "__DONE__":
                                break
                            elif chunk.startswith("__ERROR__"):
                                error_msg = chunk[9:]  # Remove "__ERROR__:" prefix
                                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                                break
                            else:
                                # Send streaming chunk
                                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                        else:
                            # Small delay to avoid busy waiting and send keepalive
                            await asyncio.sleep(0.1)
                            if not done_event.is_set():
                                yield f"data: {json.dumps({'keepalive': True})}\n\n"
                    
                    # Wait for LLM completion
                    final_response = llm_future.result()
                    
                    # Run evaluation for all responses (agent and non-agent) if we have a complete response
                    if final_response and not error_container['error']:
                        try:
                            evaluation_result = await evaluator.evaluate_chat_response(
                                question=request.message,
                                response=final_response,
                                model_used=request.model or "default",
                                agent_used=request.use_agent,
                                watershed_context=request.context,
                                response_provider=provider_info.get("name", "unknown")  # Use actual provider used
                            )
                            
                            # Send evaluation results
                            evaluation_data = {
                                'evaluation': {
                                    'id': evaluation_result.id,
                                    'overall_score': evaluation_result.metrics.overall,
                                    'confidence': evaluation_result.metrics.confidence,
                                    'safety_score': evaluation_result.metrics.safety,
                                    'helpfulness': evaluation_result.metrics.helpfulness,
                                    'accuracy': evaluation_result.metrics.accuracy,
                                    'reasoning': evaluation_result.judge_reasoning
                                }
                            }
                            yield f"data: {json.dumps(evaluation_data)}\n\n"
                            
                        except Exception as eval_error:
                            log.warning(f"Evaluation failed: {str(eval_error)}")
                            # Don't fail the entire response if evaluation fails
                    
                    yield f"data: {json.dumps({'done': True})}\n\n"
                
            except Exception as e:
                log.error(f"Stream generation error: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
        
    except Exception as e:
        log.error(f"Failed to process streaming AI chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process streaming chat message")


# =============================================================================
# NAT Agent Chat API Endpoints
# =============================================================================

@app.get(_api("nat/agents"))
async def get_available_nat_agents():
    """Get available NAT agents"""
    if not _nat_runner:
        raise HTTPException(status_code=503, detail="NAT agents are not available")
    
    try:
        agents_info = _nat_runner.list_available_agents()
        return agents_info
    except Exception as e:
        log.error(f"Failed to get NAT agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get NAT agents")

@app.post(_api("nat/chat"), response_model=NATChatResponse)
async def chat_with_nat_agent(user_id: UserID, request: NATChatMessage):
    """Chat with NAT agents (non-streaming)"""
    if not _nat_runner:
        raise HTTPException(status_code=503, detail="NAT agents are not available")
    
    try:
        # Execute NAT agent workflow based on agent type
        if request.agent_type == "data_collector":
            result = await _nat_runner.run_data_collector(request.custom_prompt or request.message)
        elif request.agent_type == "risk_analyzer":
            result = await _nat_runner.run_risk_analyzer(request.location, request.custom_prompt or request.message)
        elif request.agent_type == "emergency_responder":
            result = await _nat_runner.run_emergency_responder(request.scenario, request.custom_prompt or request.message)
        elif request.agent_type == "predictor":
            result = await _nat_runner.run_predictor(request.forecast_hours, request.location, request.custom_prompt or request.message)
        elif request.agent_type == "h2ogpte_agent":
            result = await _nat_runner.run_h2ogpte_agent("train_model", request.custom_prompt or request.message, request.custom_prompt)
        elif request.agent_type == "all":
            result = await _nat_runner.run_comprehensive_analysis()
        else:
            raise HTTPException(status_code=400, detail=f"Unknown agent type: {request.agent_type}")
        
        return NATChatResponse(
            output=result.get("output", str(result)),
            agent_type=request.agent_type,
            status=result.get("status", "completed"),
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        log.error(f"Failed to process NAT chat: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to process NAT chat: {str(e)}")

@app.post(_api("nat/chat/stream"))
async def stream_chat_with_nat_agent(user_id: UserID, request: NATChatMessage):
    """Stream chat with NAT agents with filtered logs"""
    if not _nat_runner:
        raise HTTPException(status_code=503, detail="NAT agents are not available")
    
    try:
        import asyncio
        import json
        import logging
        
        async def generate_nat_stream():
            try:
                import threading
                import concurrent.futures
                from collections import deque
                import io
                import sys
                
                # Create custom log handler to capture logs
                log_queue = deque()
                done_event = threading.Event()
                error_container = {'error': None}
                result_container = {'result': None}
                
                # Custom log handler for capturing NAT logs
                class NATLogHandler(logging.Handler):
                    def emit(self, record):
                        message = record.getMessage()
                        
                        # Include important agent logs and filter out noise
                        should_include = False
                        
                        # Always include warnings and errors
                        if record.levelno >= logging.WARNING:
                            should_include = True
                        
                        # Include agent-specific logs
                        elif any(keyword in message for keyword in [
                            '[AGENT]', 'Agent input:', 'Agent\'s thoughts:', 'Final Answer:',
                            'Action:', 'Action Input:', 'Tool\'s response:', 'Calling tools:',
                            'agent.react_agent', 'nat_base', 'Workflow completed'
                        ]):
                            should_include = True
                        
                        # Exclude HTTP requests and other noise
                        elif any(noise in message for noise in [
                            'HTTP Request:', 'httpx', 'POST http', 'GET http'
                        ]):
                            should_include = False
                        
                        if should_include:
                            log_entry = {
                                'timestamp': record.created,
                                'level': record.levelname,
                                'message': message,
                                'logger': record.name
                            }
                            log_queue.append(log_entry)
                
                # Add our handler to capture logs
                handler = NATLogHandler()
                logging.getLogger().addHandler(handler)
                
                def run_nat_sync():
                    try:
                        # Create a new event loop for this thread
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        # Execute NAT agent workflow based on agent type
                        if request.agent_type == "data_collector":
                            result = loop.run_until_complete(_nat_runner.run_data_collector(request.custom_prompt or request.message))
                        elif request.agent_type == "risk_analyzer":
                            result = loop.run_until_complete(_nat_runner.run_risk_analyzer(request.location, request.custom_prompt or request.message))
                        elif request.agent_type == "emergency_responder":
                            result = loop.run_until_complete(_nat_runner.run_emergency_responder(request.scenario, request.custom_prompt or request.message))
                        elif request.agent_type == "predictor":
                            result = loop.run_until_complete(_nat_runner.run_predictor(request.forecast_hours, request.location, request.custom_prompt or request.message))
                        elif request.agent_type == "h2ogpte_agent":
                            result = loop.run_until_complete(_nat_runner.run_h2ogpte_agent("train_model", request.custom_prompt or request.message, request.custom_prompt))
                        elif request.agent_type == "all":
                            result = loop.run_until_complete(_nat_runner.run_comprehensive_analysis())
                        else:
                            raise ValueError(f"Unknown agent type: {request.agent_type}")
                        
                        result_container['result'] = result
                        done_event.set()
                        return result
                        
                    except Exception as e:
                        error_container['error'] = str(e)
                        done_event.set()
                        return None
                    finally:
                        # Remove our log handler
                        logging.getLogger().removeHandler(handler)
                
                # Start NAT agent in background thread
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    nat_future = executor.submit(run_nat_sync)
                    
                    # Send initial metadata
                    yield f"data: {json.dumps({'type': 'start', 'agent_type': request.agent_type, 'location': request.location})}\n\n"
                    
                    # Stream logs as they arrive
                    while not done_event.is_set() or log_queue:
                        if log_queue:
                            log_entry = log_queue.popleft()
                            yield f"data: {json.dumps({'type': 'log', 'log': log_entry})}\n\n"
                        else:
                            # Small delay and send keepalive
                            await asyncio.sleep(0.1)
                            if not done_event.is_set():
                                yield f"data: {json.dumps({'type': 'keepalive'})}\n\n"
                    
                    # Wait for completion and get result
                    final_result = nat_future.result()
                    
                    if error_container['error']:
                        yield f"data: {json.dumps({'type': 'error', 'error': error_container['error']})}\n\n"
                    else:
                        result = result_container['result']
                        yield f"data: {json.dumps({'type': 'result', 'output': result.get('output', str(result)), 'status': result.get('status', 'completed')})}\n\n"
                    
                    yield f"data: {json.dumps({'type': 'done'})}\n\n"
                
            except Exception as e:
                log.error(f"NAT stream generation error: {str(e)}")
                yield f"data: {json.dumps({'type': 'error', 'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate_nat_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
        
    except Exception as e:
        log.error(f"Failed to process NAT streaming chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process NAT streaming chat")


# =============================================================================
# AI Provider Management API Endpoints
# =============================================================================

class AIProviderRequest(BaseModel):
    """Request model for AI provider operations"""
    provider: str = "auto"  # "h2ogpte", "nvidia", "auto"
    model: Optional[str] = None
    use_agent: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None
    context: Optional[Dict[str, Any]] = None

class EnhancedChatMessage(BaseModel):
    """Enhanced chat message model with provider selection"""
    message: str
    watershed_id: Optional[int] = None
    context: Optional[Dict[str, Any]] = None
    provider: str = "auto"  # "h2ogpte", "nvidia", "auto"
    model: Optional[str] = None
    use_agent: bool = False
    temperature: Optional[float] = None
    max_tokens: Optional[int] = None

class EnhancedChatResponse(BaseModel):
    """Enhanced chat response with provider metadata"""
    response: str
    provider_used: str
    model_used: str
    agent_used: bool
    confidence: float
    recommendations: List[str] = []
    timestamp: str

@app.get(_api("ai/providers"))
async def get_available_providers():
    """Get available AI providers and their capabilities"""
    try:
        providers_info = get_all_providers_info()
        current_provider = settings.ai_provider
        
        return {
            "providers": providers_info,
            "current_default": current_provider,
            "nvidia_features": {
                "agents_enabled": settings.enable_nvidia_agents,
                "rag_enabled": settings.enable_nvidia_rag,
                "evaluator_enabled": settings.enable_nvidia_evaluator
            }
        }
    except Exception as e:
        log.error(f"Failed to get available providers: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get available providers")

@app.get(_api("ai/providers/{provider_name}"))
async def get_provider_details(provider_name: str):
    """Get detailed information about a specific provider"""
    try:
        provider_info = get_provider_info(provider_name)
        return provider_info
    except Exception as e:
        log.error(f"Failed to get provider details: {str(e)}")
        raise HTTPException(status_code=404, detail=f"Provider '{provider_name}' not found or not available")

@app.get(_api("ai/providers/{provider_name}/models"))
async def get_provider_models(provider_name: str):
    """Get available models for a specific provider"""
    try:
        models = get_available_llm_models(provider_name)
        provider_info = get_provider_info(provider_name)
        
        return {
            "provider": provider_name,
            "models": models,
            "default_model": provider_info.get("default_model"),
            "supports_agents": provider_info.get("supports_agents", False)
        }
    except Exception as e:
        log.error(f"Failed to get models for provider {provider_name}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to get models for provider {provider_name}")

@app.post(_api("ai/chat/enhanced"), response_model=EnhancedChatResponse)
async def enhanced_chat_with_ai(user_id: UserID, request: EnhancedChatMessage):
    """Enhanced chat with AI assistant with provider selection"""
    try:
        # Determine which provider to use
        provider_name = request.provider if request.provider != "auto" else None
        
        # Generate AI response using selected provider
        from .api import llm_call  # Import here to avoid circular imports
        
        # Prepare context for response generation
        context = request.context or {}
        if request.watershed_id:
            context["watershed_id"] = request.watershed_id
        
        # Build enhanced prompt with India real-time context
        if request.watershed_id:
            watershed_context = db.get_watershed_context(str(_db_path), request.watershed_id)
            enhanced_prompt = _build_india_context(request.message, str(_db_path)) + f"\n\nSpecific Watershed: {watershed_context}"
        else:
            enhanced_prompt = _build_india_context(request.message, str(_db_path))
        
        # Call the AI provider
        response = await llm_call(
            enhanced_prompt,
            model=request.model,
            use_agent=request.use_agent,
            provider_name=provider_name,
            temperature=request.temperature or 0.7,
            max_tokens=request.max_tokens or 4096
        )
        
        # Get provider info for response metadata
        provider_info = get_provider_info(provider_name)
        
        return EnhancedChatResponse(
            response=response,
            provider_used=provider_info.get("name", "unknown"),
            model_used=request.model or provider_info.get("default_model", "unknown"),
            agent_used=request.use_agent and provider_info.get("supports_agents", False),
            confidence=0.75 + min(0.20, len(request.message.split()) * 0.005),
            recommendations=[],  # TODO: Add recommendation logic
            timestamp=datetime.now(timezone.utc).isoformat()
        )
        
    except Exception as e:
        log.error(f"Failed to process enhanced AI chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process enhanced chat message")

@app.post(_api("ai/chat/enhanced/stream"))
async def enhanced_stream_chat_with_ai(user_id: UserID, request: EnhancedChatMessage):
    """Enhanced streaming chat with AI assistant with provider selection"""
    try:
        import asyncio
        import json
        
        # Determine which provider to use
        provider_name = request.provider if request.provider != "auto" else None
        
        async def generate_enhanced_stream():
            try:
                import threading
                import concurrent.futures
                from collections import deque
                
                # Use thread-safe deque and event for communication
                chunks_queue = deque()
                done_event = threading.Event()
                error_container = {'error': None}
                provider_info = get_provider_info(provider_name)
                
                def sync_callback(chunk: str):
                    chunks_queue.append(chunk)
                
                def run_llm_sync():
                    try:
                        # Build enhanced prompt with India real-time context
                        # Get live watershed data for context
                        try:
                            live_watersheds = db.get_watersheds(str(_db_path))
                            high_risk = [w for w in live_watersheds if w.get('risk_score', 0) >= 6]
                            critical_risk = [w for w in live_watersheds if w.get('risk_score', 0) >= 8]
                            alerts = db.get_active_alerts(str(_db_path), limit=10)
                            summary = db.get_dashboard_summary(str(_db_path))

                            india_context = f"""You are an expert India Flood Intelligence AI assistant with access to REAL-TIME data.

=== LIVE INDIA FLOOD DATA (RIGHT NOW) ===
Total monitored river sites: {summary.get('total_watersheds', 0)}
Active flood alerts: {summary.get('active_alerts', 0)}
High risk sites (score ≥6): {len(high_risk)}
Critical risk sites (score ≥8): {len(critical_risk)}

HIGH RISK AREAS RIGHT NOW:
{chr(10).join([f"• {w['name']} — Risk {w['risk_score']:.1f}/10, Flow {w['current_streamflow_cfs']:,.0f} CFS, Trend: {w.get('trend','stable')}" for w in high_risk[:8]]) or '• No high risk areas currently'}

ACTIVE ALERTS:
{chr(10).join([f"• {a.get('alert_type','Alert')} at {a.get('watershed','Unknown')} — {a.get('severity','?')} severity" for a in alerts[:5]]) or '• No active alerts'}

DATA SOURCE: Open-Meteo Flood API (GloFAS) — updated every hour
IMD THRESHOLDS: Heavy Rain ≥64.5mm/day, Very Heavy ≥115.5mm/day, Extreme ≥204.5mm/day
EMERGENCY: NDMA helpline 1078 | IMD: mausam.imd.gov.in | CWC: cwc.gov.in

=== INDIA RIVER BASINS MONITORED ===
Ganga (UP, Bihar, WB), Brahmaputra (Assam, AR), Mahanadi (Odisha, CG),
Godavari (MH, TG, AP), Krishna (KA, AP), Narmada (MP, GJ), Kaveri (KA, TN), Indus (PB, HP, J&K)

Answer the user's question using this real-time data. Be specific, fast, and actionable.
If asked about risk in a specific area, check the high risk areas list above.
Always include NDMA 1078 for emergencies.
"""
                        except Exception:
                            india_context = """You are an India Flood Intelligence AI. Answer flood, weather and river risk questions for India.
Data source: Open-Meteo Flood API (GloFAS). Emergency: NDMA 1078."""

                        if request.watershed_id:
                            watershed_context = db.get_watershed_context(str(_db_path), request.watershed_id)
                            enhanced_prompt = f"{india_context}\n\nSpecific Watershed: {watershed_context}\n\nUser Question: {request.message}"
                        else:
                            enhanced_prompt = f"{india_context}\n\nUser Question: {request.message}"
                        
                        # Create a new event loop for this thread
                        import asyncio
                        try:
                            loop = asyncio.get_event_loop()
                        except RuntimeError:
                            loop = asyncio.new_event_loop()
                            asyncio.set_event_loop(loop)
                        
                        final_response = loop.run_until_complete(llm_call_stream(
                            enhanced_prompt, 
                            sync_callback, 
                            request.model, 
                            request.use_agent,
                            provider_name,
                            temperature=request.temperature or 0.7,
                            max_tokens=request.max_tokens or 4096
                        ))
                        chunks_queue.append("__DONE__")
                        done_event.set()
                        return final_response
                    except Exception as e:
                        error_container['error'] = str(e)
                        chunks_queue.append(f"__ERROR__:{str(e)}")
                        done_event.set()
                        return ""
                
                # Start the LLM in a background thread
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    llm_future = executor.submit(run_llm_sync)
                    
                    # Send provider info first
                    yield f"data: {json.dumps({'provider': provider_info.get('name', 'unknown'), 'model': request.model or provider_info.get('default_model', 'unknown')})}\n\n"
                    
                    # Stream chunks as they arrive
                    while not done_event.is_set() or chunks_queue:
                        if chunks_queue:
                            chunk = chunks_queue.popleft()
                            if chunk == "__DONE__":
                                break
                            elif chunk.startswith("__ERROR__"):
                                error_msg = chunk[9:]  # Remove "__ERROR__:" prefix
                                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                                break
                            else:
                                # Send streaming chunk
                                yield f"data: {json.dumps({'chunk': chunk, 'done': False})}\n\n"
                        else:
                            # Small delay to avoid busy waiting and send keepalive
                            await asyncio.sleep(0.1)
                            if not done_event.is_set():
                                yield f"data: {json.dumps({'keepalive': True})}\n\n"
                    
                    # Wait for LLM completion
                    final_response = llm_future.result()
                    
                    # Run evaluation for all responses (agent and non-agent) if we have a complete response
                    if final_response and not error_container['error']:
                        try:
                            evaluation_result = await evaluator.evaluate_chat_response(
                                question=request.message,
                                response=final_response,
                                model_used=request.model or provider_info.get("default_model", "unknown"),
                                agent_used=request.use_agent,
                                watershed_context=request.context,
                                response_provider=provider_info.get("name", "unknown")  # Use actual provider used
                            )
                            
                            # Send evaluation results
                            evaluation_data = {
                                'evaluation': {
                                    'id': evaluation_result.id,
                                    'overall_score': evaluation_result.metrics.overall,
                                    'confidence': evaluation_result.metrics.confidence,
                                    'safety_score': evaluation_result.metrics.safety,
                                    'helpfulness': evaluation_result.metrics.helpfulness,
                                    'accuracy': evaluation_result.metrics.accuracy,
                                    'reasoning': evaluation_result.judge_reasoning
                                }
                            }
                            yield f"data: {json.dumps(evaluation_data)}\n\n"
                            
                        except Exception as eval_error:
                            log.warning(f"Evaluation failed: {str(eval_error)}")
                            # Don't fail the entire response if evaluation fails
                    
                    yield f"data: {json.dumps({'done': True, 'provider_used': provider_info.get('name', 'unknown')})}\n\n"
                
            except Exception as e:
                log.error(f"Enhanced stream generation error: {str(e)}")
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
        
        return StreamingResponse(
            generate_enhanced_stream(),
            media_type="text/plain",
            headers={
                "Cache-Control": "no-cache",
                "Connection": "keep-alive",
                "Content-Type": "text/event-stream",
            }
        )
        
    except Exception as e:
        log.error(f"Failed to process enhanced streaming AI chat: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to process enhanced streaming chat message")


# =============================================================================
# Evaluation API Endpoints  
# =============================================================================

@app.post(_api("evaluation/evaluate"))
async def evaluate_response(request: Dict[str, Any]):
    """Evaluate a chat response using NVIDIA-style LLM-as-Judge"""
    try:
        question = request.get("question", "")
        response = request.get("response", "")
        model_used = request.get("model", "unknown")
        agent_used = request.get("agent_used", False)
        watershed_context = request.get("watershed_context")
        
        if not question or not response:
            raise HTTPException(status_code=400, detail="Question and response are required")
        
        # Run evaluation with cross-provider judging
        response_provider = request.get("response_provider")  # Allow manual specification
        evaluation_result = await evaluator.evaluate_chat_response(
            question=question,
            response=response,
            model_used=model_used,
            agent_used=agent_used,
            watershed_context=watershed_context,
            response_provider=response_provider
        )
        
        return {
            "evaluation_id": evaluation_result.id,
            "metrics": evaluation_result.metrics.dict(),
            "reasoning": evaluation_result.judge_reasoning,
            "duration_ms": evaluation_result.evaluation_duration_ms,
            "timestamp": evaluation_result.timestamp.isoformat()
        }
        
    except Exception as e:
        log.error(f"Failed to evaluate response: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to evaluate response")


@app.get(_api("evaluation/stats"))
async def get_evaluation_stats(hours: int = 24):
    """Get evaluation statistics for the last N hours"""
    try:
        stats = evaluator.get_evaluation_stats(hours=hours)
        return stats
        
    except Exception as e:
        log.error(f"Failed to get evaluation stats: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get evaluation statistics")


@app.get(_api("evaluation/history"))
async def get_evaluation_history(limit: int = 50):
    """Get recent evaluation history"""
    try:
        # Get recent evaluations from memory (limited to last 100)
        recent_evaluations = evaluator.evaluation_history[-limit:]
        
        return {
            "evaluations": [
                {
                    "id": eval_result.id,
                    "timestamp": eval_result.timestamp.isoformat(),
                    "question": eval_result.question[:100] + "..." if len(eval_result.question) > 100 else eval_result.question,
                    "model": eval_result.model_used,
                    "agent_used": eval_result.agent_used,
                    "overall_score": eval_result.metrics.overall,
                    "confidence": eval_result.metrics.confidence,
                    "safety_score": eval_result.metrics.safety
                }
                for eval_result in reversed(recent_evaluations)
            ]
        }
        
    except Exception as e:
        log.error(f"Failed to get evaluation history: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get evaluation history")


# =============================================================================
# AI Agents API Endpoints
# =============================================================================

@app.get(_api("agents"))
async def get_agents_status():
    """Get status of all AI agents"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        agent_status = await _agent_manager.get_agent_status()
        return {
            "agents": agent_status,
            "manager_initialized": _agent_manager.is_initialized,
            "last_update": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        log.error(f"Failed to get agents status: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get agents status")

@app.get(_api("agents/insights"))
async def get_agents_insights():
    """Get insights from all AI agents"""
    if not _agent_manager:
        return {
            "error": "AI agents are disabled",
            "insights": {},
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    
    try:
        insights = await _agent_manager.get_all_insights()
        return {
            "insights": insights,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        log.error(f"Failed to get agents insights: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Failed to get agents insights: {str(e)}")

@app.get(_api("agents/alerts"))
async def get_agents_alerts():
    """Get alerts from all AI agents"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        alerts = await _agent_manager.get_all_alerts()
        return {
            "alerts": alerts,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        log.error(f"Failed to get agents alerts: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get agents alerts")

@app.get(_api("agents/summary"))
async def get_agents_summary():
    """Get summary of all agent activities for dashboard"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        summary = await _agent_manager.get_dashboard_summary()
        return summary
    except Exception as e:
        log.error(f"Failed to get agents summary: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get agents summary")

@app.get(_api("agents/{agent_name}"))
async def get_agent_details(agent_name: str):
    """Get detailed information about a specific agent"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        details = await _agent_manager.get_agent_details(agent_name)
        return details
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.error(f"Failed to get agent details for {agent_name}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get agent details")

@app.post(_api("agents/{agent_name}/check"))
async def force_agent_check(agent_name: str, user_id: UserID):
    """Force an immediate check for a specific agent"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        result = await _agent_manager.force_agent_check(agent_name)
        return {
            "status": "success",
            "message": f"Force check completed for agent: {agent_name}",
            "result": result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        log.error(f"Failed to force check for agent {agent_name}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to force agent check")

@app.post(_api("agents/start"))
async def start_all_agents(user_id: UserID):
    """Start all AI agents"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        await _agent_manager.start_all_agents()
        return {
            "status": "success",
            "message": "All agents started successfully"
        }
    except Exception as e:
        log.error(f"Failed to start agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to start agents")

@app.post(_api("agents/stop"))
async def stop_all_agents(user_id: UserID):
    """Stop all AI agents"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        await _agent_manager.stop_all_agents()
        return {
            "status": "success",
            "message": "All agents stopped successfully"
        }
    except Exception as e:
        log.error(f"Failed to stop agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to stop agents")

@app.post(_api("agents/collect-data"))
async def collect_external_data(user_id: UserID):
    """Trigger data collection from external APIs"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        data = await _agent_manager.collect_external_data()
        return {
            "status": "success",
            "message": "External data collection completed",
            "data": data
        }
    except Exception as e:
        log.error(f"Failed to collect external data: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to collect external data")

@app.post(_api("agents/forecast"))
async def generate_ai_forecast(hours_ahead: int = 24):
    """Generate AI-powered flood forecast"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        forecast = await _agent_manager.generate_forecast(hours_ahead)
        return {
            "status": "success",
            "forecast": forecast
        }
    except Exception as e:
        log.error(f"Failed to generate forecast: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to generate forecast")

class EmergencyAlertRequest(BaseModel):
    """Emergency alert request model"""
    title: str
    message: str
    severity: str = "warning"  # info, warning, critical
    affected_areas: List[str] = []
    recommendations: List[str] = []
    channels: List[str] = ["EAS", "Cell", "Social"]

@app.post(_api("agents/emergency-alert"))
async def send_emergency_alert(user_id: UserID, request: EmergencyAlertRequest):
    """Send emergency alert through AI agents"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        alert_data = {
            "title": request.title,
            "message": request.message,
            "severity": request.severity,
            "affected_areas": request.affected_areas,
            "recommendations": request.recommendations,
            "channels": request.channels
        }
        
        success = await _agent_manager.send_emergency_alert(alert_data)
        
        if success:
            return {
                "status": "success",
                "message": "Emergency alert sent successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to send emergency alert")
    
    except Exception as e:
        log.error(f"Failed to send emergency alert: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to send emergency alert")

@app.get(_api("agents/available"))
async def get_available_agents():
    """Get list of available agents"""
    if not _agent_manager:
        raise HTTPException(status_code=503, detail="AI agents are disabled")
    
    try:
        agents = _agent_manager.get_available_agents()
        return {
            "agents": agents,
            "total_count": len(agents)
        }
    except Exception as e:
        log.error(f"Failed to get available agents: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to get available agents")

# =============================================================================
# Health Check
# =============================================================================

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    try:
        # Check Redis connection
        _redis.ping()
        
        # Check agents status if enabled
        agents_status = "disabled"
        if _agent_manager:
            try:
                agent_summary = await _agent_manager.get_dashboard_summary()
                agents_status = f"{agent_summary['running_agents']}/{agent_summary['total_agents']} running"
            except:
                agents_status = "error"
        
        return {
            "status": "healthy", 
            "redis": "connected",
            "agents": agents_status,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    except Exception as e:
        return {
            "status": "unhealthy", 
            "redis": f"error: {str(e)}",
            "agents": "unknown",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }


@app.get("/")
async def serve_index():
    """Serve the main index.html file"""
    return FileResponse(server_dir / "index.html")


# =============================================================================
# PDF Report & SMS API Endpoints
# =============================================================================

class SMSTestRequest(BaseModel):
    """Request model for sending a test SMS"""
    watershed_name: str = "Test Site"
    risk_level: str = "HIGH"
    risk_score: float = 7.5
    message: str = "This is a test alert from India Flood Intelligence System."


@app.get(_api("reports"))
async def list_reports():
    """List all generated PDF flood reports"""
    try:
        from .notifications import list_reports as _list_reports
        reports = _list_reports()
        return {
            "reports": reports,
            "count": len(reports),
            "reports_dir": settings.reports_dir,
        }
    except Exception as e:
        log.error(f"Failed to list reports: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to list reports")


@app.post(_api("reports/generate"))
async def generate_report(region: Optional[str] = None):
    """
    Generate a PDF flood risk report on demand.
    Optionally filter by region code (e.g. IN-GANGA, IN-BRAHMAPUTRA).
    Returns report metadata including filename and download URL.
    """
    try:
        from .notifications import generate_flood_report

        watersheds = db.get_watersheds(str(_db_path), region_code=region)
        if not watersheds:
            raise HTTPException(status_code=404, detail="No watershed data found to generate report")

        alerts_raw = db.get_active_alerts(str(_db_path), limit=20)

        title = "India Flood Intelligence Report"
        if region:
            title = f"India Flood Intelligence Report — {region}"

        pdf_path = generate_flood_report(
            watersheds=[dict(w) for w in watersheds],
            alerts=[dict(a) for a in alerts_raw],
            report_title=title,
        )

        if not pdf_path:
            raise HTTPException(status_code=500, detail="PDF generation failed — check server logs")

        return {
            "status": "success",
            "filename": pdf_path.name,
            "download_url": f"{settings.base_url}api/reports/download/{pdf_path.name}",
            "size_kb": round(pdf_path.stat().st_size / 1024, 1),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "watershed_count": len(watersheds),
            "alert_count": len(alerts_raw),
            "region": region or "All India",
        }

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to generate report: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to generate report: {str(e)}")


@app.get(_api("reports/download/{filename}"))
async def download_report(filename: str):
    """Download a generated PDF report by filename."""
    try:
        # Security: only allow safe filenames — no path traversal
        if "/" in filename or "\\" in filename or ".." in filename:
            raise HTTPException(status_code=400, detail="Invalid filename")
        if not filename.endswith(".pdf"):
            raise HTTPException(status_code=400, detail="Only PDF files are downloadable")

        pdf_path = Path(settings.reports_dir) / filename
        if not pdf_path.exists():
            raise HTTPException(status_code=404, detail="Report file not found")

        return FileResponse(
            path=str(pdf_path),
            media_type="application/pdf",
            filename=filename,
            headers={"Content-Disposition": f"attachment; filename={filename}"},
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Failed to download report {filename}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to download report")


@app.post(_api("reports/send-sms"))
async def send_test_sms(request: SMSTestRequest):
    """
    Send a test SMS alert to the configured phone numbers.
    Useful for verifying Twilio credentials are working.
    """
    try:
        from .notifications import send_sms_alert, _sms_last_sent

        # Temporarily clear cooldown so test always fires
        _sms_last_sent.pop(request.watershed_name, None)

        success = send_sms_alert(
            watershed_name=request.watershed_name,
            risk_level=request.risk_level,
            risk_score=request.risk_score,
            message=request.message,
        )

        if success:
            return {
                "status": "success",
                "message": f"SMS sent to {len(settings.sms_alert_numbers)} number(s)",
                "numbers": settings.sms_alert_numbers,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        else:
            return {
                "status": "failed",
                "message": "SMS not sent — check Twilio credentials in .env or risk level threshold",
                "sms_enabled": settings.sms_alerts_enabled,
                "twilio_configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
            }

    except Exception as e:
        log.error(f"Failed to send test SMS: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to send SMS: {str(e)}")


@app.get(_api("reports/sms-config"))
async def get_sms_config():
    """Get current SMS alert configuration (no secrets exposed)."""
    return {
        "sms_alerts_enabled": settings.sms_alerts_enabled,
        "alert_numbers": settings.sms_alert_numbers,
        "alert_min_severity": settings.sms_alert_min_severity,
        "cooldown_minutes": settings.sms_cooldown_minutes,
        "twilio_configured": bool(settings.twilio_account_sid and settings.twilio_auth_token),
        "from_number_set": bool(settings.twilio_from_number),
        "pdf_reports_enabled": settings.pdf_reports_enabled,
        "auto_pdf_on_critical": settings.auto_pdf_on_critical,
    }


# =============================================================================
# World-First Novel Features API  (/api/novel/*)
# 12 features never implemented anywhere in the world
# =============================================================================

# ── Feature 1: AI Flood Memory ────────────────────────────────────────────────

@app.get(_api("novel/memory/status"))
async def get_flood_memory_status():
    """Get AI Flood Memory status — predictions stored, accuracy, retrain trigger."""
    try:
        from .flood_memory import get_flood_memory
        mem = get_flood_memory(str(_db_path))
        return mem.get_memory_stats()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(_api("novel/memory/retrain"))
async def trigger_flood_memory_retrain(user_id: UserID):
    """Trigger autonomous post-event self-retraining of ML models."""
    try:
        from .flood_memory import get_flood_memory
        mem = get_flood_memory(str(_db_path))
        should, reason = mem.should_retrain()
        if not should:
            return {"status": "skipped", "reason": reason,
                    "timestamp": datetime.now(timezone.utc).isoformat()}
        report = await mem.auto_retrain()
        return {"status": "completed", "report": report.to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("novel/memory/history"))
async def get_retrain_history():
    """Get history of all autonomous retraining runs."""
    try:
        from .flood_memory import get_flood_memory
        mem = get_flood_memory(str(_db_path))
        return {"history": mem.get_retraining_history()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 2: Compound Cascade Predictor ────────────────────────────────────

@app.get(_api("novel/cascade/all"))
async def get_all_cascades(rainfall_mm: float = 0.0):
    """Get cascade predictions for all high-risk watersheds."""
    try:
        from .cascade_predictor import get_cascade_predictor
        watersheds = db.get_watersheds(str(_db_path))
        predictor  = get_cascade_predictor()
        reports    = predictor.predict_all([dict(w) for w in watersheds], rainfall_mm)
        return {"count": len(reports), "cascades": [r.to_dict() for r in reports],
                "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("novel/cascade/{watershed_id}"))
async def get_cascade_prediction(watershed_id: int, rainfall_mm: float = 0.0):
    """Predict second-order disasters: bridge failure, landslide, disease, power cuts, road closures."""
    try:
        from .cascade_predictor import get_cascade_predictor
        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if not ws:
            raise HTTPException(status_code=404, detail="Watershed not found")
        predictor = get_cascade_predictor()
        report = predictor.predict(dict(ws), rainfall_mm=rainfall_mm)
        return report.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 3: Street-Level House Flood Depth ─────────────────────────────────

@app.get(_api("novel/street-depth/{watershed_id}"))
async def get_street_depth(watershed_id: int):
    """Estimate flood depth at street/address level using Manning's equation + SRTM DEM."""
    try:
        from .street_depth import get_street_depth_estimator
        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if not ws:
            raise HTTPException(status_code=404, detail="Watershed not found")
        estimator = get_street_depth_estimator()
        report = estimator.estimate_district(dict(ws))
        return report.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class AddressDepthRequest(BaseModel):
    addresses: List[str]
    watershed_id: int


@app.post(_api("novel/street-depth/query"))
async def query_address_depths(request: AddressDepthRequest):
    """Get flood depth estimates for specific addresses."""
    try:
        from .street_depth import get_street_depth_estimator
        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == request.watershed_id), None)
        if not ws:
            raise HTTPException(status_code=404, detail="Watershed not found")
        estimator = get_street_depth_estimator()
        report = estimator.estimate_district(dict(ws), addresses=request.addresses)
        return report.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 4: Vulnerability Profiling ───────────────────────────────────────

@app.get(_api("novel/vulnerability/national-priority"))
async def get_national_rescue_priority():
    """Get national NDRF rescue priority list across all high-risk watersheds."""
    try:
        from .vulnerability_profiler import get_vulnerability_profiler
        watersheds = db.get_watersheds(str(_db_path))
        profiler   = get_vulnerability_profiler()
        priority   = profiler.generate_national_priority([dict(w) for w in watersheds])
        return {"priority_list": priority, "count": len(priority),
                "timestamp": datetime.now(timezone.utc).isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("novel/vulnerability/{watershed_id}"))
async def get_vulnerability_profile(watershed_id: int):
    """Get rescue priority list with demographic vulnerability scores per locality."""
    try:
        from .vulnerability_profiler import get_vulnerability_profiler
        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if not ws:
            raise HTTPException(status_code=404, detail="Watershed not found")
        profiler = get_vulnerability_profiler()
        report = profiler.profile_watershed(dict(ws))
        return report.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 5: Voice IVR ──────────────────────────────────────────────────────

@app.get(_api("novel/ivr/script"))
async def get_ivr_script(risk_level: str = "HIGH", lang: str = "en",
                          district: str = "your district"):
    """Get IVR flood alert script in any Indian language."""
    try:
        from .voice_ivr import get_ivr_system
        ivr = get_ivr_system()
        return {
            "lang":    lang,
            "script":  ivr.get_script(risk_level, lang),
            "ssml":    ivr.get_ssml(risk_level, lang, district),
            "menu":    ivr.get_full_menu(lang),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class IVRBatchRequest(BaseModel):
    district:      str
    risk_level:    str = "HIGH"
    phone_numbers: List[Dict[str, str]]   # [{"phone":"+91...","lang":"hi"}]


@app.post(_api("novel/ivr/batch-call"))
async def send_ivr_batch(user_id: UserID, request: IVRBatchRequest):
    """Generate and dispatch outbound IVR alert calls for CRITICAL/HIGH events."""
    try:
        from .voice_ivr import get_ivr_system
        ivr   = get_ivr_system()
        batch = ivr.generate_outbound_batch(
            request.district, request.risk_level, request.phone_numbers)
        return batch.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("novel/ivr/simulate"))
async def simulate_ivr_call(digit: str = "1", district: str = "Patna",
                              risk_level: str = "HIGH"):
    """Simulate citizen pressing a digit in the IVR menu."""
    try:
        from .voice_ivr import get_ivr_system
        ivr = get_ivr_system()
        return ivr.simulate_inbound_response(digit, district, risk_level)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 6: Dam Negotiation ────────────────────────────────────────────────

@app.get(_api("novel/dam-negotiation/{confluence}"))
async def get_dam_schedule(confluence: str, horizon: int = 72):
    """
    Calculate optimal staggered dam release schedule for a confluence point
    to prevent simultaneous downstream flood peaks.
    """
    try:
        from .dam_negotiation import get_dam_engine
        engine   = get_dam_engine()
        schedule = engine.negotiate(confluence, horizon_hours=horizon)
        return schedule.to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("novel/dam-negotiation/all"))
async def get_all_dam_schedules():
    """Get optimal release schedules for all India dam confluence points."""
    try:
        from .dam_negotiation import get_dam_engine
        engine    = get_dam_engine()
        schedules = engine.get_all_schedules()
        states    = engine.get_dam_states()
        return {
            "dam_states": [s.__dict__ for s in states],
            "schedules":  [s.to_dict() for s in schedules],
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 7: AI Compensation Assessment ────────────────────────────────────

class CompensationRequest(BaseModel):
    description:     str
    claimant_name:   str
    claimant_phone:  str
    village:         str
    district:        str
    state:           str
    flood_event_id:  str = ""
    flood_risk_score: float = 7.0
    flood_date:      Optional[str] = None


@app.post(_api("novel/compensation/assess"))
async def assess_flood_damage(request: CompensationRequest):
    """
    Generate AI flood damage assessment and pre-filled SDRF compensation claim.
    Reduces claim processing from 18 months to days.
    """
    try:
        from .compensation import get_compensation_assessor
        assessor = get_compensation_assessor()
        claim    = assessor.assess_from_description(
            description      = request.description,
            claimant_name    = request.claimant_name,
            claimant_phone   = request.claimant_phone,
            village          = request.village,
            district         = request.district,
            state            = request.state,
            flood_event_id   = request.flood_event_id,
            flood_risk_score = request.flood_risk_score,
            flood_date       = request.flood_date,
        )
        return {
            "claim":     claim.to_dict(),
            "form_text": claim.to_form_text(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("novel/compensation/rates"))
async def get_sdrf_rates():
    """Get current SDRF compensation rates (2024-25)."""
    try:
        from .compensation import SDRF_RATES
        return {"sdrf_rates": SDRF_RATES,
                "year": "2024-25",
                "source": "MHA SDRF Guidelines 2023"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 8: Flood Digital Twin ────────────────────────────────────────────

class TwinScenarioRequest(BaseModel):
    watershed_id:        int
    scenario_type:       str = "EXTRA_RAINFALL"
    extra_rainfall_mm:   float = 0.0
    rainfall_duration_h: int   = 6
    dam_release_cumecs:  float = 0.0
    upstream_surge_pct:  float = 0.0
    soil_saturation_pct: Optional[float] = None
    horizon_hours:       int   = 72


@app.post(_api("novel/digital-twin/simulate"))
async def run_digital_twin(request: TwinScenarioRequest):
    """
    Run a what-if flood scenario simulation on the digital twin.
    Shows hour-by-hour impact of extra rainfall, dam release, or upstream surge.
    """
    try:
        from .digital_twin import get_digital_twin, ScenarioInput
        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == request.watershed_id), None)
        if not ws:
            raise HTTPException(status_code=404, detail="Watershed not found")
        twin     = get_digital_twin()
        scenario = ScenarioInput(
            scenario_type       = request.scenario_type,
            extra_rainfall_mm   = request.extra_rainfall_mm,
            rainfall_duration_h = request.rainfall_duration_h,
            dam_release_cumecs  = request.dam_release_cumecs,
            upstream_surge_pct  = request.upstream_surge_pct,
            soil_saturation_pct = request.soil_saturation_pct,
        )
        result = twin.simulate(dict(ws), scenario, horizon_hours=request.horizon_hours)
        return result.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("novel/digital-twin/all-scenarios/{watershed_id}"))
async def run_all_twin_scenarios(watershed_id: int):
    """Run all 6 standard what-if scenarios for a watershed."""
    try:
        from .digital_twin import get_digital_twin
        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if not ws:
            raise HTTPException(status_code=404, detail="Watershed not found")
        twin    = get_digital_twin()
        results = twin.run_all_scenarios(dict(ws))
        return {
            "watershed":  ws.get("name"),
            "scenarios":  [r.to_dict() for r in results],
            "count":      len(results),
            "timestamp":  datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 9: Federated Learning ────────────────────────────────────────────

@app.get(_api("novel/federated/status"))
async def get_federated_status():
    """Get federated learning status across all participating Indian states."""
    try:
        from .federated_learning import get_federated_server
        server = get_federated_server()
        return server.get_status().to_dict()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(_api("novel/federated/run-round"))
async def run_federated_round(user_id: UserID, n_rounds: int = 1):
    """Run N rounds of federated averaging across all states."""
    try:
        from .federated_learning import get_federated_server
        server = get_federated_server()
        loop   = asyncio.get_event_loop()
        rounds = await loop.run_in_executor(
            None, server.run_multiple_rounds, n_rounds)
        return {"rounds": [r.to_dict() for r in rounds],
                "status": get_federated_server().get_status().to_dict()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("novel/federated/privacy-report"))
async def get_federated_privacy():
    """Get differential privacy guarantees and state data sovereignty report."""
    try:
        from .federated_learning import get_federated_server
        server = get_federated_server()
        return server.get_privacy_report()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 10: Economic Impact Predictor ────────────────────────────────────

@app.get(_api("novel/economic-impact/national"))
async def get_national_economic_impact():
    """Get pre-event economic impact forecast for all high-risk watersheds."""
    try:
        from .economic_impact import get_economic_predictor
        watersheds = db.get_watersheds(str(_db_path))
        predictor  = get_economic_predictor()
        reports    = predictor.predict_all([dict(w) for w in watersheds])
        total      = sum(r.total_impact_crore for r in reports)
        return {
            "total_impact_crore": round(total, 1),
            "watersheds_at_risk": len(reports),
            "reports": [r.to_dict() for r in reports],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("novel/economic-impact/{watershed_id}"))
async def get_economic_impact(watershed_id: int):
    """Pre-event economic damage forecast: crop loss, infrastructure, property, GDP, insurance."""
    try:
        from .economic_impact import get_economic_predictor
        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if not ws:
            raise HTTPException(status_code=404, detail="Watershed not found")
        predictor = get_economic_predictor()
        report    = predictor.predict(dict(ws))
        return {"report": report.to_dict(), "summary": report.executive_summary()}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 11: Carbon Credit Tracker ────────────────────────────────────────

@app.get(_api("novel/carbon/{watershed_id}"))
async def get_carbon_report(watershed_id: int):
    """
    Get carbon sequestration report and VCU certificates for wetland ecosystems
    in a watershed basin. Creates financial incentive to protect flood buffers.
    """
    try:
        from .carbon_credits import get_carbon_tracker
        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if not ws:
            raise HTTPException(status_code=404, detail="Watershed not found")
        tracker = get_carbon_tracker()
        report  = tracker.generate_report(dict(ws))
        return report.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class CertificateRequest(BaseModel):
    district:       str
    state:          str
    basin:          str
    ecosystem_type: str = "freshwater_wetland"
    area_ha:        float
    community_name: str


@app.post(_api("novel/carbon/issue-certificate"))
async def issue_carbon_certificate(user_id: UserID, request: CertificateRequest):
    """Issue a VCU carbon credit certificate for a community wetland guardian."""
    try:
        from .carbon_credits import get_carbon_tracker
        tracker = get_carbon_tracker()
        cert    = tracker.issue_certificate(
            district       = request.district,
            state          = request.state,
            basin          = request.basin,
            ecosystem_type = request.ecosystem_type,
            area_ha        = request.area_ha,
            community_name = request.community_name,
        )
        return {"certificate": cert.to_dict(), "certificate_text": cert.certificate_text()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Feature 12: Basin Flood Genome ───────────────────────────────────────────

@app.get(_api("novel/genome/compare-all"))
async def compare_all_genomes():
    """Compare genome anomaly scores across all monitored watersheds."""
    try:
        from .flood_genome import get_genome_analyser
        watersheds = db.get_watersheds(str(_db_path))
        analyser   = get_genome_analyser()
        comparison = analyser.compare_basins([dict(w) for w in watersheds])
        unprecedented = [c for c in comparison
                         if c["anomaly_class"] in ("UNPRECEDENTED", "RECORD")]
        return {
            "comparison":       comparison,
            "unprecedented":    unprecedented,
            "total_watersheds": len(comparison),
            "timestamp":        datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("novel/genome/{watershed_id}"))
async def get_flood_genome(watershed_id: int,
                            soil_saturation_pct: float = 60.0,
                            rainfall_mm: float = 0.0):
    """
    Compute hydrological genome fingerprint for a watershed.
    Detects NORMAL / UNUSUAL / UNPRECEDENTED / RECORD events
    using Mahalanobis distance from 50-year CWC reference genome.
    """
    try:
        from .flood_genome import get_genome_analyser
        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if not ws:
            raise HTTPException(status_code=404, detail="Watershed not found")
        analyser = get_genome_analyser()
        report   = analyser.analyse(dict(ws), soil_saturation_pct, rainfall_mm)
        return report.to_dict()
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Master novel features summary ────────────────────────────────────────────

@app.get(_api("novel/summary"))
async def get_novel_features_summary():
    """
    Quick health check for all 12 novel world-first features.
    Returns status of each module.
    """
    features = {
        "flood_memory":        "flood_memory",
        "cascade_predictor":   "cascade_predictor",
        "street_depth":        "street_depth",
        "vulnerability":       "vulnerability_profiler",
        "voice_ivr":           "voice_ivr",
        "dam_negotiation":     "dam_negotiation",
        "compensation":        "compensation",
        "digital_twin":        "digital_twin",
        "federated_learning":  "federated_learning",
        "economic_impact":     "economic_impact",
        "carbon_credits":      "carbon_credits",
        "flood_genome":        "flood_genome",
    }
    status = {}
    for name, module in features.items():
        try:
            __import__(f"flood_prediction.{module}")
            status[name] = "active"
        except Exception as e:
            status[name] = f"error: {str(e)[:50]}"
    return {
        "total_features": 12,
        "active":    sum(1 for v in status.values() if v == "active"),
        "features":  status,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


# =============================================================================
# Phase 1 — Public Portal, Translations, User Accounts APIs
# =============================================================================

# ── Translations ──────────────────────────────────────────────────────────────

@app.get(_api("translations/{lang}"))
async def get_translations(lang: str):
    """Return all UI translations for a given language code."""
    try:
        from .translations import get_all_translations, SUPPORTED_LANGUAGES
        valid = [l["code"] for l in SUPPORTED_LANGUAGES]
        if lang not in valid:
            lang = "en"
        return {
            "lang": lang,
            "translations": get_all_translations(lang),
            "supported_languages": SUPPORTED_LANGUAGES,
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("translations"))
async def get_supported_languages():
    """Return list of all supported languages."""
    from .translations import SUPPORTED_LANGUAGES
    return {"languages": SUPPORTED_LANGUAGES}


# ── Public Portal ─────────────────────────────────────────────────────────────

# District → basin/region mapping for public search
_DISTRICT_BASIN_MAP = {
    # Assam
    "guwahati": "IN-BRAHMAPUTRA", "dibrugarh": "IN-BRAHMAPUTRA",
    "jorhat": "IN-BRAHMAPUTRA", "dhubri": "IN-BRAHMAPUTRA",
    "barpeta": "IN-BRAHMAPUTRA", "lakhimpur": "IN-BRAHMAPUTRA",
    "silchar": "IN-BRAHMAPUTRA", "tezpur": "IN-BRAHMAPUTRA",
    # Bihar
    "patna": "IN-GANGA", "muzaffarpur": "IN-GANGA", "darbhanga": "IN-GANGA",
    "supaul": "IN-GANGA", "madhubani": "IN-GANGA", "samastipur": "IN-GANGA",
    "bhagalpur": "IN-GANGA", "vaishali": "IN-GANGA",
    # West Bengal
    "kolkata": "IN-GANGA", "howrah": "IN-GANGA", "malda": "IN-GANGA",
    "murshidabad": "IN-GANGA", "nadia": "IN-GANGA",
    # Uttar Pradesh
    "varanasi": "IN-GANGA", "allahabad": "IN-GANGA", "prayagraj": "IN-GANGA",
    "kanpur": "IN-GANGA", "lucknow": "IN-GANGA", "agra": "IN-GANGA",
    # Odisha
    "cuttack": "IN-MAHANADI", "puri": "IN-MAHANADI", "bhubaneswar": "IN-MAHANADI",
    "kendrapara": "IN-MAHANADI", "jagatsinghpur": "IN-MAHANADI", "balasore": "IN-MAHANADI",
    # Andhra Pradesh / Telangana
    "rajahmundry": "IN-GODAVARI", "eluru": "IN-GODAVARI",
    "vijayawada": "IN-KRISHNA", "guntur": "IN-KRISHNA",
    "hyderabad": "IN-GODAVARI", "warangal": "IN-GODAVARI",
    # Karnataka / Tamil Nadu
    "bengaluru": "IN-KAVERI", "mysuru": "IN-KAVERI", "mandya": "IN-KAVERI",
    "trichy": "IN-KAVERI", "thanjavur": "IN-KAVERI", "nagapattinam": "IN-KAVERI",
    # Madhya Pradesh / Gujarat
    "jabalpur": "IN-NARMADA", "hoshangabad": "IN-NARMADA",
    "surat": "IN-NARMADA", "vadodara": "IN-NARMADA", "bharuch": "IN-NARMADA",
    # Punjab
    "amritsar": "IN-INDUS", "ludhiana": "IN-INDUS", "jalandhar": "IN-INDUS",
}


@app.get(_api("public/risk"))
async def get_public_risk(city: str = "", district: str = "", lang: str = "en"):
    """
    Public-facing flood risk for a city or district.
    Returns plain-language risk with action guide in the requested language.
    No authentication required.
    """
    try:
        from .translations import t, TRANSLATIONS

        query = (city or district).lower().strip()
        if not query:
            raise HTTPException(status_code=400, detail="city or district is required")

        # Find matching basin
        region_code = _DISTRICT_BASIN_MAP.get(query)

        # Get live watershed data
        watersheds = db.get_watersheds(str(_db_path))

        # Filter by region if found, else search by name
        if region_code:
            matches = [w for w in watersheds
                       if w.get("region_code") == region_code]
        else:
            matches = [w for w in watersheds
                       if query in (w.get("name") or "").lower()
                       or query in (w.get("region") or "").lower()]

        if not matches:
            # Return national average if no match
            matches = watersheds

        # Compute aggregate risk
        risk_scores = [float(w.get("risk_score") or 0) for w in matches]
        avg_risk    = sum(risk_scores) / len(risk_scores) if risk_scores else 0
        max_risk    = max(risk_scores) if risk_scores else 0
        use_risk    = max_risk  # show worst case for public safety

        # Determine level
        if use_risk >= 8.0:
            level_key  = "risk_critical"
            action_key = "action_critical"
            color      = "#ef4444"
        elif use_risk >= 6.0:
            level_key  = "risk_high"
            action_key = "action_high"
            color      = "#f97316"
        elif use_risk >= 4.0:
            level_key  = "risk_moderate"
            action_key = "action_moderate"
            color      = "#eab308"
        else:
            level_key  = "risk_low"
            action_key = "action_low"
            color      = "#22c55e"

        # Rising sites count
        rising = sum(1 for w in matches if w.get("trend") == "rising")

        # Active alerts for this region
        all_alerts = db.get_active_alerts(str(_db_path), limit=50)
        local_alerts = []
        if region_code:
            local_alerts = [a for a in all_alerts
                            if region_code in str(a.get("watershed", "")).upper()
                            or query in str(a.get("watershed", "")).lower()]
        else:
            local_alerts = all_alerts[:3]

        return {
            "query":        city or district,
            "region_code":  region_code,
            "risk_score":   round(use_risk, 1),
            "risk_level":   t(level_key, lang),
            "risk_level_en": level_key.replace("risk_", "").upper(),
            "color":        color,
            "action":       t(action_key, lang),
            "emergency":    t("emergency_contact", lang),
            "rising_sites": rising,
            "sites_checked": len(matches),
            "alerts":       [
                {
                    "type":    a.get("alert_type", "Alert"),
                    "message": a.get("message", ""),
                    "severity": a.get("severity", ""),
                }
                for a in local_alerts[:3]
            ],
            "rivers": [
                {
                    "name":     w.get("name", ""),
                    "risk":     round(float(w.get("risk_score") or 0), 1),
                    "trend":    t(f"trend_{w.get('trend','stable')}", lang),
                    "level_en": (
                        "CRITICAL" if float(w.get("risk_score") or 0) >= 8 else
                        "HIGH"     if float(w.get("risk_score") or 0) >= 6 else
                        "MODERATE" if float(w.get("risk_score") or 0) >= 4 else "LOW"
                    ),
                }
                for w in sorted(matches, key=lambda x: float(x.get("risk_score") or 0),
                                reverse=True)[:5]
            ],
            "last_updated": matches[0].get("last_updated") if matches else None,
            "lang":         lang,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"public/risk error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("public/map"))
async def get_public_map_data():
    """
    Lightweight data for the public India risk map.
    Returns all watersheds with just name, coords, risk level, and color.
    """
    try:
        watersheds = db.get_watersheds(str(_db_path))
        return {
            "sites": [
                {
                    "id":     w.get("id"),
                    "name":   w.get("name", ""),
                    "lat":    w.get("location_lat"),
                    "lng":    w.get("location_lng"),
                    "risk":   round(float(w.get("risk_score") or 0), 1),
                    "level":  w.get("current_risk_level", "Low"),
                    "trend":  w.get("trend", "stable"),
                    "region": w.get("region_code", ""),
                    "color": (
                        "#ef4444" if float(w.get("risk_score") or 0) >= 8 else
                        "#f97316" if float(w.get("risk_score") or 0) >= 6 else
                        "#eab308" if float(w.get("risk_score") or 0) >= 4 else
                        "#22c55e"
                    ),
                }
                for w in watersheds
                if w.get("location_lat") and w.get("location_lng")
            ],
            "summary": db.get_dashboard_summary(str(_db_path)),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("public/districts"))
async def get_searchable_districts():
    """Return list of all searchable cities and districts."""
    districts = sorted(set(_DISTRICT_BASIN_MAP.keys()))
    return {"districts": districts, "count": len(districts)}


# ── User Accounts ─────────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    name: str
    password: str
    email: Optional[str] = None
    phone: Optional[str] = None
    home_district: Optional[str] = None
    home_state: Optional[str] = None
    language: str = "en"
    alert_threshold: str = "HIGH"


class LoginRequest(BaseModel):
    identifier: str   # email or phone
    password: str


class PreferencesRequest(BaseModel):
    home_district: Optional[str] = None
    home_state: Optional[str] = None
    language: Optional[str] = None
    alert_threshold: Optional[str] = None
    alert_sms: Optional[bool] = None
    alert_email: Optional[bool] = None
    alert_whatsapp: Optional[bool] = None


def _get_user_from_token(token: str) -> Optional[Dict[str, Any]]:
    """Extract user from Bearer token (user session token)."""
    from .user_accounts import get_user_by_token
    if not token or token == "dev-token":
        return None
    return get_user_by_token(str(_db_path), token)


@app.post(_api("user/register"))
async def register_user_endpoint(request: RegisterRequest):
    """Register a new user account."""
    try:
        from .user_accounts import register_user, init_user_tables
        init_user_tables(str(_db_path))
        user = register_user(
            str(_db_path),
            name=request.name,
            password=request.password,
            email=request.email,
            phone=request.phone,
            home_district=request.home_district,
            home_state=request.home_state,
            language=request.language,
            alert_threshold=request.alert_threshold,
        )
        return {"status": "success", "message": "Registration successful", "user": user}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        log.error(f"user/register error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(_api("user/login"))
async def login_user_endpoint(request: LoginRequest):
    """Login with email or phone + password."""
    try:
        from .user_accounts import login_user, init_user_tables
        init_user_tables(str(_db_path))
        result = login_user(str(_db_path), request.identifier, request.password)
        if not result:
            raise HTTPException(status_code=401, detail="Invalid credentials")
        return {"status": "success", "user": result, "token": result.get("session_token")}
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"user/login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(_api("user/logout"))
async def logout_user_endpoint(request: Request):
    """Logout and invalidate session token."""
    try:
        from .user_accounts import logout_user
        auth = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        if token and token != "dev-token":
            logout_user(str(_db_path), token)
        return {"status": "success", "message": "Logged out"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("user/me"))
async def get_current_user(request: Request):
    """Get current user profile from session token."""
    try:
        auth  = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        user  = _get_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        # Add unread alert count
        from .user_accounts import get_unread_count
        user["unread_alerts"] = get_unread_count(str(_db_path), user["id"])
        return user
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put(_api("user/preferences"))
async def update_preferences(request: Request, body: PreferencesRequest):
    """Update user preferences."""
    try:
        from .user_accounts import update_user_preferences
        auth  = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        user  = _get_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        updated = update_user_preferences(
            str(_db_path), user["id"],
            home_district=body.home_district,
            home_state=body.home_state,
            language=body.language,
            alert_threshold=body.alert_threshold,
            alert_sms=body.alert_sms,
            alert_email=body.alert_email,
            alert_whatsapp=body.alert_whatsapp,
        )
        return {"status": "success", "user": updated}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("user/alerts"))
async def get_user_alerts(request: Request, limit: int = 50):
    """Get personalized alert history for the logged-in user."""
    try:
        from .user_accounts import get_user_alert_history, get_unread_count
        auth  = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        user  = _get_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        alerts   = get_user_alert_history(str(_db_path), user["id"], limit)
        unread   = get_unread_count(str(_db_path), user["id"])
        return {"alerts": alerts, "unread": unread, "total": len(alerts)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post(_api("user/alerts/{alert_id}/acknowledge"))
async def acknowledge_user_alert(alert_id: int, request: Request):
    """Mark an alert as read/acknowledged."""
    try:
        from .user_accounts import acknowledge_alert
        auth  = request.headers.get("Authorization", "")
        token = auth.replace("Bearer ", "").strip()
        user  = _get_user_from_token(token)
        if not user:
            raise HTTPException(status_code=401, detail="Not authenticated")
        ok = acknowledge_alert(str(_db_path), user["id"], alert_id)
        if not ok:
            raise HTTPException(status_code=404, detail="Alert not found")
        return {"status": "success"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Explainability, Uncertainty, Evacuation, Soil Moisture, Offline Mode APIs
# =============================================================================

# ── Explainability ────────────────────────────────────────────────────────────

@app.get(_api("explain/batch"))
async def explain_top_risk_watersheds(top_n: int = 5, model: str = "random_forest"):
    """Explain predictions for the top-N highest risk watersheds."""
    try:
        from .shap_explainer import get_explainer

        watersheds = db.get_watersheds(str(_db_path))
        top = sorted(watersheds, key=lambda w: float(w.get("risk_score") or 0),
                     reverse=True)[:top_n]

        explainer = get_explainer()
        results = []
        for ws in top:
            try:
                exp = explainer.explain_prediction(dict(ws), model_name=model)
                results.append({
                    "watershed_id":   ws.get("id"),
                    "watershed_name": ws.get("name"),
                    "risk_score":     ws.get("risk_score"),
                    "top_drivers":    exp.top_drivers,
                    "risk_narrative": exp.risk_narrative,
                    "method":         exp.method,
                    "top_features":   [
                        {"feature": c.feature_label, "contribution": c.shap_value,
                         "direction": c.direction}
                        for c in exp.feature_contributions[:5]
                    ],
                })
            except Exception as ex:
                log.warning(f"Explanation failed for {ws.get('name')}: {ex}")

        return {
            "count":     len(results),
            "model":     model,
            "results":   results,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"explain/batch error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("explain/{watershed_id}"))
async def explain_prediction(watershed_id: int, model: str = "random_forest"):
    """
    Explain why a watershed received its current flood risk score.

    Uses SHAP TreeExplainer (Random Forest), gradient saliency (LSTM/GRU/Transformer),
    or physics-informed permutation proxy as fallback.

    Query params
    ------------
    model : random_forest | lstm | gru | transformer  (default: random_forest)
    """
    try:
        from .shap_explainer import get_explainer

        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if ws is None:
            raise HTTPException(status_code=404, detail=f"Watershed {watershed_id} not found")

        explainer = get_explainer()
        explanation = explainer.explain_prediction(dict(ws), model_name=model)

        return {
            "watershed_id":    watershed_id,
            "watershed_name":  ws.get("name"),
            "model":           model,
            "explanation":     explanation.to_dict(),
            "timestamp":       datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"explain/{watershed_id} error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Uncertainty Quantification ────────────────────────────────────────────────

@app.get(_api("uncertainty/summary"))
async def get_uncertainty_summary(horizon: int = 24):
    """Get uncertainty summary for all high-risk watersheds (risk_score >= 6)."""
    try:
        from .uncertainty import get_uncertainty_engine

        watersheds = db.get_watersheds(str(_db_path))
        high_risk  = [w for w in watersheds if float(w.get("risk_score") or 0) >= 6.0]

        engine  = get_uncertainty_engine()
        results = []
        for ws in high_risk[:8]:
            try:
                r = await engine.quantify(dict(ws), horizon_hours=horizon)
                results.append({
                    "watershed_id":      ws.get("id"),
                    "watershed_name":    ws.get("name"),
                    "risk_score":        ws.get("risk_score"),
                    "total_uncertainty": r.total_uncertainty,
                    "uncertainty_level": r.uncertainty_level,
                    "reliable":          r.reliable,
                    "interval_90_low":   r.intervals[0].lower_risk if r.intervals else None,
                    "interval_90_high":  r.intervals[0].upper_risk if r.intervals else None,
                    "method":            r.method_used,
                })
            except Exception as ex:
                log.warning(f"Uncertainty failed for {ws.get('name')}: {ex}")

        return {
            "horizon_hours": horizon,
            "count":         len(results),
            "results":       results,
            "timestamp":     datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"uncertainty/summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("uncertainty/{watershed_id}"))
async def get_prediction_uncertainty(watershed_id: int,
                                      horizon: int = 24,
                                      alpha: float = 0.10):
    """
    Get prediction uncertainty (confidence intervals) for a watershed.
    Returns Monte Carlo Dropout intervals, bootstrap quantiles,
    epistemic + aleatoric decomposition, and reliability flag.
    """
    try:
        from .uncertainty import get_uncertainty_engine

        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if ws is None:
            raise HTTPException(status_code=404, detail=f"Watershed {watershed_id} not found")

        engine = get_uncertainty_engine()
        result = await engine.quantify(dict(ws), horizon_hours=horizon, alpha=alpha)

        return {
            "watershed_id":    watershed_id,
            "watershed_name":  ws.get("name"),
            "uncertainty":     result.to_dict(),
            "timestamp":       datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"uncertainty/{watershed_id} error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Evacuation Planning ───────────────────────────────────────────────────────

@app.get(_api("evacuation/plan"))
async def get_evacuation_plan():
    """
    Generate a full district-level evacuation plan based on current watershed risk data.

    Returns:
    - Critical and high-risk districts
    - Evacuation routes with highway assignments
    - Shelter locations with capacity
    - NDRF deployment plan with ETA
    - Resource allocation (boats, helicopters, relief kits)
    - Action steps by severity level
    """
    try:
        from .evacuation import get_evacuation_planner

        watersheds = db.get_watersheds(str(_db_path))
        alerts     = db.get_active_alerts(str(_db_path), limit=20)

        planner = get_evacuation_planner()
        plan    = planner.generate_plan(
            [dict(w) for w in watersheds],
            [dict(a) for a in alerts],
        )
        return {
            "status":    "success",
            "plan":      plan.to_dict(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"evacuation/plan error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("evacuation/district/{district_name}"))
async def get_district_evacuation_plan(district_name: str):
    """
    Get a detailed evacuation plan for a specific India district.

    Examples: Guwahati, Patna, Cuttack, Rajahmundry, Vijayawada
    """
    try:
        from .evacuation import get_evacuation_planner

        # Look up risk score for this district's basin from live watersheds
        watersheds = db.get_watersheds(str(_db_path))
        planner    = get_evacuation_planner()

        # Try to find matching watershed risk
        risk_score = 5.0
        from .evacuation import DISTRICT_DATA
        ddata = DISTRICT_DATA.get(district_name, {})
        basin = ddata.get("basin", "")
        for ws in watersheds:
            if ws.get("region_code") == basin:
                risk_score = max(risk_score, float(ws.get("risk_score") or 0))

        plan = planner.get_district_plan(district_name, risk_score)
        return {
            "status":      "success",
            "district":    district_name,
            "risk_score":  risk_score,
            "plan":        plan.to_dict(),
            "timestamp":   datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"evacuation/district/{district_name} error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("evacuation/districts"))
async def list_evacuation_districts():
    """List all districts for which evacuation plans are available."""
    try:
        from .evacuation import DISTRICT_DATA
        return {
            "districts": [
                {
                    "name":    name,
                    "state":   d["state"],
                    "basin":   d["basin"],
                    "population_at_risk": d["pop_risk"],
                    "vulnerability_score": d["vuln"],
                }
                for name, d in DISTRICT_DATA.items()
            ],
            "count": len(DISTRICT_DATA),
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# ── Soil Moisture ─────────────────────────────────────────────────────────────

@app.get(_api("soil-moisture/summary"))
async def get_soil_moisture_summary():
    """
    Get soil moisture summary for all watersheds.
    Returns saturation levels and risk contributions in parallel.
    """
    try:
        from .soil_moisture import enrich_watersheds_with_soil_moisture

        watersheds = db.get_watersheds(str(_db_path))
        enriched   = await enrich_watersheds_with_soil_moisture(
            [dict(w) for w in watersheds[:12]]
        )

        summary = []
        for ws in enriched:
            sm = ws.get("soil_moisture")
            if sm:
                summary.append({
                    "watershed_id":      ws.get("id"),
                    "watershed_name":    ws.get("name"),
                    "saturation_pct":    sm.get("saturation_pct"),
                    "category":          sm.get("saturation_category"),
                    "risk_contribution": sm.get("risk_contribution"),
                    "data_source":       sm.get("data_source"),
                    "data_quality":      sm.get("data_quality"),
                })

        sat_vals        = [s["saturation_pct"] for s in summary if s["saturation_pct"] is not None]
        avg_sat         = round(sum(sat_vals) / len(sat_vals), 1) if sat_vals else 0.0
        saturated_count = sum(1 for s in summary if s.get("category") in ("WET", "SATURATED"))

        return {
            "watersheds":         summary,
            "avg_saturation_pct": avg_sat,
            "saturated_count":    saturated_count,
            "total_checked":      len(summary),
            "timestamp":          datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"soil-moisture/summary error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("soil-moisture/{watershed_id}"))
async def get_soil_moisture(watershed_id: int):
    """
    Get real soil moisture data for a watershed from Open-Meteo ERA5-Land API.
    Returns volumetric water content, field-capacity saturation %, and risk contribution.
    """
    try:
        from .soil_moisture import get_soil_moisture_service

        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if ws is None:
            raise HTTPException(status_code=404, detail=f"Watershed {watershed_id} not found")

        lat = float(ws.get("location_lat") or 0)
        lon = float(ws.get("location_lng") or 0)
        if not lat or not lon:
            raise HTTPException(status_code=400,
                                detail="Watershed has no lat/lon coordinates")

        svc    = get_soil_moisture_service()
        result = await svc.fetch(lat, lon, ws.get("region_code", "IN-GANGA"))

        return {
            "watershed_id":   watershed_id,
            "watershed_name": ws.get("name"),
            "soil_moisture":  result.to_dict(),
            "timestamp":      datetime.now(timezone.utc).isoformat(),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"soil-moisture/{watershed_id} error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ── Offline / System Mode ─────────────────────────────────────────────────────

@app.get(_api("system/mode"))
async def get_system_mode():
    """
    Get current system operation mode and API health status.

    Modes: ONLINE | DEGRADED | CACHED | OFFLINE

    Returns API reachability, cache stats, and recovery recommendations.
    """
    try:
        from .offline_mode import get_data_manager

        mgr    = get_data_manager()
        report = await mgr.get_mode_report()
        return report.to_dict()
    except Exception as e:
        log.error(f"system/mode error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(_api("system/cache/clear"))
async def clear_stale_cache(user_id: UserID):
    """Clear stale offline cache entries older than 24 hours."""
    try:
        from .offline_mode import get_data_manager

        mgr     = get_data_manager()
        deleted = mgr.clear_stale_cache()
        return {
            "status":          "success",
            "entries_deleted": deleted,
            "timestamp":       datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"system/cache/clear error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("system/health-extended"))
async def get_extended_health():
    """
    Extended health check including all subsystems:
    - Redis connectivity
    - AI agents status
    - ML model availability
    - External API reachability
    - Cache status
    - Database integrity
    """
    try:
        from .offline_mode import get_data_manager
        from .ml_models    import get_ensemble

        health: Dict[str, Any] = {}

        # Redis
        try:
            _redis.ping()
            health["redis"] = {"status": "connected"}
        except Exception as e:
            health["redis"] = {"status": "error", "detail": str(e)}

        # AI agents
        if _agent_manager:
            try:
                summary = await _agent_manager.get_dashboard_summary()
                health["agents"] = {
                    "status":  "running",
                    "running": summary.get("running_agents", 0),
                    "total":   summary.get("total_agents", 0),
                }
            except Exception as e:
                health["agents"] = {"status": "error", "detail": str(e)}
        else:
            health["agents"] = {"status": "disabled"}

        # ML models
        try:
            ens = get_ensemble()
            health["ml_models"] = {
                "trained":   ens.models_trained(),
                "available": ens.models_available(),
            }
        except Exception as e:
            health["ml_models"] = {"status": "error", "detail": str(e)}

        # External APIs + offline mode
        try:
            mgr    = get_data_manager()
            report = await mgr.get_mode_report()
            health["data_sources"] = {
                "mode":         report.current_mode,
                "cache_entries": report.cache_entries,
                "message":      report.message,
            }
        except Exception as e:
            health["data_sources"] = {"status": "error", "detail": str(e)}

        # Database
        try:
            summary = db.get_dashboard_summary(str(_db_path))
            health["database"] = {
                "status":       "ok",
                "watersheds":   summary.get("total_watersheds", 0),
                "active_alerts": summary.get("active_alerts", 0),
            }
        except Exception as e:
            health["database"] = {"status": "error", "detail": str(e)}

        # Overall status
        errors = [k for k, v in health.items()
                  if isinstance(v, dict) and v.get("status") == "error"]
        overall = "healthy" if not errors else f"degraded ({', '.join(errors)} have issues)"

        return {
            "overall_status": overall,
            "subsystems":     health,
            "timestamp":      datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"system/health-extended error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Research API Endpoints  (/api/research/*)
# =============================================================================
# These endpoints expose the four research modules to the UI dashboard and
# allow programmatic access for paper-writing workflows.

@app.get(_api("research/status"))
async def research_status():
    """
    Quick summary of which research modules are active and their readiness state.
    Safe to poll frequently — no heavy computation.
    """
    try:
        # ML status via PredictorAgent if running
        ml_status: Dict[str, Any] = {"available": False}
        if _agent_manager:
            try:
                predictor = _agent_manager._agents.get("predictor")
                if predictor and hasattr(predictor, "get_ml_status"):
                    ml_status = predictor.get_ml_status()
            except Exception:
                pass

        from .ml_models import TORCH_AVAILABLE, SKLEARN_AVAILABLE, get_ensemble
        ens = get_ensemble()
        return {
            "torch_available": TORCH_AVAILABLE,
            "sklearn_available": SKLEARN_AVAILABLE,
            "models_trained": ens.models_trained(),
            "models_available": ens.models_available(),
            "ml_status": ml_status,
            "research_modules": {
                "ml_models": "active",
                "validation": "active",
                "llm_ablation": "active",
                "baselines": "active",
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"research/status error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(_api("research/train-models"))
async def train_ml_models(user_id: UserID, epochs: int = 50):
    """
    Trigger ML model training (LSTM, GRU, Transformer, Random Forest).
    Runs asynchronously — returns immediately with a job token.
    Poll /api/research/model-metrics to see when training completes.
    """
    try:
        from .ml_models import get_ensemble
        ens = get_ensemble()

        async def _train():
            try:
                results = await ens.train_all(epochs=epochs)
                log.info(f"Training complete for {list(results.keys())}")
            except Exception as e:
                log.error(f"Background training failed: {e}")

        asyncio.create_task(_train())

        return {
            "status": "training_started",
            "epochs": epochs,
            "message": "ML model training started in background. "
                       "Poll /api/research/model-metrics for results.",
            "started_at": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"research/train-models error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("research/model-metrics"))
async def get_model_metrics():
    """
    Return training metrics for all ML models.
    Includes val_RMSE, val_MAE, training time, and feature importances.
    """
    try:
        from .ml_models import get_ensemble
        ens = get_ensemble()
        summary = ens.get_training_summary()
        return {
            "models": summary,
            "models_available": ens.models_available(),
            "models_trained": ens.models_trained(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"research/model-metrics error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post(_api("research/validation"))
async def run_validation(
    models: Optional[List[str]] = None,
    horizons: Optional[List[int]] = None,
):
    """
    Run back-test validation against the India Historical Flood Events dataset.
    Returns RMSE, MAE, NSE, KGE, CSI, POD, FAR, F1 for each model × horizon.

    Query params
    ------------
    models   : comma-separated list (lstm,gru,transformer,random_forest,rule_based)
    horizons : comma-separated list of hours (6,12,24,48,72)
    """
    try:
        from .validation import ValidationEngine, generate_validation_report

        engine = ValidationEngine(db_path=str(_db_path))
        await engine.run_validation(
            models=models,
            horizons=horizons,
            persist=True,
        )

        return {
            "status": "completed",
            "comparison_table_24h": engine.comparison_table(horizon_hours=24),
            "comparison_table_48h": engine.comparison_table(horizon_hours=48),
            "all_metrics": {
                model: {str(h): m.to_dict() for h, m in hmap.items()}
                for model, hmap in engine._results.items()
            },
            "dataset_info": {
                "name": "India Historical Flood Events 2015-2024",
                "n_events": 35,
                "flood_events": 22,
                "sources": ["CWC Annual Reports", "NDMA Situation Reports", "IMD Bulletins"],
            },
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"research/validation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("research/validation/report"))
async def get_validation_report():
    """
    Return the full structured validation report including significance tests.
    Suitable for embedding in a paper appendix or exporting as JSON.
    """
    try:
        from .validation import generate_validation_report
        report = generate_validation_report(db_path=str(_db_path))
        return report
    except Exception as e:
        log.error(f"research/validation/report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("research/baselines"))
async def get_baseline_comparison(horizon: int = 24):
    """
    Run all five baselines (persistence, climatology, threshold, linear_trend, ARIMA)
    and return a comparison table at the requested horizon.
    """
    try:
        from .baselines import BaselineRunner, compare_all
        from .validation import INDIA_FLOOD_EVENTS

        runner = BaselineRunner(db_path=str(_db_path))
        runner.run_all(horizons=[horizon], persist=True)

        # Also pull ML model rows from validation for the combined table
        from .validation import ValidationEngine
        val_engine = ValidationEngine()
        await val_engine.run_validation(
            models=["lstm", "gru", "transformer", "random_forest", "rule_based"],
            horizons=[horizon],
            persist=False,
        )
        ml_rows = val_engine.comparison_table(horizon_hours=horizon)

        combined_table = runner.comparison_table(
            horizon_hours=horizon, include_ml=ml_rows)

        sig_results = compare_all(
            ml_models=["lstm", "gru", "transformer", "random_forest", "rule_based"],
            baselines=["persistence", "climatology", "threshold", "linear_trend", "arima"],
            horizon_hours=horizon,
        )

        return {
            "horizon_hours": horizon,
            "comparison_table": combined_table,
            "skill_scores": sig_results.get("skill_scores_vs_persistence", {}),
            "significance_summary": sig_results.get("summary", {}),
            "pairwise_tests_count": len(sig_results.get("pairwise_significance", [])),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"research/baselines error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("research/baselines/significance"))
async def get_significance_matrix(horizon: int = 24):
    """
    Full pairwise Wilcoxon signed-rank significance matrix:
    ML models vs baselines with p-values and Cohen's d effect sizes.
    """
    try:
        from .baselines import compare_all
        results = compare_all(
            ml_models=["lstm", "gru", "transformer", "random_forest", "rule_based"],
            baselines=["persistence", "climatology", "threshold", "linear_trend", "arima"],
            horizon_hours=horizon,
        )
        return results
    except Exception as e:
        log.error(f"research/baselines/significance error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


class AblationRequest(BaseModel):
    n_queries: Optional[int] = None        # None = all 25 queries
    use_llm_judge: bool = False            # True requires active LLM connection
    categories: Optional[List[str]] = None # filter by category


@app.post(_api("research/ablation"))
async def run_ablation_study(user_id: UserID, request: AblationRequest):
    """
    Run the three-condition LLM ablation study.

    Conditions: rule_only | llm_enhanced | llm_only
    Scored on: factual_accuracy, actionability, safety_compliance, specificity

    Set use_llm_judge=true to use the LLM-as-judge protocol (G-Eval).
    Default uses calibrated heuristic scoring (fast, no LLM needed).
    """
    try:
        from .llm_ablation import AblationStudy, ABLATION_QUERIES

        # Build LLM call function if judge is requested
        llm_fn = None
        if request.use_llm_judge:
            from .api import llm_call as _llm_call
            async def llm_fn(prompt: str, max_tokens: int = 512,
                              temperature: float = 0.3) -> str:
                return await _llm_call(prompt, max_tokens=max_tokens,
                                       temperature=temperature)

        # Optionally filter queries by category
        queries = ABLATION_QUERIES
        if request.categories:
            queries = [q for q in ABLATION_QUERIES
                       if q["category"] in request.categories]

        # Get current watershed data for context
        watersheds = db.get_watersheds(str(_db_path))
        alerts = db.get_active_alerts(str(_db_path), limit=10)

        study = AblationStudy(
            db_path=str(_db_path),
            llm_call_fn=llm_fn,
            use_llm_judge=request.use_llm_judge,
        )
        result = await study.run(
            watersheds=[dict(w) for w in watersheds],
            alerts=[dict(a) for a in alerts],
            queries=queries,
            n_queries=request.n_queries,
        )
        report = study.generate_report(result)

        return {
            "status": "completed",
            "run_id": result.run_id,
            "n_queries": result.n_queries,
            "condition_scores": result.condition_scores,
            "llm_contribution_delta": result.llm_delta,
            "paper_table": report["paper_table"],
            "interpretation": report["interpretation"],
            "category_breakdown": report["category_breakdown"],
            "scoring_method": report["scoring_method"],
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"research/ablation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("research/ablation/history"))
async def get_ablation_history(limit: int = 20):
    """Return recent ablation study results from the DB."""
    try:
        summary = db.get_ablation_summary(str(_db_path), limit=limit)
        return {
            "summary_by_condition": summary,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        log.error(f"research/ablation/history error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("research/full-report"))
async def get_full_research_report():
    """
    Generate the complete research report combining:
    - ML model validation metrics
    - Baseline comparison with significance tests
    - LLM ablation study summary (heuristic scoring)
    - Feature importance rankings

    Intended as the data source for paper tables and figures.
    """
    try:
        from .validation import generate_validation_report
        from .baselines import BaselineRunner, compare_all
        from .llm_ablation import AblationStudy, ABLATION_QUERIES
        from .ml_models import get_ensemble

        # 1. Validation report
        val_report = generate_validation_report(db_path=str(_db_path))

        # 2. Baseline comparison at 24h
        runner = BaselineRunner()
        runner.run_all(horizons=[24, 48])
        baseline_table_24h = runner.comparison_table(
            horizon_hours=24,
            include_ml=val_report.get("comparison_tables", {}).get("24h", []),
        )
        sig = compare_all(horizon_hours=24)

        # 3. Ablation (heuristic scoring, fast)
        watersheds = db.get_watersheds(str(_db_path))
        alerts = db.get_active_alerts(str(_db_path), limit=10)
        study = AblationStudy(db_path=str(_db_path), llm_call_fn=None, use_llm_judge=False)
        ablation_result = await study.run(
            watersheds=[dict(w) for w in watersheds],
            alerts=[dict(a) for a in alerts],
            n_queries=10,   # quick pass
        )
        ablation_report = study.generate_report(ablation_result)

        # 4. Feature importances (RF model)
        ens = get_ensemble()
        fi = {}
        if ens.models_trained():
            from .ml_models import _RFWrapper
            rf = ens._wrappers.get("random_forest") if ens._wrappers else None
            if rf and hasattr(rf, "feature_importances"):
                fi = rf.feature_importances()

        return {
            "report_type": "full_research_report",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "sections": {
                "ml_validation": {
                    "dataset": val_report.get("dataset"),
                    "best_model_24h": val_report.get("best_model_24h"),
                    "comparison_table_24h": val_report.get("comparison_tables", {}).get("24h", []),
                    "significance_tests": val_report.get("significance_tests", {}),
                    "summary": val_report.get("summary", {}),
                },
                "baseline_comparison": {
                    "combined_table_24h": baseline_table_24h,
                    "skill_scores": sig.get("skill_scores_vs_persistence", {}),
                    "significance_summary": sig.get("summary", {}),
                },
                "llm_ablation": {
                    "condition_scores": ablation_result.condition_scores,
                    "llm_delta": ablation_result.llm_delta,
                    "paper_table": ablation_report.get("paper_table", []),
                    "interpretation": ablation_report.get("interpretation", {}),
                },
                "feature_importances": fi,
            },
        }
    except Exception as e:
        log.error(f"research/full-report error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get(_api("research/predict/{watershed_id}"))
async def research_predict(watershed_id: int, horizon: int = 24):
    """
    Generate a live ML ensemble prediction for a specific watershed.
    Returns individual model predictions + ensemble result.
    """
    try:
        from .ml_models import get_ensemble

        watersheds = db.get_watersheds(str(_db_path))
        ws = next((w for w in watersheds if w.get("id") == watershed_id), None)
        if ws is None:
            raise HTTPException(status_code=404,
                                detail=f"Watershed {watershed_id} not found")

        ens = get_ensemble()
        pred = await ens.predict(dict(ws), horizon_hours=horizon)

        return {
            "watershed_id": watershed_id,
            "watershed_name": ws.get("name"),
            "horizon_hours": horizon,
            "ensemble": {
                "discharge_cfs": pred.ensemble_discharge_cfs,
                "risk_score": pred.ensemble_risk_score,
                "risk_level": pred.ensemble_risk_level,
                "confidence": pred.ensemble_confidence,
                "model_agreement": pred.model_agreement,
            },
            "model_predictions": [p.to_dict() for p in pred.model_predictions],
            "predicted_at": pred.predicted_at,
            "valid_at": pred.valid_at,
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"research/predict error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# =============================================================================
# Static file serving (keep LAST — catches all non-API routes)
# =============================================================================

@app.get("/{path:path}")
async def serve_static(path: str):
    """Serve static files, but exclude API routes"""
    # Don't serve static files for API routes
    if path.startswith("api/"):
        raise HTTPException(status_code=404, detail="API endpoint not found")
    
    f = server_dir / path
    return FileResponse(f if f.is_file() else server_dir / "index.html")

# =============================================================================
# Error Handlers
# =============================================================================

@app.exception_handler(404)
async def not_found_handler(request: Request, exc: HTTPException):
    return {"error": "Not found", "detail": exc.detail}


@app.exception_handler(500)
async def internal_error_handler(request: Request, exc: Exception):
    return {"error": "Internal server error", "detail": str(exc)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)