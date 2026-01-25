"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import init_db
from app.api.routes import search, leads, inbox, dashboard, auth
from app.jobs.scheduler import start_scheduler, shutdown_scheduler
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    # Startup
    await init_db()
    start_scheduler()
    yield
    # Shutdown
    shutdown_scheduler()


app = FastAPI(
    title="LeadGen API",
    description="Production-grade lead generation SaaS",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
settings = get_settings()
cors_origins = [
    "http://localhost:5173",
    "http://localhost:3000",
]
# Add production frontend URL from environment if set
if hasattr(settings, 'frontend_url') and settings.frontend_url:
    cors_origins.append(settings.frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_origin_regex=r"https://lead-.*-liqen-tech\.vercel\.app",  # Match all Vercel preview URLs
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
app.include_router(search.router, prefix="/api/search", tags=["search"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(inbox.router, prefix="/api/inbox", tags=["inbox"])
app.include_router(dashboard.router, prefix="/api/dashboard", tags=["dashboard"])


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "LeadGen API"}
