"""
Pydantic models for Twitter Harvester
"""
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import datetime
from enum import Enum


class SearchType(str, Enum):
    KEYWORD = "keyword"
    HASHTAG = "hashtag"
    USERNAME = "username"
    URL = "url"


class HarvestRequest(BaseModel):
    """Request model for harvesting tweets"""
    project_id: str = Field(..., description="Project ID for data routing")
    search_terms: List[str] = Field(..., description="List of search terms/usernames/hashtags")
    search_type: SearchType = Field(default=SearchType.KEYWORD, description="Type of search")
    max_tweets: int = Field(default=100, ge=1, le=10000, description="Maximum tweets to harvest")
    start_date: Optional[datetime] = Field(default=None, description="Start date filter")
    end_date: Optional[datetime] = Field(default=None, description="End date filter")
    include_replies: bool = Field(default=False, description="Include reply tweets")
    language: Optional[str] = Field(default=None, description="Filter by language code")


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


class Engagement(BaseModel):
    """Tweet engagement metrics"""
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    bookmarks: int = 0


class Mention(BaseModel):
    """Mentioned user"""
    id: str
    screen_name: str
    name: Optional[str] = None


class ReplyTo(BaseModel):
    """Reply target"""
    user_id: str
    username: str


class Tweet(BaseModel):
    """Normalized tweet model matching Elasticsearch schema"""
    id: str
    conversation_id: Optional[str] = None
    created_at: str  # Format: yyyy-MM-dd HH:mm:ss
    date: str  # Format: yyyy-MM-dd HH:mm:ss
    project_id: str
    job_id: str
    tweet: str  # Tweet content
    lang: Optional[str] = None
    hashtags: List[str] = []
    cashtags: List[str] = []
    user_id_str: str
    username: str
    name: Optional[str] = None
    verified: bool = False
    day: int  # Day of week (0-6)
    hour: int  # Hour of day (0-23)
    link: str
    retweet: bool = False
    essid: str
    engagement: Engagement
    sentiment: List[SentimentResult] = []
    sentiment_label: Optional[str] = None
    emotion: List[EmotionResult] = []
    emotion_label: Optional[str] = None
    topic: List[TopicResult] = []
    topics_label: Optional[str] = None
    mentions: List[Mention] = []
    urls: List[str] = []
    photos: List[str] = []
    thumbnail: Optional[str] = None
    source: Optional[str] = None
    reply_to: Optional[ReplyTo] = None
    user_rt_id: Optional[str] = None
    user_rt: Optional[str] = None
    retweet_id: Optional[str] = None
    retweet_date: Optional[str] = None
    embedding: Optional[List[float]] = None  # 768-dimensional embedding from all-mpnet-base-v2


class HarvestResponse(BaseModel):
    """Response model for harvest operation"""
    success: bool
    job_id: str
    project_id: str
    tweets_harvested: int
    tweets_published: int
    message: str


class JobStatus(BaseModel):
    """Job status model"""
    job_id: str
    status: str
    progress: int
    total: int
    error: Optional[str] = None
