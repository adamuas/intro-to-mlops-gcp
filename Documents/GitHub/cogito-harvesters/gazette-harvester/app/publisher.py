"""
Google Cloud Pub/Sub publisher for News data
"""
import os
import json
from typing import List, Any
from concurrent import futures
from google.cloud import pubsub_v1

# Default configuration
DEFAULT_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
# Use socials-harvester-output for harvested data
DEFAULT_TOPIC = os.environ.get("PUBSUB_TOPIC", "socials-harvester-output")
BATCH_SIZE = 50  # Number of articles per message


class NewsPublisher:
    """
    Publisher for sending news article data to Pub/Sub.
    """

    def __init__(
        self,
        project_id: str = None,
        topic_id: str = None
    ):
        """
        Initialize the publisher.

        Args:
            project_id: GCP project ID
            topic_id: Pub/Sub topic ID
        """
        self.project_id = project_id or DEFAULT_PROJECT
        self.topic_id = topic_id or DEFAULT_TOPIC

        if not self.project_id:
            raise ValueError("GCP project ID is required")

        self.publisher = pubsub_v1.PublisherClient()
        self.topic_path = self.publisher.topic_path(self.project_id, self.topic_id)

    def _serialize_article(self, article: Any) -> dict:
        """
        Serialize an article model to dictionary.
        """
        if hasattr(article, "model_dump"):
            return article.model_dump()
        elif hasattr(article, "dict"):
            return article.dict()
        elif isinstance(article, dict):
            return article
        else:
            raise ValueError(f"Cannot serialize article of type {type(article)}")

    def publish_articles(
        self,
        articles: List[Any],
        project_id: str,
        job_id: str
    ) -> int:
        """
        Publish articles to Pub/Sub topic.

        Articles are batched into messages for efficiency.

        Args:
            articles: List of Article models or dictionaries
            project_id: Project ID for routing
            job_id: Job ID for tracking

        Returns:
            Number of messages published
        """
        if not articles:
            return 0

        # Serialize articles
        serialized = [self._serialize_article(a) for a in articles]

        # Batch articles into messages
        messages_published = 0
        publish_futures = []

        for i in range(0, len(serialized), BATCH_SIZE):
            batch = serialized[i:i + BATCH_SIZE]

            message_data = {
                "project_id": project_id,
                "job_id": job_id,
                "batch_index": i // BATCH_SIZE,
                "total_batches": (len(serialized) + BATCH_SIZE - 1) // BATCH_SIZE,
                "articles": batch
            }

            # Publish message
            data = json.dumps(message_data).encode("utf-8")
            future = self.publisher.publish(
                self.topic_path,
                data,
                project_id=project_id,
                job_id=job_id,
                content_type="application/json"
            )
            publish_futures.append(future)
            messages_published += 1

        # Wait for all publishes to complete
        for future in futures.as_completed(set(publish_futures), timeout=60):
            try:
                future.result()
            except Exception as e:
                print(f"Error publishing message: {e}")

        return messages_published


def create_topic_if_not_exists(project_id: str, topic_id: str) -> str:
    """
    Create Pub/Sub topic if it doesn't exist.

    Args:
        project_id: GCP project ID
        topic_id: Topic ID to create

    Returns:
        Topic path
    """
    publisher = pubsub_v1.PublisherClient()
    topic_path = publisher.topic_path(project_id, topic_id)

    try:
        publisher.get_topic(request={"topic": topic_path})
        print(f"Topic {topic_path} already exists")
    except Exception:
        topic = publisher.create_topic(request={"name": topic_path})
        print(f"Created topic: {topic.name}")

    return topic_path
