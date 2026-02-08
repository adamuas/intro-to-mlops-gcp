"""
NLP utilities using GLiNER2 service and Vertex AI embedding endpoint.

Labels are backward compatible with Cardiff NLP models:
- Sentiment: cardiffnlp/twitter-roberta-base-sentiment-latest
- Emotion: cardiffnlp/twitter-roberta-large-emotion-latest
- Topic: cardiffnlp/twitter-roberta-base-dec2021-tweet-topic-multi-all
- Embedding: sentence-transformers/all-mpnet-base-v2
"""
import os
import httpx
from typing import Dict, Any, List, Optional


# GLiNER endpoint
GLINER_ENDPOINT = os.environ.get(
    "GLINER_ENDPOINT",
    "https://gliner2-service-634181660442.us-central1.run.app"
)

# Vertex AI Embedding endpoint config
VERTEX_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
VERTEX_LOCATION = os.environ.get("VERTEX_LOCATION", "us-east1")
VERTEX_ENDPOINT_ID = os.environ.get("VERTEX_EMBEDDING_ENDPOINT_ID", "3219548167011827712")

# Cardiff NLP compatible labels
# Sentiment: cardiffnlp/twitter-roberta-base-sentiment-latest
SENTIMENT_LABELS = ["negative", "neutral", "positive"]

# Emotion: cardiffnlp/twitter-roberta-large-emotion-latest (11 classes)
EMOTION_LABELS = [
    "anger", "anticipation", "disgust", "fear", "joy",
    "love", "optimism", "pessimism", "sadness", "surprise", "trust"
]

# Topic: cardiffnlp/twitter-roberta-base-dec2021-tweet-topic-multi-all (19 classes)
TOPIC_LABELS = [
    "arts_&_culture", "business_&_entrepreneurs", "celebrity_&_pop_culture",
    "diaries_&_daily_life", "family", "fashion_&_style", "film_tv_&_video",
    "fitness_&_health", "food_&_dining", "gaming", "learning_&_educational",
    "music", "news_&_social_concern", "other_hobbies", "relationships",
    "science_&_technology", "sports", "travel_&_adventure", "youth_&_student_life"
]


def _call_gliner(text: str, labels: List[str], timeout: float = 10.0) -> List[Dict[str, Any]]:
    """
    Call the GLiNER extraction endpoint.

    Args:
        text: Text to analyze
        labels: Labels to extract/classify
        timeout: Request timeout

    Returns:
        List of extraction results
    """
    if not text or not text.strip():
        return []

    try:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                f"{GLINER_ENDPOINT}/extract",
                json={"text": text, "labels": labels}
            )
            response.raise_for_status()
            return response.json()
    except Exception as e:
        print(f"GLiNER error: {e}")
        return []


def analyze_sentiment(text: str) -> Dict[str, Any]:
    """
    Analyze sentiment using GLiNER2.
    Labels: negative, neutral, positive (Cardiff NLP compatible)

    Args:
        text: The text to analyze

    Returns:
        Dictionary with sentiment analysis results
    """
    results = _call_gliner(text, SENTIMENT_LABELS)

    if not results:
        return {
            "label": "neutral",
            "polarity": 0.0,
            "subjectivity": 0.5,
            "label_probability": 0.5,
            "model": "gliner2"
        }

    # Find highest scoring sentiment
    best = max(results, key=lambda x: x.get("score", 0))
    label = best.get("label", "neutral")
    score = best.get("score", 0.5)

    # Convert to polarity (-1 to 1)
    if label == "positive":
        polarity = score
    elif label == "negative":
        polarity = -score
    else:
        polarity = 0.0

    return {
        "label": label,
        "polarity": round(polarity, 4),
        "subjectivity": 0.5,
        "label_probability": round(score, 4),
        "model": "gliner2"
    }


def detect_emotion(text: str) -> Dict[str, Any]:
    """
    Detect primary emotion using GLiNER2.
    Labels: anger, anticipation, disgust, fear, joy, love, optimism,
            pessimism, sadness, surprise, trust (Cardiff NLP compatible)

    Args:
        text: The text to analyze

    Returns:
        Dictionary with emotion detection result
    """
    results = _call_gliner(text, EMOTION_LABELS)

    if not results:
        return {"label": "joy", "score": 0.5, "model": "gliner2"}

    # Return highest scoring emotion
    best = max(results, key=lambda x: x.get("score", 0))
    return {
        "label": best.get("label", "joy"),
        "score": round(best.get("score", 0.5), 4),
        "model": "gliner2"
    }


