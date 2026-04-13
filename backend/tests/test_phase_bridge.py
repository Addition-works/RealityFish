"""Tests for phase_bridge.py — entity-to-OASIS conversion and awareness config."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.phase_bridge import PhaseBridge
from app.services.entity_extractor import ExtractedEntity
from app.services.social_scraper import ScrapedPost
from app.services.awareness_engine import AwarenessEngine


def _make_entity(username, topic_aware=True, openness="neutral", posts=None, **kwargs):
    return ExtractedEntity(
        username=username,
        platform="x",
        display_name=kwargs.get("display_name", f"{username} Display"),
        topic_aware=topic_aware,
        relevance_reason=kwargs.get("relevance_reason", "Test entity"),
        sentiment_summary=kwargs.get("sentiment_summary", "Positive about AI"),
        personality_summary=kwargs.get("personality_summary", "Tech enthusiast"),
        communication_style=kwargs.get("communication_style", "Casual"),
        core_topics=kwargs.get("core_topics", ["AI", "coding"]),
        absent_topics=kwargs.get("absent_topics", ["sports"]),
        engagement_pattern=kwargs.get("engagement_pattern", "Active poster"),
        openness_to_new=openness,
        posts=posts or [],
    )


def test_convert_basic():
    bridge = PhaseBridge(AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5))
    entities = [
        _make_entity("alice", topic_aware=True),
        _make_entity("bob", topic_aware=False),
    ]
    oasis_profiles, awareness_profiles = bridge.convert_entities_to_profiles(entities)

    assert len(oasis_profiles) == 2
    assert len(awareness_profiles) == 2

    assert oasis_profiles[0].user_name == "alice"
    assert oasis_profiles[0].user_id == 0
    assert oasis_profiles[1].user_name == "bob"
    assert oasis_profiles[1].user_id == 1


def test_persona_includes_real_data():
    bridge = PhaseBridge(AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5))
    entity = _make_entity(
        "alice", topic_aware=True,
        personality_summary="Loves AI tools",
        sentiment_summary="Very excited about vibe coding",
    )
    profiles, _ = bridge.convert_entities_to_profiles([entity])
    persona = profiles[0].persona
    assert "Loves AI tools" in persona
    assert "Very excited about vibe coding" in persona
    assert "already aware" in persona


def test_persona_audience_profile():
    bridge = PhaseBridge(AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5))
    entity = _make_entity("bob", topic_aware=False)
    profiles, _ = bridge.convert_entities_to_profiles([entity])
    assert "not currently aware" in profiles[0].persona


def test_awareness_probabilities_aligned():
    bridge = PhaseBridge(AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5))
    entities = [
        _make_entity("alice", topic_aware=True, openness="eager"),
        _make_entity("bob", topic_aware=False, openness="resistant"),
    ]
    _, awareness = bridge.convert_entities_to_profiles(entities)

    assert awareness[0].awareness_probability > awareness[1].awareness_probability
    assert awareness[0].caring_probability > awareness[1].caring_probability


def test_awareness_config_generation():
    bridge = PhaseBridge(AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5))
    entities = [
        _make_entity("alice", topic_aware=True),
        _make_entity("bob", topic_aware=False),
    ]
    _, awareness = bridge.convert_entities_to_profiles(entities)
    config = bridge.generate_awareness_config(awareness)

    assert "0" in config
    assert "1" in config
    assert config["0"]["topic_aware"] is True
    assert config["1"]["topic_aware"] is False
    assert "awareness_probability" in config["0"]
    assert "caring_probability" in config["0"]


def test_mbti_from_openness():
    bridge = PhaseBridge(AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5))

    eager_entity = _make_entity("alice", openness="eager")
    skeptical_entity = _make_entity("bob", openness="skeptical")

    profiles, _ = bridge.convert_entities_to_profiles([eager_entity, skeptical_entity])
    assert profiles[0].mbti in ["ENFP", "ENTP", "ENTJ", "ENFJ"]
    assert profiles[1].mbti in ["INTJ", "ISTJ", "ISTP", "INTP"]


def test_oasis_format_output():
    bridge = PhaseBridge(AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5))
    entity = _make_entity("alice", display_name="Alice Smith", core_topics=["AI", "coding"])
    profiles, _ = bridge.convert_entities_to_profiles([entity])

    twitter_fmt = profiles[0].to_twitter_format()
    assert twitter_fmt["username"] == "alice"
    assert twitter_fmt["name"] == "Alice Smith"
    assert "bio" in twitter_fmt
    assert "persona" in twitter_fmt

    reddit_fmt = profiles[0].to_reddit_format()
    assert reddit_fmt["username"] == "alice"
    assert "karma" in reddit_fmt


def test_posts_in_persona():
    posts = [
        ScrapedPost(platform="x", post_id="1", author_username="alice", text="AI is changing everything"),
    ]
    bridge = PhaseBridge(AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5))
    entity = _make_entity("alice", posts=posts)
    profiles, _ = bridge.convert_entities_to_profiles([entity])
    assert "AI is changing everything" in profiles[0].persona


if __name__ == "__main__":
    test_convert_basic()
    test_persona_includes_real_data()
    test_persona_audience_profile()
    test_awareness_probabilities_aligned()
    test_awareness_config_generation()
    test_mbti_from_openness()
    test_oasis_format_output()
    test_posts_in_persona()
    print("All phase_bridge tests passed!")
