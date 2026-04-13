"""Tests for awareness_engine.py — probability calculations."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.awareness_engine import AwarenessEngine, AwarenessProfile
from app.services.entity_extractor import ExtractedEntity
from app.services.social_scraper import ScrapedPost


def _make_entity(username, topic_aware=True, openness="neutral", engagement_pattern="", num_posts=0):
    posts = [ScrapedPost(platform="x", post_id=str(i), author_username=username) for i in range(num_posts)]
    return ExtractedEntity(
        username=username,
        platform="x",
        topic_aware=topic_aware,
        openness_to_new=openness,
        engagement_pattern=engagement_pattern,
        posts=posts,
    )


def test_topic_aware_higher_than_audience():
    engine = AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5)
    aware = engine.calculate_awareness(_make_entity("alice", topic_aware=True))
    audience = engine.calculate_awareness(_make_entity("bob", topic_aware=False))
    assert aware.awareness_probability > audience.awareness_probability
    assert aware.caring_probability > audience.caring_probability


def test_eager_higher_than_resistant():
    engine = AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5)
    eager = engine.calculate_awareness(_make_entity("alice", topic_aware=False, openness="eager"))
    resistant = engine.calculate_awareness(_make_entity("bob", topic_aware=False, openness="resistant"))
    assert eager.awareness_probability > resistant.awareness_probability


def test_high_engagement_boosts():
    engine = AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5)
    active = engine.calculate_awareness(_make_entity("alice", topic_aware=False, engagement_pattern="very active poster"))
    lurker = engine.calculate_awareness(_make_entity("bob", topic_aware=False, engagement_pattern="rarely posts, lurks"))
    assert active.awareness_probability > lurker.awareness_probability


def test_probabilities_clamped():
    engine = AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5)
    # Max case: topic_aware + eager + high engagement
    max_entity = _make_entity("max", topic_aware=True, openness="eager", engagement_pattern="frequent active")
    profile = engine.calculate_awareness(max_entity)
    assert profile.awareness_probability <= 0.95
    assert profile.caring_probability <= 0.95

    # Min case: not topic_aware + resistant + lurker
    min_entity = _make_entity("min", topic_aware=False, openness="resistant", engagement_pattern="lurks passively")
    profile = engine.calculate_awareness(min_entity)
    assert profile.awareness_probability >= 0.05
    assert profile.caring_probability >= 0.10


def test_engagement_probability_combined():
    profile = AwarenessProfile(
        entity_key="x:alice", username="alice", platform="x",
        awareness_probability=0.5, caring_probability=0.6,
        topic_aware=True,
    )
    assert abs(profile.engagement_probability - 0.3) < 0.001


def test_roll_mechanics():
    """Test that roll functions work (stochastic, so just check they return bools)."""
    import random
    random.seed(42)

    profile = AwarenessProfile(
        entity_key="x:alice", username="alice", platform="x",
        awareness_probability=0.5, caring_probability=0.5,
        topic_aware=True,
    )

    noticed, cared = profile.roll_engages()
    assert isinstance(noticed, bool)
    assert isinstance(cared, bool)
    if not noticed:
        assert cared is False


def test_roll_high_probability():
    """Very high probability should almost always trigger."""
    import random
    random.seed(42)

    profile = AwarenessProfile(
        entity_key="x:test", username="test", platform="x",
        awareness_probability=0.99, caring_probability=0.99,
        topic_aware=True,
    )
    # Run 100 times, expect most to engage
    engaged_count = sum(1 for _ in range(100) if all(profile.roll_engages()))
    assert engaged_count > 90


def test_roll_low_probability():
    """Very low probability should almost never trigger."""
    import random
    random.seed(42)

    profile = AwarenessProfile(
        entity_key="x:test", username="test", platform="x",
        awareness_probability=0.05, caring_probability=0.10,
        topic_aware=False,
    )
    engaged_count = sum(1 for _ in range(100) if all(profile.roll_engages()))
    assert engaged_count < 5


def test_batch_calculation():
    engine = AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5)
    entities = [
        _make_entity("alice", topic_aware=True),
        _make_entity("bob", topic_aware=False),
        _make_entity("charlie", topic_aware=True, openness="eager"),
    ]
    profiles = engine.calculate_batch(entities)
    assert len(profiles) == 3
    # All should have valid probabilities
    for p in profiles:
        assert 0.05 <= p.awareness_probability <= 0.95
        assert 0.10 <= p.caring_probability <= 0.95


def test_classify_engagement_by_posts():
    engine = AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5)
    heavy = _make_entity("heavy", num_posts=10)
    light = _make_entity("light", num_posts=1)
    assert engine._classify_engagement(heavy) == "high"
    assert engine._classify_engagement(light) == "low"


def test_factors_tracked():
    engine = AwarenessEngine(base_probability=0.15, topic_aware_boost=0.5)
    profile = engine.calculate_awareness(_make_entity("alice", topic_aware=True, openness="curious"))
    assert "base" in profile.factors
    assert "topic_aware" in profile.factors
    assert "openness" in profile.factors
    assert "engagement" in profile.factors
    assert profile.factors["topic_aware"] == 0.5


if __name__ == "__main__":
    test_topic_aware_higher_than_audience()
    test_eager_higher_than_resistant()
    test_high_engagement_boosts()
    test_probabilities_clamped()
    test_engagement_probability_combined()
    test_roll_mechanics()
    test_roll_high_probability()
    test_roll_low_probability()
    test_batch_calculation()
    test_classify_engagement_by_posts()
    test_factors_tracked()
    print("All awareness_engine tests passed!")
