"""
Gazette Harvester - FastAPI Application

A serverless Cloud Run service for harvesting news articles using NewsAPI
and publishing to Google Cloud Pub/Sub.
"""
import os
from uuid import uuid4
from datetime import datetime
from typing import Optional
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .models import (
    HarvestRequest, HarvestResponse, SearchType, SortBy, JobStatus
)
from .newsapi_client import NewsClient
from .transformer import transform_batch
from .publisher import NewsPublisher


# Synapse Feeds compatible request model (for workflow integration)
class SynapseSearchRequest(BaseModel):
    """Request model compatible with synapse-dev-feeds /search endpoint"""
    query: str
    source_type: str = "webzio-news"
    project_id: str
    client_id: str = "cogito-client"
    language: Optional[str] = "en"
    start_date: Optional[str] = None  # YYYY-MM-DD format
    end_date: Optional[str] = None    # YYYY-MM-DD format
    limit: Optional[int] = 100
    place: Optional[str] = None
    country: Optional[str] = None
    sort_by: Optional[str] = None
    env: Optional[str] = "dev"
    callback_url: Optional[str] = None


# In-memory job tracking (use Redis/Firestore for production)
jobs: dict = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    print("Gazette Harvester starting up...")
    yield
    # Shutdown
    print("Gazette Harvester shutting down...")


