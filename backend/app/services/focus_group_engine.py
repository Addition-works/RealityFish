"""
Focus Group Engine.

Automatically composes small panels from the entity pool, runs moderated
multi-turn LLM conversations, and produces transcripts. Transcripts are stored
in Zep alongside the entity graph so the ReportAgent can access them.

Supports two modes:
- Phase 1 (Existing Reality): panelists discuss current behaviors/attitudes
- Phase 2 (Future Simulation): panelists react to simulated scenarios
"""

import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Optional

from .entity_extractor import ExtractedEntity

logger = logging.getLogger("realityfish.focus_group")

MODERATOR_SYSTEM_PROMPT_REALITY = """You are a skilled focus group moderator researching how real people currently think and behave regarding a topic.

You are moderating a panel of {panel_size} participants. Each participant is a real person whose social media activity you have access to.

Your job:
1. Ask probing, open-ended questions that reveal genuine attitudes and behaviors
2. Follow up on interesting responses — dig deeper, ask "why"
3. Encourage quieter participants to share
4. Surface disagreements and tensions between participants
5. Avoid leading questions — let participants reveal their own perspectives

You will conduct {num_rounds} rounds of discussion. Each round, you ask ONE question to the group.

Research context: {research_question}

Participants:
{participant_descriptions}

Start with a warm-up question, then progressively go deeper. Final round should probe for unmet needs or frustrations."""

MODERATOR_SYSTEM_PROMPT_FUTURE = """You are a skilled focus group moderator exploring how real people would react to a future scenario.

You are moderating a panel of {panel_size} participants. Each participant is a real person whose social media activity and current attitudes you have access to.

The scenario being discussed:
{scenario_description}

Your job:
1. Present the scenario and gauge initial reactions
2. Probe for genuine responses — would they actually notice this? Care about it?
3. Explore barriers to adoption or engagement
4. Surface unexpected reactions and edge cases
5. Specifically ask participants who seem indifferent WHY they don't care

You will conduct {num_rounds} rounds of discussion. Each round, you ask ONE question to the group.

Research context: {research_question}

Participants:
{participant_descriptions}

Start by presenting the scenario, then probe reactions. Final rounds should explore "what would it take to change your mind?"."""

PANELIST_SYSTEM_PROMPT = """You are {display_name} (@{username} on {platform}). You are participating in a focus group discussion.

Your personality and communication style:
{personality_summary}

Topics you care about: {core_topics}
Topics you typically don't discuss: {absent_topics}
Your engagement style: {engagement_pattern}
Your openness to new things: {openness_to_new}

Your recent social media activity shows:
{recent_post_summary}

IMPORTANT:
- Stay in character. Respond as this person would actually respond.
- Be authentic — if you wouldn't care about something, say so.
- Use your natural communication style (formal/casual, verbose/brief, etc.)
- Don't pretend to know things you wouldn't know based on your profile.
- It's OK to disagree, be indifferent, or say "I don't really think about that."
- Keep responses concise (2-4 sentences for most answers)."""


@dataclass
class FocusGroupMessage:
    role: str  # "moderator" or participant username
    content: str
    round_num: int


@dataclass
class FocusGroupPanel:
    panel_id: str
    panel_name: str
    participants: list[ExtractedEntity]
    messages: list[FocusGroupMessage] = field(default_factory=list)
    mode: str = "reality"  # "reality" or "future"

    @property
    def transcript_text(self) -> str:
        lines = [f"# Focus Group: {self.panel_name}\n"]
        lines.append(f"Mode: {self.mode}")
        lines.append(f"Participants: {', '.join(f'@{p.username}' for p in self.participants)}\n")
        current_round = -1
        for msg in self.messages:
            if msg.round_num != current_round:
                current_round = msg.round_num
                lines.append(f"\n## Round {current_round + 1}\n")
            speaker = "MODERATOR" if msg.role == "moderator" else f"@{msg.role}"
            lines.append(f"**{speaker}:** {msg.content}\n")
        return "\n".join(lines)


