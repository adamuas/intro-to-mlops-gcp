"""
Data transformer for converting NewsAPI articles to Cogito schema
"""
from datetime import datetime
from typing import Dict, Any, List
from uuid import uuid4
import hashlib
import re

from .nlp import analyze_sentiment, detect_emotion, classify_topic, get_embedding
from .models import Article, ArticleSource, SentimentResult, EmotionResult, TopicResult


def parse_newsapi_date(date_str: str) -> datetime:
    """
    Parse date string from NewsAPI response.
    """
    if not date_str:
        return datetime.utcnow()

    formats = [
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.replace("+00:00", "Z"), fmt)
        except ValueError:
            continue

    # Fallback
    try:
        clean_date = date_str.replace('Z', '').replace('T', ' ').split('.')[0]
        return datetime.fromisoformat(clean_date)
    except Exception:
        return datetime.utcnow()


def format_date_for_es(dt: datetime) -> str:
    """Format datetime for Elasticsearch (yyyy-MM-dd HH:mm:ss)"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def generate_article_id(url: str, title: str) -> str:
    """
    Generate a unique article ID based on URL and title.
    """
    content = f"{url}:{title}"
    return hashlib.md5(content.encode()).hexdigest()


def extract_keywords_from_text(text: str, max_keywords: int = 10) -> List[str]:
    """
    Extract keywords from text using simple word frequency.
    """
    if not text:
        return []

    # Remove common words and punctuation
    stopwords = {
        'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'is', 'are', 'was', 'were', 'be', 'been',
        'being', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'this',
        'that', 'these', 'those', 'it', 'its', 'as', 'if', 'when', 'where',
        'who', 'what', 'which', 'how', 'why', 'all', 'each', 'every', 'both',
        'few', 'more', 'most', 'other', 'some', 'such', 'no', 'nor', 'not',
        'only', 'own', 'same', 'so', 'than', 'too', 'very', 'just', 'also',
        'now', 'here', 'there', 'about', 'after', 'before', 'above', 'below',
        'between', 'into', 'through', 'during', 'under', 'again', 'further',
        'then', 'once', 'up', 'down', 'out', 'off', 'over', 'any', 'our',
        'your', 'his', 'her', 'their', 'my', 'we', 'you', 'he', 'she', 'they',
        'me', 'him', 'us', 'them', 'i', 'said', 'says', 'according', 'new',
        'first', 'last', 'one', 'two', 'three', 'four', 'five', 'year', 'years',
    }

    # Extract words
    words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())

    # Filter and count
    word_counts = {}
    for word in words:
        if word not in stopwords:
            word_counts[word] = word_counts.get(word, 0) + 1

    # Sort by frequency and return top keywords
    sorted_words = sorted(word_counts.items(), key=lambda x: x[1], reverse=True)
    return [word for word, count in sorted_words[:max_keywords]]


def transform_newsapi_article(
    article_data: Dict[str, Any],
    project_id: str,
    job_id: str,
    category: str = None
) -> Article:
    """
    Transform NewsAPI article data to Cogito Article model.

    Args:
        article_data: Raw article data from NewsAPI
        project_id: Project ID for routing
        job_id: Job ID for tracking
        category: Optional category to assign

    Returns:
        Article model matching Elasticsearch schema
    """
    # Parse dates
    published_at_raw = article_data.get("publishedAt", "")
    published_at_dt = parse_newsapi_date(published_at_raw)
    published_at = format_date_for_es(published_at_dt)

    # Extract source
    source_data = article_data.get("source", {})
    source = ArticleSource(
        id=source_data.get("id"),
        name=source_data.get("name", "Unknown")
    )

    # Get content
    title = article_data.get("title", "")
    description = article_data.get("description")
    content = article_data.get("content")

    # Clean content (NewsAPI truncates content with "[+X chars]")
    if content and "[+" in content:
        content = content.split("[+")[0].strip()

    # Combine text for NLP analysis
    combined_for_nlp = f"{title} {description or ''}"

    # Analyze sentiment, emotion, and topic using GLiNER
    sentiment_result = analyze_sentiment(combined_for_nlp)
    sentiment = [SentimentResult(**sentiment_result)]

    emotion_result = detect_emotion(combined_for_nlp)
    emotion = [EmotionResult(**emotion_result)]

    topic_result = classify_topic(combined_for_nlp)
    topic = [TopicResult(**topic_result)]

    # Get embedding using Vertex AI
    embedding = get_embedding(combined_for_nlp)

    # Extract keywords
    combined_text = f"{title} {description or ''} {content or ''}"
    keywords = extract_keywords_from_text(combined_text)

    # Generate article ID
    url = article_data.get("url", "")
    article_id = generate_article_id(url, title)

    return Article(
        id=article_id,
        title=title,
        description=description,
        content=content,
        url=url,
        image_url=article_data.get("urlToImage"),
        published_at=published_at,
        source=source,
        author=article_data.get("author"),
        lang="en",  # NewsAPI doesn't return language per article
        project_id=project_id,
        job_id=job_id,
        sentiment=sentiment,
        sentiment_label=sentiment_result["label"],
        emotion=emotion,
        emotion_label=emotion_result["label"],
        topic=topic,
        topics_label=topic_result["label"],
        keywords=keywords,
        category=category,
        day=published_at_dt.weekday(),
        hour=published_at_dt.hour,
        embedding=embedding
    )


def transform_batch(
    articles: List[Dict[str, Any]],
    project_id: str,
    job_id: str,
    category: str = None
) -> List[Article]:
    """
    Transform a batch of NewsAPI articles to Cogito schema.

    Args:
        articles: List of raw article data from NewsAPI
        project_id: Project ID for routing
        job_id: Job ID for tracking
        category: Optional category to assign

    Returns:
        List of Article models
    """
    transformed = []
    seen_ids = set()

    for article_data in articles:
        try:
            article = transform_newsapi_article(article_data, project_id, job_id, category)

            # Deduplicate by ID
            if article.id not in seen_ids:
                transformed.append(article)
                seen_ids.add(article.id)
        except Exception as e:
            print(f"Error transforming article: {e}")
            continue

    return transformed
