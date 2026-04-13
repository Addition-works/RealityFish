"""Tests for world_builder.py — unit tests for search strategy and pipeline logic."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.world_builder import SearchStrategy, WorldBuildProgress


def test_search_strategy_all_queries():
    strategy = SearchStrategy(
        topic_aware_queries=["vibe coding", "AI tools"],
        audience_profile_queries=[
            {"audience": "Entrepreneurs", "queries": ["small business tips", "etsy shop"]},
            {"audience": "Students", "queries": ["college projects"]},
        ],
    )
    all_q = strategy.all_queries
    assert len(all_q) == 5
    assert all_q[0] == ("vibe coding", "topic_aware")
    assert all_q[1] == ("AI tools", "topic_aware")
    assert all_q[2] == ("small business tips", "audience:Entrepreneurs")
    assert all_q[3] == ("etsy shop", "audience:Entrepreneurs")
    assert all_q[4] == ("college projects", "audience:Students")


def test_search_strategy_empty():
    strategy = SearchStrategy()
    assert strategy.all_queries == []


def test_progress_idle():
    p = WorldBuildProgress()
    assert p.progress_pct == 0
    assert p.phase == "idle"


def test_progress_scraping():
    p = WorldBuildProgress(phase="scraping", total_queries=10, completed_queries=5)
    assert p.progress_pct == 15  # 30 * 5/10


def test_progress_extracting():
    p = WorldBuildProgress(phase="extracting")
    assert p.progress_pct == 30


def test_progress_enriching():
    p = WorldBuildProgress(phase="enriching", total_entities=10, enriched_entities=5)
    assert p.progress_pct == 60  # 30 + 60 * 5/10


def test_progress_complete():
    p = WorldBuildProgress(phase="complete")
    assert p.progress_pct == 100


if __name__ == "__main__":
    test_search_strategy_all_queries()
    test_search_strategy_empty()
    test_progress_idle()
    test_progress_scraping()
    test_progress_extracting()
    test_progress_enriching()
    test_progress_complete()
    print("All world_builder tests passed!")
