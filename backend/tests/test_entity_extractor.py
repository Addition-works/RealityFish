"""Tests for entity_extractor.py — unit tests for data models and fallback logic."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.entity_extractor import ExtractedEntity, EntityExtractor
from app.services.social_scraper import ScrapedPost, ScrapeResult


def _make_post(platform, post_id, username, text="hello", display_name=""):
    return ScrapedPost(
        platform=platform,
        post_id=post_id,
        author_username=username,
        author_display_name=display_name,
        text=text,
    )


def test_entity_key():
    entity = ExtractedEntity(username="Alice", platform="x")
    assert entity.entity_key == "x:alice"


def test_entity_to_dict():
    entity = ExtractedEntity(
        username="bob",
        platform="reddit",
        topic_aware=True,
        core_topics=["AI", "coding"],
    )
    d = entity.to_dict()
    assert d["username"] == "bob"
    assert d["platform"] == "reddit"
    assert d["topic_aware"] is True
    assert d["core_topics"] == ["AI", "coding"]
    assert d["post_count"] == 0


def test_fallback_extraction():
    """Fallback extraction creates one entity per unique author."""
    posts = [
        _make_post("x", "1", "alice", "I love vibe coding"),
        _make_post("x", "2", "alice", "AI Studio is great"),
        _make_post("x", "3", "bob", "What is vibe coding?"),
        _make_post("reddit", "4", "charlie", "Just built an app"),
        _make_post("reddit", "5", "[deleted]", "This was deleted"),
    ]

    extractor = EntityExtractor.__new__(EntityExtractor)
    entities = extractor._fallback_extraction(posts)

    assert len(entities) == 3  # alice, bob, charlie (not [deleted])

    by_key = {e.entity_key: e for e in entities}
    assert "x:alice" in by_key
    assert len(by_key["x:alice"].posts) == 2
    assert len(by_key["x:alice"].post_ids) == 2
    assert "x:bob" in by_key
    assert "reddit:charlie" in by_key
    assert "reddit:[deleted]" not in by_key


def test_fallback_extraction_empty():
    extractor = EntityExtractor.__new__(EntityExtractor)
    entities = extractor._fallback_extraction([])
    assert entities == []


def test_extract_entities_no_posts():
    """Extract from empty results returns empty list."""
    extractor = EntityExtractor.__new__(EntityExtractor)
    extractor.llm = None  # Won't be called
    result = ScrapeResult(platform="x", query="test", query_type="keyword", error="failed")
    entities = extractor.extract_entities([result])
    assert entities == []


def test_format_posts_for_llm():
    extractor = EntityExtractor.__new__(EntityExtractor)
    posts = [
        _make_post("x", "1", "alice", "Hello world", "Alice S"),
        _make_post("reddit", "2", "bob", "Testing 123"),
    ]
    text = extractor._format_posts_for_llm(posts)
    assert "[ID: 1]" in text
    assert "@alice" in text
    assert "Alice S" in text
    assert "[ID: 2]" in text
    assert "@bob" in text


def test_dedup_across_batches():
    """Entities with the same key across batches get merged."""
    extractor = EntityExtractor.__new__(EntityExtractor)

    e1 = ExtractedEntity(
        username="alice", platform="x",
        topic_aware=False,
        post_ids=["1"], posts=[_make_post("x", "1", "alice")],
    )
    e2 = ExtractedEntity(
        username="alice", platform="x",
        topic_aware=True,
        post_ids=["2"], posts=[_make_post("x", "2", "alice")],
    )

    # Simulate the merge logic from extract_entities
    all_entities = {}
    for entity in [e1, e2]:
        key = entity.entity_key
        if key in all_entities:
            existing = all_entities[key]
            existing.post_ids.extend(entity.post_ids)
            existing.posts.extend(entity.posts)
            if entity.topic_aware:
                existing.topic_aware = True
        else:
            all_entities[key] = entity

    merged = all_entities["x:alice"]
    assert len(merged.post_ids) == 2
    assert len(merged.posts) == 2
    assert merged.topic_aware is True  # promoted to True


if __name__ == "__main__":
    test_entity_key()
    test_entity_to_dict()
    test_fallback_extraction()
    test_fallback_extraction_empty()
    test_extract_entities_no_posts()
    test_format_posts_for_llm()
    test_dedup_across_batches()
    print("All entity_extractor tests passed!")
