"""
Apify client for Twitter scraping using apidojo/tweet-scraper
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from apify_client import ApifyClient

# Apify actor ID for Tweet Scraper V2
TWEET_SCRAPER_ACTOR = "apidojo/tweet-scraper"

# Valid ISO 639-1 language codes for Apify Twitter scraper
VALID_LANGUAGE_CODES = {
    "ab", "aa", "af", "ak", "sq", "am", "ar", "an", "hy", "as", "av", "ae", "ay", "az",
    "bm", "ba", "eu", "be", "bn", "bi", "bs", "br", "bg", "my", "ca", "ch", "ce", "ny",
    "zh", "cu", "cv", "kw", "co", "cr", "hr", "cs", "da", "dv", "nl", "dz", "en", "eo",
    "et", "ee", "fo", "fj", "fi", "fr", "fy", "ff", "gd", "gl", "lg", "ka", "de", "el",
    "kl", "gn", "gu", "ht", "ha", "he", "hz", "hi", "ho", "hu", "is", "io", "ig", "id",
    "ia", "ie", "iu", "ik", "ga", "it", "ja", "jv", "kn", "kr", "ks", "kk", "km", "ki",
    "rw", "ky", "kv", "kg", "ko", "kj", "ku", "lo", "la", "lv", "li", "ln", "lt", "lu",
    "lb", "mk", "mg", "ms", "ml", "mt", "gv", "mi", "mr", "mh", "mn", "na", "nv", "nd",
    "nr", "ng", "ne", "no", "nb", "nn", "ii", "oc", "oj", "or", "om", "os", "pi", "ps",
    "fa", "pl", "pt", "pa", "qu", "ro", "rm", "rn", "ru", "se", "sm", "sg", "sa", "sc",
    "sr", "sn", "sd", "si", "sk", "sl", "so", "st", "es", "su", "sw", "ss", "sv", "tl",
    "ty", "tg", "ta", "tt", "te", "th", "bo", "ti", "to", "ts", "tn", "tr", "tk", "tw",
    "ug", "uk", "ur", "uz", "ve", "vi", "vo", "wa", "cy", "wo", "xh", "yi", "yo", "za", "zu"
}


def normalize_language_code(language: Optional[str]) -> Optional[str]:
    """
    Normalize language code to valid ISO 639-1 format.

    Args:
        language: Language code (e.g., 'en', 'en-US', 'english')

    Returns:
        Valid ISO 639-1 code or None if invalid
    """
    if not language:
        return None

    # Take first 2 characters and lowercase
    lang_code = language[:2].lower()

    # Validate against known codes
    if lang_code in VALID_LANGUAGE_CODES:
        return lang_code

    return None


class TwitterScraper:
    """
    Client for scraping Twitter using Apify's Tweet Scraper V2.
    """

    def __init__(self, api_token: Optional[str] = None):
        """
        Initialize the Twitter scraper.

        Args:
            api_token: Apify API token. If not provided, uses APIFY_API_TOKEN env var.
        """
        self.api_token = api_token or os.environ.get("APIFY_API_TOKEN")
        if not self.api_token:
            raise ValueError("Apify API token is required")

        self.client = ApifyClient(self.api_token)

    def search_tweets(
        self,
        search_terms: List[str],
        max_tweets: int = 30,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        include_replies: bool = False,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Search for tweets by keyword.

        Args:
            search_terms: List of search terms
            max_tweets: Maximum number of tweets to return
            start_date: Filter tweets after this date
            end_date: Filter tweets before this date
            include_replies: Whether to include reply tweets
            language: Filter by language code

        Returns:
            List of tweet data dictionaries
        """
        # Normalize language code
        valid_language = normalize_language_code(language)

        # Build search queries
        search_queries = []
        for term in search_terms:
            query = term
            if valid_language:
                query += f" lang:{valid_language}"
            if not include_replies:
                query += " -filter:replies"
            search_queries.append(query)

        # Prepare actor input
        actor_input = {
            "searchTerms": search_queries,
            "maxTweets": max_tweets,
            "sort": "Latest",
        }

        # Only add tweetLanguage if valid
        if valid_language:
            actor_input["tweetLanguage"] = valid_language

        # Add date filters if provided
        if start_date:
            actor_input["startDate"] = start_date.strftime("%Y-%m-%d")
        if end_date:
            actor_input["endDate"] = end_date.strftime("%Y-%m-%d")

        # Run the actor
        run = self.client.actor(TWEET_SCRAPER_ACTOR).call(run_input=actor_input)

        # Get results from dataset
        tweets = []
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            tweets.append(item)

        return tweets

    def scrape_user_tweets(
        self,
        usernames: List[str],
        max_tweets: int = 30,
        include_replies: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Scrape tweets from specific users.

        Args:
            usernames: List of Twitter usernames (without @)
            max_tweets: Maximum tweets per user
            include_replies: Whether to include replies

        Returns:
            List of tweet data dictionaries
        """
        # Build profile URLs
        profile_urls = [f"https://twitter.com/{username}" for username in usernames]

        actor_input = {
            "profilesDesired": profile_urls,
            "maxTweets": max_tweets,
            "includeReplies": include_replies,
        }

        # Run the actor
        run = self.client.actor(TWEET_SCRAPER_ACTOR).call(run_input=actor_input)

        # Get results
        tweets = []
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            tweets.append(item)

        return tweets

    def scrape_hashtag(
        self,
        hashtags: List[str],
        max_tweets: int = 30,
        language: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Scrape tweets by hashtag.

        Args:
            hashtags: List of hashtags (with or without #)
            max_tweets: Maximum tweets to return
            language: Filter by language

        Returns:
            List of tweet data dictionaries
        """
        # Normalize hashtags
        normalized = [f"#{ht.lstrip('#')}" for ht in hashtags]

        return self.search_tweets(
            search_terms=normalized,
            max_tweets=max_tweets,
            language=language
        )

    def scrape_urls(
        self,
        tweet_urls: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Scrape specific tweets by URL.

        Args:
            tweet_urls: List of tweet URLs

        Returns:
            List of tweet data dictionaries
        """
        actor_input = {
            "startUrls": [{"url": url} for url in tweet_urls],
        }

        # Run the actor
        run = self.client.actor(TWEET_SCRAPER_ACTOR).call(run_input=actor_input)

        # Get results
        tweets = []
        for item in self.client.dataset(run["defaultDatasetId"]).iterate_items():
            tweets.append(item)

        return tweets

    def get_run_status(self, run_id: str) -> Dict[str, Any]:
        """
        Get the status of an actor run.

        Args:
            run_id: The run ID

        Returns:
            Run status information
        """
        run = self.client.run(run_id).get()
        return {
            "id": run["id"],
            "status": run["status"],
            "started_at": run.get("startedAt"),
            "finished_at": run.get("finishedAt"),
            "stats": run.get("stats", {})
        }