def classify_topic(text: str) -> Dict[str, Any]:
    """
    Classify topic using GLiNER2.
    Labels: 19 Cardiff NLP topic classes (arts_&_culture, business_&_entrepreneurs, etc.)

    Args:
        text: The text to analyze

    Returns:
        Dictionary with topic classification result
    """
    results = _call_gliner(text, TOPIC_LABELS)

    if not results:
        return {"label": "other_hobbies", "score": 0.5, "model": "gliner2"}

    # Return highest scoring topic
    best = max(results, key=lambda x: x.get("score", 0))
    return {
        "label": best.get("label", "other_hobbies"),
        "score": round(best.get("score", 0.5), 4),
        "model": "gliner2"
    }


def get_embedding(text: str) -> Optional[List[float]]:
    """
    Get text embedding using Vertex AI endpoint (all-mpnet-base-v2).

    Args:
        text: Text to embed

    Returns:
        List of floats (768-dimensional embedding) or None on error
    """
    if not text or not text.strip():
        return None

    if not VERTEX_PROJECT:
        print("Warning: GOOGLE_CLOUD_PROJECT not set, skipping embedding")
        return None

    try:
        from google.cloud import aiplatform
        from google.protobuf import json_format
        from google.protobuf.struct_pb2 import Value

        # Initialize Vertex AI
        aiplatform.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)

        # Get the endpoint
        endpoint = aiplatform.Endpoint(
            endpoint_name=f"projects/{VERTEX_PROJECT}/locations/{VERTEX_LOCATION}/endpoints/{VERTEX_ENDPOINT_ID}"
        )

        # Prepare instance for prediction
        instance = {"text": text}
        instances = [json_format.ParseDict(instance, Value())]

        # Get prediction
        response = endpoint.predict(instances=instances)

        # Extract embedding from response
        if response.predictions:
            embedding = response.predictions[0]
            if isinstance(embedding, list):
                return embedding
            elif hasattr(embedding, 'values'):
                return list(embedding.values())

        return None

    except ImportError:
        print("Warning: google-cloud-aiplatform not installed, skipping embedding")
        return None
    except Exception as e:
        print(f"Vertex AI embedding error: {e}")
        return None


def get_embedding_batch(texts: List[str], batch_size: int = 32) -> List[Optional[List[float]]]:
    """
    Get embeddings for a batch of texts.

    Args:
        texts: List of texts to embed
        batch_size: Number of texts per batch

    Returns:
        List of embeddings (or None for failed texts)
    """
    if not VERTEX_PROJECT:
        return [None] * len(texts)

    try:
        from google.cloud import aiplatform
        from google.protobuf import json_format
        from google.protobuf.struct_pb2 import Value

        aiplatform.init(project=VERTEX_PROJECT, location=VERTEX_LOCATION)
        endpoint = aiplatform.Endpoint(
            endpoint_name=f"projects/{VERTEX_PROJECT}/locations/{VERTEX_LOCATION}/endpoints/{VERTEX_ENDPOINT_ID}"
        )

        embeddings = []
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i + batch_size]
            instances = [json_format.ParseDict({"text": t}, Value()) for t in batch if t and t.strip()]

            if not instances:
                embeddings.extend([None] * len(batch))
                continue

            response = endpoint.predict(instances=instances)

            for pred in response.predictions:
                if isinstance(pred, list):
                    embeddings.append(pred)
                elif hasattr(pred, 'values'):
                    embeddings.append(list(pred.values()))
                else:
                    embeddings.append(None)

        return embeddings

    except ImportError:
        return [None] * len(texts)
    except Exception as e:
        print(f"Batch embedding error: {e}")
        return [None] * len(texts)


def analyze_tweet(text: str, include_embedding: bool = True) -> Dict[str, Any]:
    """
    Perform full NLP analysis on a tweet.

    Args:
        text: Tweet text
        include_embedding: Whether to include embedding

    Returns:
        Dictionary with sentiment, emotion, topic, and optionally embedding
    """
    result = {
        "sentiment": analyze_sentiment(text),
        "emotion": detect_emotion(text),
        "topic": classify_topic(text)
    }

    if include_embedding:
        embedding = get_embedding(text)
        if embedding:
            result["embedding"] = embedding

    return result


def batch_analyze_tweets(texts: List[str], include_embedding: bool = True) -> List[Dict[str, Any]]:
    """
    Analyze multiple tweets.

    Args:
        texts: List of tweet texts
        include_embedding: Whether to include embeddings

    Returns:
        List of analysis results
    """
    results = []
    embeddings = get_embedding_batch(texts) if include_embedding else [None] * len(texts)

    for text, embedding in zip(texts, embeddings):
        result = {
            "sentiment": analyze_sentiment(text),
            "emotion": detect_emotion(text),
            "topic": classify_topic(text)
        }
        if embedding:
            result["embedding"] = embedding
        results.append(result)

    return results
