"""Tests for social_scraper.py — unit tests for data models and normalization."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.social_scraper import (
    ScrapedPost, ScrapedUser, ScrapeResult,
    XScraper, RedditScraper,
)


def test_scraped_post_defaults():
    post = ScrapedPost(platform="x", post_id="123", author_username="alice")
    assert post.platform == "x"
    assert post.post_id == "123"
    assert post.text == ""
    assert post.likes == 0
    assert post.raw_data == {}


def test_scraped_user_defaults():
    user = ScrapedUser(platform="reddit", username="bob")
    assert user.bio == ""
    assert user.followers == 0
    assert user.recent_posts == []


def test_scrape_result_defaults():
    result = ScrapeResult(platform="x", query="test", query_type="keyword")
    assert result.posts == []
    assert result.error == ""


def test_x_scraper_unavailable():
    scraper = XScraper(api_token="")
    assert not scraper.available
    result = scraper.search_keyword("test")
    assert result.error == "Apify API token not configured"
    assert result.posts == []


def test_x_scraper_username_unavailable():
    scraper = XScraper(api_token="")
    result = scraper.search_username("someuser")
    assert result.query_type == "username"
    assert result.query == "someuser"
    assert "not configured" in result.error


def test_reddit_scraper_unavailable():
    scraper = RedditScraper(client_id="", client_secret="")
    assert not scraper.available
    result = scraper.search_keyword("test")
    assert "not configured" in result.error


def test_reddit_scraper_username_unavailable():
    scraper = RedditScraper(client_id="", client_secret="")
    result = scraper.search_username("someuser")
    assert result.query_type == "username"
    assert "not configured" in result.error


def test_x_normalize_tweet():
    scraper = XScraper(api_token="fake")
    item = {
        "id": "abc123",
        "text": "Hello world",
        "url": "https://x.com/alice/status/abc123",
        "createdAt": "2026-04-10T12:00:00Z",
        "likeCount": 42,
        "retweetCount": 5,
        "replyCount": 3,
        "viewCount": 1000,
        "author": {
            "userName": "alice",
            "name": "Alice Smith",
        },
    }
    post = scraper._normalize_tweet(item, "test query")
    assert post.platform == "x"
    assert post.post_id == "abc123"
    assert post.author_username == "alice"
    assert post.author_display_name == "Alice Smith"
    assert post.text == "Hello world"
    assert post.likes == 42
    assert post.reposts == 5
    assert post.replies == 3
    assert post.views == 1000
    assert post.search_query == "test query"


def test_x_normalize_tweet_null_counts():
    """Apify sometimes returns None for counts."""
    scraper = XScraper(api_token="fake")
    item = {
        "id": "xyz",
        "text": "test",
        "likeCount": None,
        "retweetCount": None,
        "replyCount": None,
        "viewCount": None,
        "author": {"userName": "bob"},
    }
    post = scraper._normalize_tweet(item, "q")
    assert post.likes == 0
    assert post.reposts == 0
    assert post.replies == 0
    assert post.views == 0


def test_x_normalize_tweet_string_author():
    """Handle case where author is a string instead of dict."""
    scraper = XScraper(api_token="fake")
    item = {"id": "1", "text": "hi", "author": "charlie"}
    post = scraper._normalize_tweet(item, "q")
    assert post.author_username == "charlie"
    assert post.author_display_name == ""


if __name__ == "__main__":
    test_scraped_post_defaults()
    test_scraped_user_defaults()
    test_scrape_result_defaults()
    test_x_scraper_unavailable()
    test_x_scraper_username_unavailable()
    test_reddit_scraper_unavailable()
    test_reddit_scraper_username_unavailable()
    test_x_normalize_tweet()
    test_x_normalize_tweet_null_counts()
    test_x_normalize_tweet_string_author()
    print("All social_scraper tests passed!")
