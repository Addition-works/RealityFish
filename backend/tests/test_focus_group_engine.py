"""Tests for focus_group_engine.py — panel composition and data models."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.focus_group_engine import (
    FocusGroupEngine, FocusGroupPanel, FocusGroupMessage, FocusGroupResult,
)
from app.services.entity_extractor import ExtractedEntity


def _make_entity(username, platform="x", topic_aware=True):
    return ExtractedEntity(
        username=username,
        platform=platform,
        topic_aware=topic_aware,
        personality_summary=f"{username} is a test entity",
    )


def test_compose_panels_basic():
    engine = FocusGroupEngine.__new__(FocusGroupEngine)
    entities = [
        _make_entity("alice", topic_aware=True),
        _make_entity("bob", topic_aware=True),
        _make_entity("charlie", topic_aware=False),
        _make_entity("diana", topic_aware=False),
        _make_entity("eve", topic_aware=False),
    ]
    panels = engine.compose_panels(entities, panel_size=5, max_panels=1)
    assert len(panels) == 1
    assert len(panels[0]) == 5


def test_compose_panels_diversity():
    """Panels should include both topic-aware and audience-profile entities."""
    engine = FocusGroupEngine.__new__(FocusGroupEngine)
    entities = [
        _make_entity("a1", topic_aware=True),
        _make_entity("a2", topic_aware=True),
        _make_entity("a3", topic_aware=True),
        _make_entity("b1", topic_aware=False),
        _make_entity("b2", topic_aware=False),
        _make_entity("b3", topic_aware=False),
        _make_entity("b4", topic_aware=False),
    ]
    panels = engine.compose_panels(entities, panel_size=5, max_panels=1)
    panel = panels[0]
    topic_count = sum(1 for e in panel if e.topic_aware)
    audience_count = sum(1 for e in panel if not e.topic_aware)
    assert topic_count >= 1
    assert audience_count >= 1


def test_compose_panels_multiple():
    engine = FocusGroupEngine.__new__(FocusGroupEngine)
    entities = [_make_entity(f"user{i}", topic_aware=i % 2 == 0) for i in range(12)]
    panels = engine.compose_panels(entities, panel_size=4, max_panels=3)
    assert len(panels) == 3
    # No entity should appear in multiple panels
    all_keys = []
    for panel in panels:
        for e in panel:
            all_keys.append(e.entity_key)
    assert len(all_keys) == len(set(all_keys))


def test_compose_panels_too_few():
    engine = FocusGroupEngine.__new__(FocusGroupEngine)
    entities = [_make_entity("only_one")]
    panels = engine.compose_panels(entities, panel_size=5, max_panels=1)
    assert len(panels) == 0  # Need at least 2 participants


def test_compose_panels_empty():
    engine = FocusGroupEngine.__new__(FocusGroupEngine)
    panels = engine.compose_panels([], panel_size=5, max_panels=3)
    assert panels == []


def test_panel_transcript():
    panel = FocusGroupPanel(
        panel_id="test123",
        panel_name="Panel 1",
        participants=[_make_entity("alice"), _make_entity("bob")],
        messages=[
            FocusGroupMessage(role="moderator", content="What do you think?", round_num=0),
            FocusGroupMessage(role="alice", content="I think it's great.", round_num=0),
            FocusGroupMessage(role="bob", content="I'm not sure.", round_num=0),
        ],
    )
    transcript = panel.transcript_text
    assert "# Focus Group: Panel 1" in transcript
    assert "## Round 1" in transcript
    assert "**MODERATOR:**" in transcript
    assert "**@alice:**" in transcript
    assert "**@bob:**" in transcript


def test_focus_group_result():
    p1 = FocusGroupPanel(
        panel_id="a", panel_name="Panel 1",
        participants=[], messages=[
            FocusGroupMessage(role="moderator", content="Q1", round_num=0),
        ],
    )
    p2 = FocusGroupPanel(
        panel_id="b", panel_name="Panel 2",
        participants=[], messages=[
            FocusGroupMessage(role="moderator", content="Q2", round_num=0),
        ],
    )
    result = FocusGroupResult(panels=[p1, p2], mode="reality")
    full = result.full_transcript
    assert "Panel 1" in full
    assert "Panel 2" in full
    assert "---" in full


def test_participant_descriptions():
    engine = FocusGroupEngine.__new__(FocusGroupEngine)
    entities = [
        _make_entity("alice", topic_aware=True),
        _make_entity("bob", topic_aware=False),
    ]
    desc = engine._format_participant_descriptions(entities)
    assert "@alice" in desc
    assert "discusses the topic" in desc
    assert "@bob" in desc
    assert "has NOT discussed the topic" in desc


if __name__ == "__main__":
    test_compose_panels_basic()
    test_compose_panels_diversity()
    test_compose_panels_multiple()
    test_compose_panels_too_few()
    test_compose_panels_empty()
    test_panel_transcript()
    test_focus_group_result()
    test_participant_descriptions()
    print("All focus_group_engine tests passed!")
