"""
Data transformer for converting Apify tweet data to Cogito schema
"""
from datetime import datetime
from typing import Dict, Any, List, Optional
from uuid import uuid4
import re

from .nlp import analyze_sentiment, detect_emotion, classify_topic, get_embedding
from .models import (
    Tweet, Engagement, Mention, ReplyTo, SentimentResult, EmotionResult, TopicResult
)


def parse_apify_date(date_str: str) -> datetime:
    """
    Parse date string from Apify response.
    Handles multiple formats.
    """
    formats = [
        "%Y-%m-%dT%H:%M:%S.%fZ",
        "%Y-%m-%dT%H:%M:%SZ",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%a %b %d %H:%M:%S %z %Y",  # Twitter native format
    ]

    for fmt in formats:
        try:
            return datetime.strptime(date_str.replace("+0000", "+00:00"), fmt)
        except ValueError:
            continue

    # Fallback: try to extract datetime components
    try:
        # Remove timezone info and try again
        clean_date = re.sub(r'[+-]\d{2}:\d{2}$', '', date_str)
        clean_date = clean_date.replace('Z', '').replace('T', ' ')
        return datetime.fromisoformat(clean_date.split('.')[0])
    except Exception:
        return datetime.utcnow()


def format_date_for_es(dt: datetime) -> str:
    """Format datetime for Elasticsearch (yyyy-MM-dd HH:mm:ss)"""
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def extract_hashtags(tweet_data: Dict) -> List[str]:
    """Extract hashtags from tweet data"""
    hashtags = []

    # From entities
    if "entities" in tweet_data and "hashtags" in tweet_data["entities"]:
        for ht in tweet_data["entities"]["hashtags"]:
            if isinstance(ht, dict):
                hashtags.append(ht.get("tag", ht.get("text", "")))
            elif isinstance(ht, str):
                hashtags.append(ht)

    # From text using regex
    if "text" in tweet_data:
        found = re.findall(r'#(\w+)', tweet_data.get("text", ""))
        hashtags.extend(found)

    return list(set(hashtags))


def extract_mentions(tweet_data: Dict) -> List[Mention]:
    """Extract mentioned users from tweet data"""
    mentions = []

    # From entities
    if "entities" in tweet_data and "mentions" in tweet_data["entities"]:
        for m in tweet_data["entities"]["mentions"]:
            if isinstance(m, dict):
                mentions.append(Mention(
                    id=str(m.get("id", m.get("id_str", ""))),
                    screen_name=m.get("username", m.get("screen_name", "")),
                    name=m.get("name", m.get("displayname"))
                ))

    # From mentionedUsers (Apify format)
    if "mentionedUsers" in tweet_data:
        for m in tweet_data.get("mentionedUsers", []):
            if isinstance(m, dict):
                mentions.append(Mention(
                    id=str(m.get("id", "")),
                    screen_name=m.get("username", ""),
                    name=m.get("displayname")
                ))

    return mentions


def extract_urls(tweet_data: Dict) -> List[str]:
    """Extract URLs from tweet data"""
    urls = []

    # From entities
    if "entities" in tweet_data and "urls" in tweet_data["entities"]:
        for u in tweet_data["entities"]["urls"]:
            if isinstance(u, dict):
                urls.append(u.get("expanded_url", u.get("url", "")))
            elif isinstance(u, str):
                urls.append(u)

    # From outlinks (Apify format)
    if "outlinks" in tweet_data:
        urls.extend(tweet_data.get("outlinks", []))

    return list(set(filter(None, urls)))


def extract_photos(tweet_data: Dict) -> List[str]:
    """Extract photo URLs from tweet data"""
    photos = []

    # From media
    if "media" in tweet_data:
        for m in tweet_data.get("media", []):
            if isinstance(m, dict):
                if m.get("type") == "photo":
                    photos.append(m.get("url", m.get("media_url_https", "")))
            elif isinstance(m, str):
                photos.append(m)

    # From extendedEntities
    if "extendedEntities" in tweet_data and "media" in tweet_data["extendedEntities"]:
        for m in tweet_data["extendedEntities"]["media"]:
            if m.get("type") == "photo":
                photos.append(m.get("media_url_https", ""))

    return list(set(filter(None, photos)))


