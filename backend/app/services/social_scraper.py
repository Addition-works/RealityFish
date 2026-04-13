"""
Social media scraping service for X (Twitter) and Reddit.

Ported from insights-deep-research/venmo_agent/apify_social_service.py
and reddit_analysis_service.py. Stripped to keyword search + username scraping only.
"""

import os
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger("realityfish.scraper")


@dataclass
class ScrapedPost:
    """Normalized post from any platform."""
    platform: str
    post_id: str
    author_username: str
    author_display_name: str = ""
    text: str = ""
    url: str = ""
    created_at: str = ""
    likes: int = 0
    reposts: int = 0
    replies: int = 0
    views: int = 0
    search_query: str = ""
    raw_data: dict = field(default_factory=dict)


@dataclass
class ScrapedUser:
    """User profile data from deep scraping."""
    platform: str
    username: str
    display_name: str = ""
    bio: str = ""
    followers: int = 0
    following: int = 0
    verified: bool = False
    recent_posts: list[ScrapedPost] = field(default_factory=list)
    raw_data: dict = field(default_factory=dict)


@dataclass
class ScrapeResult:
    """Result of a scraping operation."""
    platform: str
    query: str
    query_type: str  # "keyword" or "username"
    posts: list[ScrapedPost] = field(default_factory=list)
    users: list[ScrapedUser] = field(default_factory=list)
    error: str = ""


class XScraper:
    """X (Twitter) scraping via Apify."""

    SEARCH_ACTOR_ID = "CJdippxWmn9uRfooo"

    def __init__(self, api_token: str = ""):
        self.api_token = api_token or os.environ.get("APIFY_API_TOKEN", "")
        self._client = None

    @property
    def client(self):
        if self._client is None and self.api_token:
            from apify_client import ApifyClient
            self._client = ApifyClient(self.api_token)
        return self._client

    @property
    def available(self) -> bool:
        return bool(self.api_token)

    def search_keyword(
        self,
        query: str,
        max_results: int = 20,
        recency_days: int = 7,
        lang: str = "en",
    ) -> ScrapeResult:
        """Search X for tweets matching a keyword query."""
        result = ScrapeResult(platform="x", query=query, query_type="keyword")

        if not self.available:
            result.error = "Apify API token not configured"
            return result

        try:
            since_date = (datetime.now() - timedelta(days=recency_days)).strftime("%Y-%m-%d")
            enhanced_query = f"{query} since:{since_date}"

            run = self.client.actor(self.SEARCH_ACTOR_ID).call(
                run_input={
                    "filter:blue_verified": False,
                    "filter:consumer_video": False,
                    "filter:has_engagement": False,
                    "filter:hashtags": False,
                    "filter:images": False,
                    "filter:links": False,
                    "filter:media": False,
                    "filter:mentions": False,
                    "filter:native_video": False,
                    "filter:nativeretweets": False,
                    "filter:news": False,
                    "filter:pro_video": False,
                    "filter:quote": False,
                    "filter:replies": False,
                    "filter:safe": False,
                    "filter:spaces": False,
                    "filter:twimg": False,
                    "filter:videos": False,
                    "filter:vine": False,
                    "include:nativeretweets": False,
                    "lang": lang,
                    "searchTerms": [enhanced_query],
                    "maxItems": max_results,
                    "queryType": "Top",
                    "min_retweets": 0,
                    "min_faves": 0,
                    "min_replies": 0,
                },
                timeout_secs=180,
            )

            items = list(self.client.dataset(run["defaultDatasetId"]).iterate_items())
            result.posts = [self._normalize_tweet(item, query) for item in items]
            logger.info(f"X keyword search '{query}': {len(result.posts)} tweets")

        except Exception as e:
            result.error = f"X search failed: {e}"
            logger.error(result.error)

        return result

    def search_username(
        self,
        username: str,
        max_results: int = 20,
        recency_days: int = 30,
    ) -> ScrapeResult:
        """Fetch recent tweets from a specific user using from:username syntax."""
        from_query = f"from:{username}"
        result = self.search_keyword(from_query, max_results, recency_days)
        result.query = username
        result.query_type = "username"
        return result

    def _normalize_tweet(self, item: dict, query: str) -> ScrapedPost:
        author = item.get("author", {})
        if isinstance(author, dict):
            username = author.get("userName", "")
            display_name = author.get("name", "")
        else:
            username = str(author)
            display_name = ""

        post = ScrapedPost(
            platform="x",
            post_id=str(item.get("id", "")),
            author_username=username,
            author_display_name=display_name,
            text=item.get("text", ""),
            url=item.get("url", ""),
            created_at=item.get("createdAt", ""),
            likes=item.get("likeCount", 0) or 0,
            reposts=item.get("retweetCount", 0) or 0,
            replies=item.get("replyCount", 0) or 0,
            views=item.get("viewCount", 0) or 0,
            search_query=query,
            raw_data=item,
        )
        return post

    @staticmethod
    def extract_user_profile(raw_data: dict) -> dict:
        """Extract user profile metadata from a tweet's raw_data."""
        author = raw_data.get("author", {})
        if not isinstance(author, dict) or not author:
            return {}
        bio = author.get("description", "")
        if not bio:
            profile_bio = author.get("profile_bio", {})
            if isinstance(profile_bio, dict):
                bio = profile_bio.get("description", "")
        return {
            "bio": bio,
            "followers": author.get("followers", 0) or 0,
            "following": author.get("following", 0) or 0,
            "verified": bool(author.get("isVerified") or author.get("isBlueVerified")),
            "location": author.get("location", ""),
            "profile_picture": author.get("profilePicture", ""),
        }