app = FastAPI(
    title="Gazette Harvester",
    description="Serverless news article harvester using NewsAPI",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def parse_date(date_str: Optional[str]) -> Optional[datetime]:
    """Parse date string in YYYY-MM-DD format to datetime"""
    if not date_str:
        return None
    try:
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        # Try ISO format as fallback
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except ValueError:
            return None


def run_harvest_job(
    job_id: str,
    request: HarvestRequest
):
    """
    Background task to run the harvest job.
    """
    try:
        jobs[job_id] = JobStatus(
            job_id=job_id,
            status="running",
            progress=0,
            total=request.max_articles
        )

        # Initialize clients
        news_client = NewsClient()
        publisher = NewsPublisher()

        # Fetch articles based on search type
        raw_articles = []

        if request.search_type == SearchType.EVERYTHING:
            raw_articles = news_client.fetch_all_articles(
                keywords=request.keywords if request.keywords else None,
                sources=request.sources if request.sources else None,
                domains=request.domains if request.domains else None,
                language=request.language,
                sort_by=request.sort_by.value,
                start_date=request.start_date,
                end_date=request.end_date,
                max_articles=request.max_articles
            )
        elif request.search_type == SearchType.TOP_HEADLINES:
            raw_articles = news_client.fetch_top_headlines_all(
                keywords=request.keywords if request.keywords else None,
                sources=request.sources if request.sources else None,
                category=request.category,
                country=request.country,
                language=request.language,
                max_articles=request.max_articles
            )

        # Update progress
        jobs[job_id].progress = len(raw_articles)
        jobs[job_id].total = len(raw_articles)

        # Transform to Cogito schema
        transformed_articles = transform_batch(
            articles=raw_articles,
            project_id=request.project_id,
            job_id=job_id,
            category=request.category
        )

        # Publish to Pub/Sub
        messages_published = publisher.publish_articles(
            articles=transformed_articles,
            project_id=request.project_id,
            job_id=job_id
        )

        # Mark job complete
        jobs[job_id].status = "completed"
        jobs[job_id].progress = len(transformed_articles)

        print(f"Job {job_id} completed: {len(transformed_articles)} articles, {messages_published} messages")

    except Exception as e:
        jobs[job_id].status = "failed"
        jobs[job_id].error = str(e)
        print(f"Job {job_id} failed: {e}")


def run_synapse_search_job(
    job_id: str,
    request: SynapseSearchRequest
):
    """
    Background task to run a synapse-feeds compatible search job.
    """
    try:
        jobs[job_id] = JobStatus(
            job_id=job_id,
            status="running",
            progress=0,
            total=request.limit or 100
        )

        # Initialize clients
        news_client = NewsClient()
        publisher = NewsPublisher()

        # Parse dates
        start_date = parse_date(request.start_date)
        end_date = parse_date(request.end_date)

        # Fetch articles using keyword search
        raw_articles = news_client.fetch_all_articles(
            keywords=[request.query],
            sources=None,
            domains=None,
            language=request.language,
            sort_by="publishedAt",
            start_date=start_date,
            end_date=end_date,
            max_articles=request.limit or 100
        )

        # Update progress
        jobs[job_id].progress = len(raw_articles)
        jobs[job_id].total = len(raw_articles)

        # Transform to Cogito schema
        transformed_articles = transform_batch(
            articles=raw_articles,
            project_id=request.project_id,
            job_id=job_id,
            category=None
        )

        # Publish to Pub/Sub
        messages_published = publisher.publish_articles(
            articles=transformed_articles,
            project_id=request.project_id,
            job_id=job_id
        )

        # Mark job complete
        jobs[job_id].status = "completed"
        jobs[job_id].progress = len(transformed_articles)

        print(f"Synapse search job {job_id} completed: {len(transformed_articles)} articles, {messages_published} messages")

    except Exception as e:
        jobs[job_id].status = "failed"
        jobs[job_id].error = str(e)
        print(f"Synapse search job {job_id} failed: {e}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {"status": "healthy", "service": "gazette-harvester", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "gazette-harvester"}


@app.post("/search", status_code=202)
async def synapse_search(
    request: SynapseSearchRequest,
    background_tasks: BackgroundTasks
):
    """
    Synapse Feeds compatible search endpoint.

    This endpoint matches the synapse-dev-feeds /search API for workflow integration.
    Accepts the same payload format and returns a compatible response.
    """
    job_id = str(uuid4())

    # Validate source_type
    if request.source_type not in ["webzio-news", "webzio-reviews", "newsapi"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source_type: {request.source_type}. Use 'webzio-news' or 'newsapi'"
        )

    # Start background task
    background_tasks.add_task(run_synapse_search_job, job_id, request)

    # Return synapse-feeds compatible response
    return {
        "status": "Started.",
        "job_id": job_id,
        "payload": {
            "query": request.query,
            "source_type": request.source_type,
            "project_id": request.project_id,
            "limit": request.limit
        }
    }


@app.post("/harvest", response_model=HarvestResponse)
async def harvest_articles(
    request: HarvestRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a news harvesting job.

    The job runs asynchronously in the background.
    Use the /jobs/{job_id} endpoint to check status.
    """
    job_id = str(uuid4())

    # Start background task
    background_tasks.add_task(run_harvest_job, job_id, request)

    return HarvestResponse(
        success=True,
        job_id=job_id,
        project_id=request.project_id,
        articles_harvested=0,
        articles_published=0,
        message=f"Harvest job {job_id} started. Check /jobs/{job_id} for status."
    )


@app.post("/harvest/sync", response_model=HarvestResponse)
async def harvest_articles_sync(request: HarvestRequest):
    """
    Run a news harvesting job synchronously.

    Use this for smaller jobs or when you need immediate results.
    For larger jobs, use the async /harvest endpoint.
    """
    job_id = str(uuid4())

    try:
        # Initialize clients
        news_client = NewsClient()
        publisher = NewsPublisher()

        # Fetch articles based on search type
        raw_articles = []

        if request.search_type == SearchType.EVERYTHING:
            raw_articles = news_client.fetch_all_articles(
                keywords=request.keywords if request.keywords else None,
                sources=request.sources if request.sources else None,
                domains=request.domains if request.domains else None,
                language=request.language,
                sort_by=request.sort_by.value,
                start_date=request.start_date,
                end_date=request.end_date,
                max_articles=request.max_articles
            )
        elif request.search_type == SearchType.TOP_HEADLINES:
            raw_articles = news_client.fetch_top_headlines_all(
                keywords=request.keywords if request.keywords else None,
                sources=request.sources if request.sources else None,
                category=request.category,
                country=request.country,
                language=request.language,
                max_articles=request.max_articles
            )

        # Transform to Cogito schema
        transformed_articles = transform_batch(
            articles=raw_articles,
            project_id=request.project_id,
            job_id=job_id,
            category=request.category
        )

        # Publish to Pub/Sub
        messages_published = publisher.publish_articles(
            articles=transformed_articles,
            project_id=request.project_id,
            job_id=job_id
        )

        return HarvestResponse(
            success=True,
            job_id=job_id,
            project_id=request.project_id,
            articles_harvested=len(raw_articles),
            articles_published=len(transformed_articles),
            message=f"Successfully harvested {len(transformed_articles)} articles"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/jobs/{job_id}", response_model=JobStatus)
async def get_job_status(job_id: str):
    """
    Get the status of a harvest job.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")

    return jobs[job_id]


@app.get("/jobs")
async def list_jobs():
    """
    List all jobs (for debugging).
    """
    return {"jobs": list(jobs.values())}


@app.get("/sources")
async def list_sources(
    category: str = None,
    language: str = "en",
    country: str = None
):
    """
    List available news sources.
    """
    try:
        client = NewsClient()
        response = client.get_sources(
            category=category,
            language=language,
            country=country
        )
        return response
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Cloud Run entry point
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
