"""
Google Cloud Pub/Sub publisher for Twitter data
"""
import os
import json
from typing import List, Dict, Any
from concurrent import futures
from google.cloud import pubsub_v1

# Default configuration
DEFAULT_PROJECT = os.environ.get("GOOGLE_CLOUD_PROJECT", "")
# Use socials-harvester-output for harvested data
DEFAULT_TOPIC = os.environ.get("PUBSUB_TOPIC", "socials-harvester-output")
BATCH_SIZE = 100  # Number of tweets per message


class TwitterPublisher:
    """
    Publisher for sending tweet data to Pub/Sub.
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

        # Configure batch settings for efficiency
        self.batch_settings = pubsub_v1.types.BatchSettings(
            max_messages=100,
            max_bytes=1024 * 1024,  # 1MB
            max_latency=1,  # 1 second
        )

    def _serialize_tweet(self, tweet: Any) -> Dict[str, Any]:
        """
        Serialize a tweet model to dictionary.
        """
        if hasattr(tweet, "model_dump"):
            return tweet.model_dump()
        elif hasattr(tweet, "dict"):
            return tweet.dict()
        elif isinstance(tweet, dict):
            return tweet
        else:
            raise ValueError(f"Cannot serialize tweet of type {type(tweet)}")

    def publish_tweets(
        self,
        tweets: List[Any],
        project_id: str,
        job_id: str
    ) -> int:
        """
        Publish tweets to Pub/Sub topic.

        Tweets are batched into messages for efficiency.

        Args:
            tweets: List of Tweet models or dictionaries
            project_id: Project ID for routing
            job_id: Job ID for tracking

        Returns:
            Number of messages published
        """
        if not tweets:
            return 0

        # Serialize tweets
        serialized = [self._serialize_tweet(t) for t in tweets]

        # Batch tweets into messages
        messages_published = 0
        publish_futures = []

        for i in range(0, len(serialized), BATCH_SIZE):
            batch = serialized[i:i + BATCH_SIZE]

            message_data = {
                "project_id": project_id,
                "job_id": job_id,
                "batch_index": i // BATCH_SIZE,
                "total_batches": (len(serialized) + BATCH_SIZE - 1) // BATCH_SIZE,
                "tweets": batch
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

    def publish_single(
        self,
        tweet: Any,
        project_id: str,
        job_id: str
    ) -> str:
        """
        Publish a single tweet to Pub/Sub.

        Args:
            tweet: Tweet model or dictionary
            project_id: Project ID for routing
            job_id: Job ID for tracking

        Returns:
            Message ID
        """
        serialized = self._serialize_tweet(tweet)

        message_data = {
            "project_id": project_id,
            "job_id": job_id,
            "tweets": [serialized]
        }

        data = json.dumps(message_data).encode("utf-8")
        future = self.publisher.publish(
            self.topic_path,
            data,
            project_id=project_id,
            job_id=job_id,
            content_type="application/json"
        )

        return future.result()


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