@dataclass
class FocusGroupResult:
    panels: list[FocusGroupPanel]
    mode: str

    @property
    def full_transcript(self) -> str:
        return "\n\n---\n\n".join(p.transcript_text for p in self.panels)


class FocusGroupEngine:
    """Runs focus group sessions with LLM-simulated panelists."""

    def __init__(self, llm_client=None):
        if llm_client is None:
            from ..utils.llm_client import LLMClient
            llm_client = LLMClient()
        self.llm = llm_client

    def compose_panels(
        self,
        entities: list[ExtractedEntity],
        panel_size: int = 5,
        max_panels: int = 3,
    ) -> list[list[ExtractedEntity]]:
        """
        Automatically compose diverse panels from the entity pool.
        Each panel has a mix of topic-aware and audience-profile entities.
        """
        if not entities:
            return []

        topic_aware = [e for e in entities if e.topic_aware]
        audience_only = [e for e in entities if not e.topic_aware]

        panels = []
        used = set()

        for _ in range(max_panels):
            panel = []
            # Target ~40% topic-aware, ~60% audience-profile for realistic mix
            n_topic = max(1, int(panel_size * 0.4))
            n_audience = panel_size - n_topic

            for e in topic_aware:
                if e.entity_key not in used and len(panel) < n_topic:
                    panel.append(e)
                    used.add(e.entity_key)

            for e in audience_only:
                if e.entity_key not in used and len(panel) < panel_size:
                    panel.append(e)
                    used.add(e.entity_key)

            # Fill remaining from either pool
            for e in entities:
                if e.entity_key not in used and len(panel) < panel_size:
                    panel.append(e)
                    used.add(e.entity_key)

            if len(panel) >= 2:
                panels.append(panel)

            if len(used) >= len(entities):
                break

        return panels

    def run_focus_group(
        self,
        entities: list[ExtractedEntity],
        research_question: str,
        mode: str = "reality",
        scenario_description: str = "",
        num_rounds: int = 5,
        panel_size: int = 5,
        max_panels: int = 3,
    ) -> FocusGroupResult:
        """Run complete focus group sessions."""
        panels_entities = self.compose_panels(entities, panel_size, max_panels)

        panels = []
        for i, panel_entities in enumerate(panels_entities):
            panel = self._run_single_panel(
                panel_entities=panel_entities,
                panel_index=i,
                research_question=research_question,
                mode=mode,
                scenario_description=scenario_description,
                num_rounds=num_rounds,
            )
            panels.append(panel)
            logger.info(f"Panel {i+1}/{len(panels_entities)} complete: {len(panel.messages)} messages")

        return FocusGroupResult(panels=panels, mode=mode)

    def _run_single_panel(
        self,
        panel_entities: list[ExtractedEntity],
        panel_index: int,
        research_question: str,
        mode: str,
        scenario_description: str,
        num_rounds: int,
    ) -> FocusGroupPanel:
        """Run a single panel discussion."""
        panel_id = str(uuid.uuid4())[:8]
        panel = FocusGroupPanel(
            panel_id=panel_id,
            panel_name=f"Panel {panel_index + 1}",
            participants=panel_entities,
            mode=mode,
        )

        participant_descriptions = self._format_participant_descriptions(panel_entities)
        moderator_prompt = self._build_moderator_prompt(
            mode, research_question, scenario_description,
            len(panel_entities), num_rounds, participant_descriptions,
        )

        conversation_history = [{"role": "system", "content": moderator_prompt}]

        for round_num in range(num_rounds):
            # Moderator asks a question
            moderator_question = self._get_moderator_question(
                conversation_history, round_num, num_rounds
            )
            panel.messages.append(FocusGroupMessage(
                role="moderator", content=moderator_question, round_num=round_num,
            ))
            conversation_history.append({"role": "assistant", "content": moderator_question})

            # Each panelist responds
            for entity in panel_entities:
                response = self._get_panelist_response(
                    entity, moderator_question, panel.messages, round_num
                )
                panel.messages.append(FocusGroupMessage(
                    role=entity.username, content=response, round_num=round_num,
                ))

            # Feed all responses back to moderator for next round
            responses_text = "\n".join(
                f"@{m.role}: {m.content}"
                for m in panel.messages
                if m.round_num == round_num and m.role != "moderator"
            )
            conversation_history.append({"role": "user", "content": f"Participant responses:\n{responses_text}"})

        return panel

    def _build_moderator_prompt(
        self, mode, research_question, scenario_description,
        panel_size, num_rounds, participant_descriptions,
    ) -> str:
        if mode == "future":
            return MODERATOR_SYSTEM_PROMPT_FUTURE.format(
                panel_size=panel_size,
                num_rounds=num_rounds,
                research_question=research_question,
                scenario_description=scenario_description,
                participant_descriptions=participant_descriptions,
            )
        else:
            return MODERATOR_SYSTEM_PROMPT_REALITY.format(
                panel_size=panel_size,
                num_rounds=num_rounds,
                research_question=research_question,
                participant_descriptions=participant_descriptions,
            )

    def _get_moderator_question(
        self,
        conversation_history: list[dict],
        round_num: int,
        total_rounds: int,
    ) -> str:
        """Get the moderator's next question."""
        prompt = "Ask your next question to the group."
        if round_num == 0:
            prompt = "Ask your opening warm-up question to introduce the topic."
        elif round_num == total_rounds - 1:
            prompt = "Ask your final wrap-up question. Probe for unmet needs or what would change their minds."

        conversation_history.append({"role": "user", "content": prompt})

        try:
            question = self.llm.chat(
                messages=conversation_history,
                temperature=0.7,
                max_tokens=300,
            )
            conversation_history.pop()  # Remove the prompt, we'll add the response as assistant
            return question.strip()
        except Exception as e:
            conversation_history.pop()
            logger.error(f"Moderator question failed: {e}")
            return "What are your thoughts on this topic?"

    def _get_panelist_response(
        self,
        entity: ExtractedEntity,
        question: str,
        prior_messages: list[FocusGroupMessage],
        round_num: int,
    ) -> str:
        """Get a panelist's response to the moderator's question."""
        recent_posts = "\n".join(
            f"- {p.text[:150]}" for p in entity.posts[:5]
        ) or "No recent posts available."

        system_prompt = PANELIST_SYSTEM_PROMPT.format(
            display_name=entity.display_name or entity.username,
            username=entity.username,
            platform=entity.platform,
            personality_summary=entity.personality_summary or "No detailed profile available.",
            core_topics=", ".join(entity.core_topics) if entity.core_topics else "various topics",
            absent_topics=", ".join(entity.absent_topics) if entity.absent_topics else "unknown",
            engagement_pattern=entity.engagement_pattern or "average engagement",
            openness_to_new=entity.openness_to_new or "neutral",
            recent_post_summary=recent_posts,
        )

        # Include recent discussion context
        context_messages = []
        for msg in prior_messages[-6:]:
            if msg.round_num == round_num and msg.role != "moderator":
                context_messages.append(f"@{msg.role}: {msg.content}")

        context = ""
        if context_messages:
            context = f"\n\nOther participants have said:\n" + "\n".join(context_messages)

        try:
            response = self.llm.chat(
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": f"Moderator asks: {question}{context}\n\nRespond as yourself."},
                ],
                temperature=0.8,
                max_tokens=200,
            )
            return response.strip()
        except Exception as e:
            logger.error(f"Panelist @{entity.username} response failed: {e}")
            return "I don't have strong feelings about this."

    def _format_participant_descriptions(self, entities: list[ExtractedEntity]) -> str:
        lines = []
        for e in entities:
            topic_status = "discusses the topic" if e.topic_aware else "has NOT discussed the topic"
            lines.append(
                f"- @{e.username} ({e.platform}): {e.personality_summary or e.relevance_reason} "
                f"[{topic_status}]"
            )
        return "\n".join(lines)
