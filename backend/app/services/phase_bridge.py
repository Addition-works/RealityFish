"""
Phase 1 → Phase 2 Bridge.

Converts Existing Reality entities (scraped real people with behavioral profiles)
into OASIS agent profiles with awareness probabilities. This bridges the gap
between the real-data world built in Phase 1 and the simulation in Phase 2.
"""

import random
import logging
from typing import Optional

from .entity_extractor import ExtractedEntity
from .awareness_engine import AwarenessEngine, AwarenessProfile
from .oasis_profile_generator import OasisAgentProfile

logger = logging.getLogger("realityfish.phase_bridge")

MBTI_MAPPING = {
    "eager": ["ENFP", "ENTP", "ENTJ", "ENFJ"],
    "curious": ["INTP", "INFP", "ISTP", "ENFP"],
    "neutral": ["ISTJ", "ISFJ", "ESTJ", "ESFJ"],
    "skeptical": ["INTJ", "ISTJ", "ISTP", "INTP"],
    "resistant": ["ISTJ", "ISFJ", "ESTJ", "ISFP"],
}


class PhaseBridge:
    """Converts Phase 1 entities into Phase 2 OASIS simulation profiles."""

    def __init__(self, awareness_engine: Optional[AwarenessEngine] = None):
        self.awareness_engine = awareness_engine or AwarenessEngine()

    def convert_entities_to_profiles(
        self,
        entities: list[ExtractedEntity],
        scenario_description: str = "",
    ) -> tuple[list[OasisAgentProfile], list[AwarenessProfile]]:
        """
        Convert all entities to OASIS profiles and compute awareness probabilities.

        Returns:
            (oasis_profiles, awareness_profiles) — matched by index
        """
        awareness_profiles = self.awareness_engine.calculate_batch(entities)
        oasis_profiles = []

        for i, (entity, awareness) in enumerate(zip(entities, awareness_profiles)):
            profile = self._entity_to_oasis_profile(entity, i)
            oasis_profiles.append(profile)

        logger.info(
            f"Converted {len(oasis_profiles)} entities to OASIS profiles. "
            f"Topic-aware: {sum(1 for a in awareness_profiles if a.topic_aware)}, "
            f"Audience-profile: {sum(1 for a in awareness_profiles if not a.topic_aware)}"
        )
        return oasis_profiles, awareness_profiles

    def _entity_to_oasis_profile(
        self,
        entity: ExtractedEntity,
        user_id: int,
    ) -> OasisAgentProfile:
        """Convert a single ExtractedEntity to an OasisAgentProfile."""
        # Build a rich persona from the entity's real data
        persona_parts = []
        if entity.personality_summary:
            persona_parts.append(entity.personality_summary)
        if entity.relevance_reason:
            persona_parts.append(f"Context: {entity.relevance_reason}")
        if entity.sentiment_summary:
            persona_parts.append(f"Current stance: {entity.sentiment_summary}")

        topic_status = "already aware of and discussing the topic" if entity.topic_aware \
            else "not currently aware of or discussing the topic"
        persona_parts.append(f"This person is {topic_status}.")

        if entity.engagement_pattern:
            persona_parts.append(f"Engagement: {entity.engagement_pattern}")

        # Include sample of real posts for richer context
        if entity.posts:
            sample_posts = entity.posts[:3]
            posts_text = " | ".join(p.text[:100] for p in sample_posts)
            persona_parts.append(f"Recent activity: {posts_text}")

        persona = " ".join(persona_parts)

        # Bio from display name and core topics
        bio_parts = []
        if entity.core_topics:
            bio_parts.append(f"Interested in {', '.join(entity.core_topics[:3])}")
        if entity.communication_style:
            bio_parts.append(entity.communication_style)
        bio = ". ".join(bio_parts) if bio_parts else f"@{entity.username} on {entity.platform}"

        # Infer MBTI from openness
        openness = entity.openness_to_new.lower() if entity.openness_to_new else "neutral"
        mbti_options = MBTI_MAPPING.get(openness, MBTI_MAPPING["neutral"])
        mbti = random.choice(mbti_options)

        # Estimate engagement stats from post data
        follower_count = entity.posts[0].views // 10 if entity.posts and entity.posts[0].views else random.randint(50, 5000)
        friend_count = follower_count // 2

        return OasisAgentProfile(
            user_id=user_id,
            user_name=entity.username,
            name=entity.display_name or entity.username,
            bio=bio,
            persona=persona,
            karma=sum(p.likes for p in entity.posts) if entity.posts else 100,
            friend_count=friend_count,
            follower_count=follower_count,
            statuses_count=len(entity.posts) * 50 if entity.posts else 100,
            mbti=mbti,
            country="US",
            interested_topics=entity.core_topics[:5] if entity.core_topics else [],
            source_entity_uuid=entity.entity_key,
            source_entity_type="scraped_entity",
        )

    def generate_awareness_config(
        self,
        awareness_profiles: list[AwarenessProfile],
    ) -> dict:
        """
        Generate a config dict mapping agent user_ids to awareness probabilities,
        for use by the modified OASIS simulation runner.
        """
        config = {}
        for i, profile in enumerate(awareness_profiles):
            config[str(i)] = {
                "awareness_probability": profile.awareness_probability,
                "caring_probability": profile.caring_probability,
                "topic_aware": profile.topic_aware,
                "factors": profile.factors,
            }
        return config
