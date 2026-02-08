"""
Twitter Harvester - FastAPI Application

A serverless Cloud Run service for harvesting Twitter data using Apify
and publishing to Google Cloud Pub/Sub.
"""
import os
from uuid import uuid4
from datetime import datetime
from typing import Optional, List
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, BackgroundTasks, Response
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .models import (
    HarvestRequest, HarvestResponse, SearchType, JobStatus
)
from .apify_client import TwitterScraper
from .transformer import transform_batch
from .publisher import TwitterPublisher


# Synapse Feeds compatible request model (for workflow integration)
class SynapseSearchRequest(BaseModel):
    """Request model compatible with synapse-dev-feeds /search endpoint"""
    query: str
    source_type: str = "apify-twitter"
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
    print("Twitter Harvester starting up...")
    yield
    # Shutdown
    print("Twitter Harvester shutting down...")


app = FastAPI(
    title="Twitter Harvester",
    description="Serverless Twitter data harvester using Apify",
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
            total=request.max_tweets
        )

        # Initialize clients
        scraper = TwitterScraper()
        publisher = TwitterPublisher()

        # Scrape tweets based on search type
        raw_tweets = []

        if request.search_type == SearchType.KEYWORD:
            raw_tweets = scraper.search_tweets(
                search_terms=request.search_terms,
                max_tweets=request.max_tweets,
                start_date=request.start_date,
                end_date=request.end_date,
                include_replies=request.include_replies,
                language=request.language
            )
        elif request.search_type == SearchType.USERNAME:
            raw_tweets = scraper.scrape_user_tweets(
                usernames=request.search_terms,
                max_tweets=request.max_tweets,
                include_replies=request.include_replies
            )
        elif request.search_type == SearchType.HASHTAG:
            raw_tweets = scraper.scrape_hashtag(
                hashtags=request.search_terms,
                max_tweets=request.max_tweets,
                language=request.language
            )
        elif request.search_type == SearchType.URL:
            raw_tweets = scraper.scrape_urls(
                tweet_urls=request.search_terms
            )

        # Update progress
        jobs[job_id].progress = len(raw_tweets)
        jobs[job_id].total = len(raw_tweets)

        # Transform to Cogito schema
        transformed_tweets = transform_batch(
            tweets=raw_tweets,
            project_id=request.project_id,
            job_id=job_id
        )

        # Publish to Pub/Sub
        messages_published = publisher.publish_tweets(
            tweets=transformed_tweets,
            project_id=request.project_id,
            job_id=job_id
        )

        # Mark job complete
        jobs[job_id].status = "completed"
        jobs[job_id].progress = len(transformed_tweets)

        print(f"Job {job_id} completed: {len(transformed_tweets)} tweets, {messages_published} messages")

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
        scraper = TwitterScraper()
        publisher = TwitterPublisher()

        # Parse dates
        start_date = parse_date(request.start_date)
        end_date = parse_date(request.end_date)

        # Scrape tweets using keyword search
        raw_tweets = scraper.search_tweets(
            search_terms=[request.query],
            max_tweets=request.limit or 100,
            start_date=start_date,
            end_date=end_date,
            include_replies=False,
            language=request.language
        )

        # Update progress
        jobs[job_id].progress = len(raw_tweets)
        jobs[job_id].total = len(raw_tweets)

        # Transform to Cogito schema
        transformed_tweets = transform_batch(
            tweets=raw_tweets,
            project_id=request.project_id,
            job_id=job_id
        )

        # Publish to Pub/Sub
        messages_published = publisher.publish_tweets(
            tweets=transformed_tweets,
            project_id=request.project_id,
            job_id=job_id
        )

        # Mark job complete
        jobs[job_id].status = "completed"
        jobs[job_id].progress = len(transformed_tweets)

        print(f"Synapse search job {job_id} completed: {len(transformed_tweets)} tweets, {messages_published} messages")

    except Exception as e:
        jobs[job_id].status = "failed"
        jobs[job_id].error = str(e)
        print(f"Synapse search job {job_id} failed: {e}")


@app.get("/")
async def root():
    """Root endpoint"""
    return {"status": "healthy", "service": "twitter-harvester", "version": "1.0.0"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "twitter-harvester"}


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
    if request.source_type not in ["apify-twitter", "twitter-api"]:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported source_type: {request.source_type}. Use 'apify-twitter'"
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
async def harvest_tweets(
    request: HarvestRequest,
    background_tasks: BackgroundTasks
):
    """
    Start a Twitter harvesting job.

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
        tweets_harvested=0,
        tweets_published=0,
        message=f"Harvest job {job_id} started. Check /jobs/{job_id} for status."
    )


@app.post("/harvest/sync", response_model=HarvestResponse)
async def harvest_tweets_sync(request: HarvestRequest):
    """
    Run a Twitter harvesting job synchronously.

    Use this for smaller jobs or when you need immediate results.
    For larger jobs, use the async /harvest endpoint.
    """
    job_id = str(uuid4())

    try:
        # Initialize clients
        scraper = TwitterScraper()
        publisher = TwitterPublisher()

        # Scrape tweets based on search type
        raw_tweets = []

        if request.search_type == SearchType.KEYWORD:
            raw_tweets = scraper.search_tweets(
                search_terms=request.search_terms,
                max_tweets=request.max_tweets,
                start_date=request.start_date,
                end_date=request.end_date,
                include_replies=request.include_replies,
                language=request.language
            )
        elif request.search_type == SearchType.USERNAME:
            raw_tweets = scraper.scrape_user_tweets(
                usernames=request.search_terms,
                max_tweets=request.max_tweets,
                include_replies=request.include_replies
            )
        elif request.search_type == SearchType.HASHTAG:
            raw_tweets = scraper.scrape_hashtag(
                hashtags=request.search_terms,
                max_tweets=request.max_tweets,
                language=request.language
            )
        elif request.search_type == SearchType.URL:
            raw_tweets = scraper.scrape_urls(
                tweet_urls=request.search_terms
            )

        # Transform to Cogito schema
        transformed_tweets = transform_batch(
            tweets=raw_tweets,
            project_id=request.project_id,
            job_id=job_id
        )

        # Publish to Pub/Sub
        messages_published = publisher.publish_tweets(
            tweets=transformed_tweets,
            project_id=request.project_id,
            job_id=job_id
        )

        return HarvestResponse(
            success=True,
            job_id=job_id,
            project_id=request.project_id,
            tweets_harvested=len(raw_tweets),
            tweets_published=len(transformed_tweets),
            message=f"Successfully harvested {len(transformed_tweets)} tweets"
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


# Cloud Run entry point
if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
