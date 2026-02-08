"""
Pydantic models for Gazette/News Harvester
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class SearchType(str, Enum):
    EVERYTHING = "everything"
    TOP_HEADLINES = "top_headlines"


class SortBy(str, Enum):
    RELEVANCY = "relevancy"
    POPULARITY = "popularity"
    PUBLISHED_AT = "publishedAt"


class HarvestRequest(BaseModel):
    """Request model for harvesting news articles"""
    project_id: str = Field(..., description="Project ID for data routing")
    keywords: List[str] = Field(default=[], description="Keywords to search for")
    sources: List[str] = Field(default=[], description="News sources to filter by")
    domains: List[str] = Field(default=[], description="Domains to filter by")
    category: Optional[str] = Field(default=None, description="Category filter (business, technology, etc.)")
    country: Optional[str] = Field(default=None, description="Country code (us, gb, etc.)")
    language: Optional[str] = Field(default="en", description="Language code")
    search_type: SearchType = Field(default=SearchType.EVERYTHING, description="Type of search")
    sort_by: SortBy = Field(default=SortBy.PUBLISHED_AT, description="Sort order")
    max_articles: int = Field(default=100, ge=1, le=1000, description="Maximum articles to harvest")
    start_date: Optional[datetime] = Field(default=None, description="Start date filter")
    end_date: Optional[datetime] = Field(default=None, description="End date filter")


class SentimentResult(BaseModel):
    """Sentiment analysis result"""
    label: str
    polarity: float
    subjectivity: float
    label_probability: float
    model: str = "gliner2"


class EmotionResult(BaseModel):
    """Emotion detection result"""
    label: str
    score: float
    model: str = "gliner2"


class TopicResult(BaseModel):
    """Topic classification result"""
    label: str
    score: float
    model: str = "gliner2"


class ArticleSource(BaseModel):
    """News source information"""
    id: Optional[str] = None
    name: str


class Article(BaseModel):
    """Normalized article model for Elasticsearch"""
    id: str
    title: str
    description: Optional[str] = None
    content: Optional[str] = None
    url: str
    image_url: Optional[str] = None
    published_at: str  # Format: yyyy-MM-dd HH:mm:ss
    source: ArticleSource
    author: Optional[str] = None
    lang: str = "en"
    project_id: str
    job_id: str
    sentiment: List[SentimentResult] = []
    sentiment_label: Optional[str] = None
    emotion: List[EmotionResult] = []
    emotion_label: Optional[str] = None
    topic: List[TopicResult] = []
    topics_label: Optional[str] = None
    keywords: List[str] = []
    category: Optional[str] = None
    day: int  # Day of week (0-6)
    hour: int  # Hour of day (0-23)
    embedding: Optional[List[float]] = None  # 768-dimensional embedding from all-mpnet-base-v2


class HarvestResponse(BaseModel):
    """Response model for harvest operation"""
    success: bool
    job_id: str
    project_id: str
    articles_harvested: int
    articles_published: int
    message: str


class JobStatus(BaseModel):
    """Job status model"""
    job_id: str
    status: str
    progress: int
    total: int
    error: Optional[str] = None
