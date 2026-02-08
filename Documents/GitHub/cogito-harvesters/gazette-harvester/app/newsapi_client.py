"""
NewsAPI client for fetching news articles
"""
import os
from typing import List, Dict, Any, Optional
from datetime import datetime
from newsapi import NewsApiClient


class NewsClient:
    """
    Client for fetching news articles using NewsAPI.
    """

    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize the News client.

        Args:
            api_key: NewsAPI key. If not provided, uses NEWS_API_KEY env var.
        """
        self.api_key = api_key or os.environ.get("NEWS_API_KEY")
        if not self.api_key:
            raise ValueError("NewsAPI key is required")

        self.client = NewsApiClient(api_key=self.api_key)

    def search_everything(
        self,
        keywords: List[str] = None,
        sources: List[str] = None,
        domains: List[str] = None,
        language: str = "en",
        sort_by: str = "publishedAt",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        page_size: int = 100,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Search all articles using the /everything endpoint.

        Args:
            keywords: List of keywords to search
            sources: List of source IDs
            domains: List of domains
            language: Language code
            sort_by: Sort order (relevancy, popularity, publishedAt)
            start_date: Filter articles after this date
            end_date: Filter articles before this date
            page_size: Number of articles per page (max 100)
            page: Page number

        Returns:
            API response with articles
        """
        # Build query from keywords
        q = " OR ".join(keywords) if keywords else None

        # Format dates
        from_param = start_date.strftime("%Y-%m-%d") if start_date else None
        to_param = end_date.strftime("%Y-%m-%d") if end_date else None

        # Format sources and domains
        sources_str = ",".join(sources) if sources else None
        domains_str = ",".join(domains) if domains else None

        response = self.client.get_everything(
            q=q,
            sources=sources_str,
            domains=domains_str,
            language=language,
            sort_by=sort_by,
            from_param=from_param,
            to_param=to_param,
            page_size=min(page_size, 100),
            page=page
        )

        return response

    def get_top_headlines(
        self,
        keywords: List[str] = None,
        sources: List[str] = None,
        category: str = None,
        country: str = None,
        language: str = "en",
        page_size: int = 100,
        page: int = 1
    ) -> Dict[str, Any]:
        """
        Get top headlines using the /top-headlines endpoint.

        Args:
            keywords: List of keywords to search
            sources: List of source IDs (cannot be used with country/category)
            category: Category filter (business, entertainment, etc.)
            country: Country code (us, gb, etc.)
            language: Language code
            page_size: Number of articles per page (max 100)
            page: Page number

        Returns:
            API response with articles
        """
        q = " OR ".join(keywords) if keywords else None
        sources_str = ",".join(sources) if sources else None

        # Note: sources cannot be combined with country or category
        if sources_str:
            response = self.client.get_top_headlines(
                q=q,
                sources=sources_str,
                language=language,
                page_size=min(page_size, 100),
                page=page
            )
        else:
            response = self.client.get_top_headlines(
                q=q,
                category=category,
                country=country,
                language=language,
                page_size=min(page_size, 100),
                page=page
            )

        return response

    def get_sources(
        self,
        category: str = None,
        language: str = "en",
        country: str = None
    ) -> Dict[str, Any]:
        """
        Get available news sources.

        Args:
            category: Category filter
            language: Language code
            country: Country code

        Returns:
            API response with sources
        """
        return self.client.get_sources(
            category=category,
            language=language,
            country=country
        )

    def fetch_all_articles(
        self,
        keywords: List[str] = None,
        sources: List[str] = None,
        domains: List[str] = None,
        language: str = "en",
        sort_by: str = "publishedAt",
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        max_articles: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch all articles across multiple pages.

        Args:
            keywords: Keywords to search
            sources: Source IDs
            domains: Domain names
            language: Language code
            sort_by: Sort order
            start_date: Start date filter
            end_date: End date filter
            max_articles: Maximum articles to fetch

        Returns:
            List of article dictionaries
        """
        all_articles = []
        page = 1
        page_size = min(100, max_articles)

        while len(all_articles) < max_articles:
            response = self.search_everything(
                keywords=keywords,
                sources=sources,
                domains=domains,
                language=language,
                sort_by=sort_by,
                start_date=start_date,
                end_date=end_date,
                page_size=page_size,
                page=page
            )

            if response.get("status") != "ok":
                print(f"NewsAPI error: {response.get('message', 'Unknown error')}")
                break

            articles = response.get("articles", [])
            if not articles:
                break

            all_articles.extend(articles)
            page += 1

            # Check if we've fetched all available articles
            total_results = response.get("totalResults", 0)
            if len(all_articles) >= total_results:
                break

        return all_articles[:max_articles]

    def fetch_top_headlines_all(
        self,
        keywords: List[str] = None,
        sources: List[str] = None,
        category: str = None,
        country: str = None,
        language: str = "en",
        max_articles: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Fetch all top headlines across multiple pages.

        Args:
            keywords: Keywords to search
            sources: Source IDs
            category: Category filter
            country: Country code
            language: Language code
            max_articles: Maximum articles to fetch

        Returns:
            List of article dictionaries
        """
        all_articles = []
        page = 1
        page_size = min(100, max_articles)

        while len(all_articles) < max_articles:
            response = self.get_top_headlines(
                keywords=keywords,
                sources=sources,
                category=category,
                country=country,
                language=language,
                page_size=page_size,
                page=page
            )

            if response.get("status") != "ok":
                print(f"NewsAPI error: {response.get('message', 'Unknown error')}")
                break

            articles = response.get("articles", [])
            if not articles:
                break

            all_articles.extend(articles)
            page += 1

            total_results = response.get("totalResults", 0)
            if len(all_articles) >= total_results:
                break

        return all_articles[:max_articles]
