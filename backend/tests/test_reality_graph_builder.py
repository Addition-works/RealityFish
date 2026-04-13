"""Tests for reality_graph_builder.py — entity formatting (no Zep calls)."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.reality_graph_builder import RealityGraphBuilder
from app.services.entity_extractor import ExtractedEntity
from app.services.social_scraper import ScrapedPost


def _make_entity(username, platform="x", topic_aware=True, **kwargs):
    return ExtractedEntity(
        username=username,
        platform=platform,
        display_name=kwargs.get("display_name", ""),
        topic_aware=topic_aware,
        relevance_reason=kwargs.get("relevance_reason", "Test entity"),
        sentiment_summary=kwargs.get("sentiment_summary", ""),
        personality_summary=kwargs.get("personality_summary", ""),
        communication_style=kwargs.get("communication_style", ""),
        core_topics=kwargs.get("core_topics", []),
        absent_topics=kwargs.get("absent_topics", []),
        engagement_pattern=kwargs.get("engagement_pattern", ""),
        openness_to_new=kwargs.get("openness_to_new", ""),
        posts=kwargs.get("posts", []),
    )


def test_format_entity_basic():
    builder = RealityGraphBuilder.__new__(RealityGraphBuilder)
    entity = _make_entity(
        "alice", platform="x", topic_aware=True,
        display_name="Alice Smith",
        relevance_reason="Discusses vibe coding frequently",
    )
    text = builder._format_entity_as_episode(entity)
    assert "@alice" in text
    assert "Platform: x" in text
    assert "Alice Smith" in text
    assert "actively discusses the research topic" in text
    assert "vibe coding" in text


def test_format_entity_audience_profile():
    builder = RealityGraphBuilder.__new__(RealityGraphBuilder)
    entity = _make_entity("bob", topic_aware=False)
    text = builder._format_entity_as_episode(entity)
    assert "has not discussed the research topic directly" in text


def test_format_entity_with_posts():
    builder = RealityGraphBuilder.__new__(RealityGraphBuilder)
    posts = [
        ScrapedPost(
            platform="x", post_id="1", author_username="alice",
            text="I just tried vibe coding and it's amazing!",
            likes=42, replies=5,
        ),
        ScrapedPost(
            platform="x", post_id="2", author_username="alice",
            text="Built my first app in 10 minutes",
            likes=15, replies=2,
        ),
    ]
    entity = _make_entity("alice", posts=posts)
    text = builder._format_entity_as_episode(entity)
    assert "Recent Activity (2 posts)" in text
    assert "vibe coding" in text
    assert "likes: 42" in text


def test_format_entity_with_enrichment():
    builder = RealityGraphBuilder.__new__(RealityGraphBuilder)
    entity = _make_entity(
        "charlie",
        personality_summary="Tech enthusiast who loves trying new tools.",
        communication_style="Casual and enthusiastic",
        core_topics=["AI", "coding", "startups"],
        absent_topics=["politics", "sports"],
        engagement_pattern="Active daily poster",
        openness_to_new="eager",
    )
    text = builder._format_entity_as_episode(entity)
    assert "Behavioral Profile:" in text
    assert "Tech enthusiast" in text
    assert "Casual and enthusiastic" in text
    assert "AI, coding, startups" in text
    assert "politics, sports" in text
    assert "Active daily poster" in text
    assert "eager" in text


def test_format_entity_minimal():
    """Even with minimal data, should produce valid text."""
    builder = RealityGraphBuilder.__new__(RealityGraphBuilder)
    entity = ExtractedEntity(username="minimal", platform="reddit")
    text = builder._format_entity_as_episode(entity)
    assert "@minimal" in text
    assert "reddit" in text
    assert len(text) > 20


if __name__ == "__main__":
    test_format_entity_basic()
    test_format_entity_audience_profile()
    test_format_entity_with_posts()
    test_format_entity_with_enrichment()
    test_format_entity_minimal()
    print("All reality_graph_builder tests passed!")