class RedditScraper:
    """Reddit scraping via PRAW."""

    def __init__(
        self,
        client_id: str = "",
        client_secret: str = "",
        user_agent: str = "realityfish-bot/1.0",
    ):
        self.client_id = client_id or os.environ.get("REDDIT_CLIENT_ID", "")
        self.client_secret = client_secret or os.environ.get("REDDIT_CLIENT_SECRET", "")
        self.user_agent = user_agent or os.environ.get("REDDIT_USER_AGENT", "realityfish-bot/1.0")
        self._client = None

    @property
    def client(self):
        if self._client is None and self.available:
            import praw
            self._client = praw.Reddit(
                client_id=self.client_id,
                client_secret=self.client_secret,
                user_agent=self.user_agent,
            )
        return self._client

    @property
    def available(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def search_keyword(
        self,
        query: str,
        subreddits: Optional[list[str]] = None,
        max_posts_per_sub: int = 5,
        time_filter: str = "week",
        max_comments: int = 20,
    ) -> ScrapeResult:
        """Search Reddit for posts matching a keyword."""
        result = ScrapeResult(platform="reddit", query=query, query_type="keyword")

        if not self.available:
            result.error = "Reddit API credentials not configured"
            return result

        target_subs = subreddits or ["all"]

        try:
            for sub_name in target_subs:
                try:
                    subreddit = self.client.subreddit(sub_name)
                    for submission in subreddit.search(query, limit=max_posts_per_sub, time_filter=time_filter):
                        submission.comments.replace_more(limit=0)
                        comments = submission.comments.list()[:max_comments]

                        comment_texts = [
                            {
                                "author": str(c.author) if c.author else "[deleted]",
                                "body": c.body[:500],
                                "score": c.score,
                            }
                            for c in comments
                            if hasattr(c, "body")
                        ]

                        post = ScrapedPost(
                            platform="reddit",
                            post_id=submission.id,
                            author_username=str(submission.author) if submission.author else "[deleted]",
                            text=f"{submission.title}\n\n{submission.selftext}" if submission.selftext else submission.title,
                            url=f"https://reddit.com{submission.permalink}",
                            created_at=datetime.fromtimestamp(submission.created_utc).isoformat(),
                            likes=submission.score,
                            replies=submission.num_comments,
                            search_query=query,
                            raw_data={
                                "subreddit": sub_name,
                                "title": submission.title,
                                "selftext": submission.selftext,
                                "comments": comment_texts,
                            },
                        )
                        result.posts.append(post)

                except Exception as e:
                    logger.warning(f"Error searching r/{sub_name}: {e}")
                    continue

            logger.info(f"Reddit keyword search '{query}': {len(result.posts)} posts")

        except Exception as e:
            result.error = f"Reddit search failed: {e}"
            logger.error(result.error)

        return result

    def search_username(
        self,
        username: str,
        max_submissions: int = 20,
        max_comments: int = 20,
    ) -> ScrapeResult:
        """Fetch a Reddit user's recent posts and comments."""
        result = ScrapeResult(platform="reddit", query=username, query_type="username")

        if not self.available:
            result.error = "Reddit API credentials not configured"
            return result

        try:
            redditor = self.client.redditor(username)

            for submission in redditor.submissions.new(limit=max_submissions):
                post = ScrapedPost(
                    platform="reddit",
                    post_id=submission.id,
                    author_username=username,
                    text=f"{submission.title}\n\n{submission.selftext}" if submission.selftext else submission.title,
                    url=f"https://reddit.com{submission.permalink}",
                    created_at=datetime.fromtimestamp(submission.created_utc).isoformat(),
                    likes=submission.score,
                    replies=submission.num_comments,
                    search_query=f"user:{username}",
                    raw_data={
                        "subreddit": str(submission.subreddit),
                        "title": submission.title,
                        "selftext": submission.selftext,
                    },
                )
                result.posts.append(post)

            user_data = ScrapedUser(
                platform="reddit",
                username=username,
                recent_posts=result.posts,
            )
            try:
                user_data.bio = getattr(redditor, "subreddit", {}).get("public_description", "") if hasattr(redditor, "subreddit") else ""
                user_data.followers = getattr(redditor, "subreddit", {}).get("subscribers", 0) if hasattr(redditor, "subreddit") else 0
                user_data.verified = getattr(redditor, "is_gold", False) or getattr(redditor, "has_verified_email", False)
            except Exception:
                pass

            result.users = [user_data]
            logger.info(f"Reddit user scrape '{username}': {len(result.posts)} posts")

        except Exception as e:
            result.error = f"Reddit user scrape failed: {e}"
            logger.error(result.error)

        return result


class SocialScraper:
    """Unified interface for scraping X and Reddit."""

    def __init__(self):
        from app.config import Config
        self.x = XScraper(api_token=Config.APIFY_API_TOKEN)
        self.reddit = RedditScraper(
            client_id=Config.REDDIT_CLIENT_ID,
            client_secret=Config.REDDIT_CLIENT_SECRET,
            user_agent=Config.REDDIT_USER_AGENT,
        )

    def search_keyword(
        self,
        query: str,
        platforms: list[str] = None,
        **kwargs,
    ) -> list[ScrapeResult]:
        """Search for a keyword across specified platforms."""
        platforms = platforms or ["x", "reddit"]
        results = []

        if "x" in platforms:
            results.append(self.x.search_keyword(query, **{
                k: v for k, v in kwargs.items()
                if k in ("max_results", "recency_days", "lang")
            }))

        if "reddit" in platforms:
            results.append(self.reddit.search_keyword(query, **{
                k: v for k, v in kwargs.items()
                if k in ("subreddits", "max_posts_per_sub", "time_filter", "max_comments")
            }))

        return results

    def search_username(
        self,
        username: str,
        platform: str,
        **kwargs,
    ) -> ScrapeResult:
        """Deep-scrape a specific user's profile and history."""
        if platform == "x":
            return self.x.search_username(username, **{
                k: v for k, v in kwargs.items()
                if k in ("max_results", "recency_days")
            })
        elif platform == "reddit":
            return self.reddit.search_username(username, **{
                k: v for k, v in kwargs.items()
                if k in ("max_submissions", "max_comments")
            })
        else:
            return ScrapeResult(
                platform=platform,
                query=username,
                query_type="username",
                error=f"Unsupported platform: {platform}",
            )

    @property
    def status(self) -> dict:
        return {
            "x": {"available": self.x.available},
            "reddit": {"available": self.reddit.available},
        }
