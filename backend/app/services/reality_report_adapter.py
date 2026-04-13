"""
Reality Report Adapter.

Wraps the existing ReportAgent to support two modes:
- "reality" — Existing Reality report (Phase 1)
- "future" — Future Prediction report (Phase 2)

The adapter swaps the prompt constants used by ReportAgent before
generating a report, then restores them afterward.
"""

import logging
from typing import Optional, Callable

from ..utils.llm_client import LLMClient
from . import report_agent as report_agent_module
from .report_agent import ReportAgent
from .zep_tools import ZepToolsService
from .reality_report_prompts import (
    REALITY_PLAN_SYSTEM_PROMPT,
    REALITY_PLAN_USER_PROMPT_TEMPLATE,
    REALITY_SECTION_SYSTEM_PROMPT_TEMPLATE,
    FUTURE_PLAN_SYSTEM_PROMPT,
    FUTURE_PLAN_USER_PROMPT_TEMPLATE,
    FUTURE_SECTION_SYSTEM_PROMPT_TEMPLATE,
)

logger = logging.getLogger("realityfish.reality_report")

# Map mode to prompt sets
PROMPT_SETS = {
    "reality": {
        "plan_system": REALITY_PLAN_SYSTEM_PROMPT,
        "plan_user": REALITY_PLAN_USER_PROMPT_TEMPLATE,
        "section_system": REALITY_SECTION_SYSTEM_PROMPT_TEMPLATE,
    },
    "future": {
        "plan_system": FUTURE_PLAN_SYSTEM_PROMPT,
        "plan_user": FUTURE_PLAN_USER_PROMPT_TEMPLATE,
        "section_system": FUTURE_SECTION_SYSTEM_PROMPT_TEMPLATE,
    },
}


class RealityReportAdapter:
    """
    Generates reports using the existing ReportAgent with mode-specific prompts.

    Usage:
        adapter = RealityReportAdapter(
            graph_id="reality_abc123",
            simulation_id="sim_xyz",
            research_question="How do people think about AI coding tools?",
            mode="reality",
        )
        report_id = adapter.generate_report(progress_callback=my_callback)
    """

    def __init__(
        self,
        graph_id: str,
        simulation_id: str,
        research_question: str,
        mode: str = "reality",
        llm_client: Optional[LLMClient] = None,
        zep_tools: Optional[ZepToolsService] = None,
    ):
        if mode not in PROMPT_SETS:
            raise ValueError(f"Unknown mode '{mode}'. Must be 'reality' or 'future'.")

        self.graph_id = graph_id
        self.simulation_id = simulation_id
        self.research_question = research_question
        self.mode = mode
        self.llm = llm_client
        self.zep_tools = zep_tools

    def generate_report(
        self,
        progress_callback: Optional[Callable] = None,
    ) -> str:
        """
        Generate a report using the existing ReportAgent with mode-specific prompts.

        Returns:
            report_id — the ID of the generated report directory
        """
        prompts = PROMPT_SETS[self.mode]

        original_plan_system = report_agent_module.PLAN_SYSTEM_PROMPT
        original_plan_user = report_agent_module.PLAN_USER_PROMPT_TEMPLATE
        original_section_system = report_agent_module.SECTION_SYSTEM_PROMPT_TEMPLATE

        try:
            report_agent_module.PLAN_SYSTEM_PROMPT = prompts["plan_system"]
            report_agent_module.PLAN_USER_PROMPT_TEMPLATE = prompts["plan_user"]
            report_agent_module.SECTION_SYSTEM_PROMPT_TEMPLATE = prompts["section_system"]

            agent = ReportAgent(
                graph_id=self.graph_id,
                simulation_id=self.simulation_id,
                simulation_requirement=self.research_question,
                llm_client=self.llm,
                zep_tools=self.zep_tools,
            )

            report = agent.generate_report(progress_callback=progress_callback)

            report_id = report.report_id if hasattr(report, 'report_id') else str(report)
            logger.info(f"Generated {self.mode} report: {report_id}")
            return report_id

        finally:
            report_agent_module.PLAN_SYSTEM_PROMPT = original_plan_system
            report_agent_module.PLAN_USER_PROMPT_TEMPLATE = original_plan_user
            report_agent_module.SECTION_SYSTEM_PROMPT_TEMPLATE = original_section_system
