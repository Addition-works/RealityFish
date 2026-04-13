"""Tests for reality_report_adapter.py — prompt switching logic."""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services import report_agent as report_agent_module
from app.services.reality_report_adapter import RealityReportAdapter, PROMPT_SETS
from app.services.reality_report_prompts import (
    REALITY_PLAN_SYSTEM_PROMPT,
    FUTURE_PLAN_SYSTEM_PROMPT,
)


def test_prompt_sets_exist():
    assert "reality" in PROMPT_SETS
    assert "future" in PROMPT_SETS
    assert "plan_system" in PROMPT_SETS["reality"]
    assert "plan_user" in PROMPT_SETS["reality"]
    assert "section_system" in PROMPT_SETS["reality"]


def test_reality_prompts_content():
    assert "Existing Reality" in REALITY_PLAN_SYSTEM_PROMPT
    assert "real social media data" in REALITY_PLAN_SYSTEM_PROMPT
    assert "NOT a simulation" in REALITY_PLAN_SYSTEM_PROMPT


def test_future_prompts_content():
    assert "Future Prediction" in FUTURE_PLAN_SYSTEM_PROMPT
    assert "realistic awareness" in FUTURE_PLAN_SYSTEM_PROMPT
    assert "WHO DIDN'T NOTICE" in FUTURE_PLAN_SYSTEM_PROMPT


def test_invalid_mode():
    try:
        RealityReportAdapter(
            graph_id="test",
            simulation_id="test",
            research_question="test",
            mode="invalid",
        )
        assert False, "Should have raised ValueError"
    except ValueError as e:
        assert "Unknown mode" in str(e)


def test_adapter_initialization():
    adapter = RealityReportAdapter(
        graph_id="reality_abc123",
        simulation_id="sim_xyz",
        research_question="How do people think about AI coding?",
        mode="reality",
    )
    assert adapter.mode == "reality"
    assert adapter.graph_id == "reality_abc123"
    assert adapter.research_question == "How do people think about AI coding?"


def test_prompts_are_distinct():
    """Reality and future prompts should be different."""
    for key in ("plan_system", "plan_user", "section_system"):
        assert PROMPT_SETS["reality"][key] != PROMPT_SETS["future"][key], \
            f"Prompt '{key}' should differ between reality and future modes"


if __name__ == "__main__":
    test_prompt_sets_exist()
    test_reality_prompts_content()
    test_future_prompts_content()
    test_invalid_mode()
    test_adapter_initialization()
    test_prompts_are_distinct()
    print("All reality_report_adapter tests passed!")