def transform_apify_tweet(
    tweet_data: Dict[str, Any],
    project_id: str,
    job_id: str
) -> Tweet:
    """
    Transform Apify tweet data to Cogito Tweet model.

    Args:
        tweet_data: Raw tweet data from Apify
        project_id: Project ID for routing
        job_id: Job ID for tracking

    Returns:
        Tweet model matching Elasticsearch schema
    """
    # Generate unique ID
    essid = str(uuid4())

    # Parse dates
    created_at_raw = tweet_data.get("createdAt", tweet_data.get("created_at", ""))
    created_at_dt = parse_apify_date(created_at_raw) if created_at_raw else datetime.utcnow()
    created_at = format_date_for_es(created_at_dt)

    # Extract user data
    user = tweet_data.get("author", tweet_data.get("user", {}))
    if isinstance(user, str):
        user = {"username": user}

    user_id = str(user.get("id", user.get("id_str", tweet_data.get("authorId", ""))))
    username = user.get("userName", user.get("username", user.get("screen_name", "")))
    display_name = user.get("name", user.get("displayname", username))
    verified = user.get("isVerified", user.get("verified", False))
    profile_image = user.get("profilePicture", user.get("profile_image_url", user.get("profileImageUrl")))

    # Get tweet text
    tweet_text = tweet_data.get("text", tweet_data.get("full_text", tweet_data.get("tweet", "")))

    # Build tweet link
    tweet_id = str(tweet_data.get("id", tweet_data.get("id_str", "")))
    link = tweet_data.get("url", f"https://twitter.com/{username}/status/{tweet_id}")

    # Extract engagement metrics
    engagement = Engagement(
        likes=int(tweet_data.get("likeCount", tweet_data.get("favorite_count", 0)) or 0),
        retweets=int(tweet_data.get("retweetCount", tweet_data.get("retweet_count", 0)) or 0),
        replies=int(tweet_data.get("replyCount", tweet_data.get("reply_count", 0)) or 0),
        quotes=int(tweet_data.get("quoteCount", tweet_data.get("quote_count", 0)) or 0),
        bookmarks=int(tweet_data.get("bookmarkCount", 0) or 0)
    )

    # Analyze sentiment, emotion, and topic using GLiNER
    sentiment_result = analyze_sentiment(tweet_text)
    sentiment = [SentimentResult(**sentiment_result)]

    emotion_result = detect_emotion(tweet_text)
    emotion = [EmotionResult(**emotion_result)]

    topic_result = classify_topic(tweet_text)
    topic = [TopicResult(**topic_result)]

    # Get embedding using Vertex AI
    embedding = get_embedding(tweet_text)

    # Check if retweet
    is_retweet = tweet_data.get("isRetweet", False) or tweet_text.startswith("RT @")
    retweeted_tweet = tweet_data.get("retweetedTweet", tweet_data.get("retweeted_status"))

    # Build reply info
    reply_to = None
    in_reply_to_user = tweet_data.get("inReplyToUser", tweet_data.get("in_reply_to_user"))
    if in_reply_to_user:
        if isinstance(in_reply_to_user, dict):
            reply_to = ReplyTo(
                user_id=str(in_reply_to_user.get("id", "")),
                username=in_reply_to_user.get("username", in_reply_to_user.get("screen_name", ""))
            )

    # Extract conversation ID
    conversation_id = tweet_data.get("conversationId", tweet_data.get("conversation_id"))

    return Tweet(
        id=tweet_id,
        conversation_id=str(conversation_id) if conversation_id else None,
        created_at=created_at,
        date=created_at,
        project_id=project_id,
        job_id=job_id,
        tweet=tweet_text,
        lang=tweet_data.get("lang", tweet_data.get("language")),
        hashtags=extract_hashtags(tweet_data),
        cashtags=tweet_data.get("cashtags", []),
        user_id_str=user_id,
        username=username,
        name=display_name,
        verified=verified,
        day=created_at_dt.weekday(),
        hour=created_at_dt.hour,
        link=link,
        retweet=is_retweet,
        essid=essid,
        engagement=engagement,
        sentiment=sentiment,
        sentiment_label=sentiment_result["label"],
        emotion=emotion,
        emotion_label=emotion_result["label"],
        topic=topic,
        topics_label=topic_result["label"],
        mentions=extract_mentions(tweet_data),
        urls=extract_urls(tweet_data),
        photos=extract_photos(tweet_data),
        thumbnail=profile_image,
        source=tweet_data.get("source", tweet_data.get("sourceLabel")),
        reply_to=reply_to,
        user_rt_id=str(retweeted_tweet.get("author", {}).get("id", "")) if retweeted_tweet and isinstance(retweeted_tweet, dict) else None,
        user_rt=retweeted_tweet.get("author", {}).get("username") if retweeted_tweet and isinstance(retweeted_tweet, dict) else None,
        retweet_id=str(retweeted_tweet.get("id", "")) if retweeted_tweet and isinstance(retweeted_tweet, dict) else None,
        retweet_date=format_date_for_es(parse_apify_date(retweeted_tweet.get("createdAt", ""))) if retweeted_tweet and isinstance(retweeted_tweet, dict) and retweeted_tweet.get("createdAt") else None,
        embedding=embedding
    )


def transform_batch(
    tweets: List[Dict[str, Any]],
    project_id: str,
    job_id: str
) -> List[Tweet]:
    """
    Transform a batch of Apify tweets to Cogito schema.

    Args:
        tweets: List of raw tweet data from Apify
        project_id: Project ID for routing
        job_id: Job ID for tracking

    Returns:
        List of Tweet models
    """
    transformed = []
    for tweet_data in tweets:
        try:
            transformed.append(transform_apify_tweet(tweet_data, project_id, job_id))
        except Exception as e:
            print(f"Error transforming tweet {tweet_data.get('id', 'unknown')}: {e}")
            continue
    return transformed
