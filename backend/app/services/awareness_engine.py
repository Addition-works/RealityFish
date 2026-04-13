"""
Awareness Engine.

Calculates the probability that an agent "notices" an event during simulation,
based on their profile characteristics. This replaces the default MiroFish
assumption that every agent engages with every event.

The flow for each event reaching an agent:
1. Roll against awareness_probability → if fail, agent doesn't notice (silence)
2. If noticed, roll against caring_probability → if fail, agent noticed but doesn't engage
3. If both pass, agent processes and may respond
"""

import random
import logging
from dataclasses import dataclass, field

from .entity_extractor import ExtractedEntity

logger = logging.getLogger("realityfish.awareness")


@dataclass
class AwarenessProfile:
    """Awareness probabilities for a single agent."""
    entity_key: str
    username: str
    platform: str
    awareness_probability: float  # chance of noticing an event (0.0-1.0)
    caring_probability: float     # chance of caring IF noticed (0.0-1.0)
    topic_aware: bool
    factors: dict = field(default_factory=dict)

    @property
    def engagement_probability(self) -> float:
        """Combined probability of both noticing AND caring."""
        return self.awareness_probability * self.caring_probability

    def roll_notices(self) -> bool:
        return random.random() < self.awareness_probability

    def roll_cares(self) -> bool:
        return random.random() < self.caring_probability

    def roll_engages(self) -> tuple[bool, bool]:
        """Returns (noticed, cares). If not noticed, cares is always False."""
        noticed = self.roll_notices()
        if not noticed:
            return False, False
        cares = self.roll_cares()
        return True, cares


class AwarenessEngine:
    """
    Calculates awareness probabilities for entities based on their profiles.

    Factors that increase awareness:
    - Topic-aware entity (they're already in the conversation)
    - High engagement pattern (they post/interact frequently)
    - Openness to new things (eager > curious > neutral > skeptical > resistant)
    - Platform alignment (event on same platform as entity)

    Factors that decrease awareness:
    - Audience-profile entity (never discussed the topic)
    - Low engagement pattern
    - Resistant to new things
    - Cross-platform event
    """

    DEFAULT_BASE_PROBABILITY = 0.15
    DEFAULT_TOPIC_AWARE_BOOST = 0.5
    DEFAULT_CARING_BASE = 0.3

    OPENNESS_MODIFIERS = {
        "eager": 0.25,
        "curious": 0.15,
        "neutral": 0.0,
        "skeptical": -0.10,
        "resistant": -0.15,
    }

    ENGAGEMENT_MODIFIERS = {
        "high": 0.15,
        "moderate": 0.05,
        "low": -0.10,
    }

    def __init__(
        self,
        base_probability: float = None,
        topic_aware_boost: float = None,
    ):
        from ..config import Config
        self.base_probability = base_probability or Config.AWARENESS_BASE_PROBABILITY
        self.topic_aware_boost = topic_aware_boost or Config.TOPIC_AWARE_BOOST

    def calculate_awareness(self, entity: ExtractedEntity) -> AwarenessProfile:
        """Calculate awareness probabilities for a single entity."""
        factors = {}

        # Start with base probability
        prob = self.base_probability
        factors["base"] = self.base_probability

        # Topic awareness is the biggest factor
        if entity.topic_aware:
            prob += self.topic_aware_boost
            factors["topic_aware"] = self.topic_aware_boost
        else:
            factors["topic_aware"] = 0.0

        # Openness to new things
        openness = entity.openness_to_new.lower() if entity.openness_to_new else "neutral"
        openness_mod = self.OPENNESS_MODIFIERS.get(openness, 0.0)
        prob += openness_mod
        factors["openness"] = openness_mod

        # Engagement pattern
        engagement = self._classify_engagement(entity)
        engagement_mod = self.ENGAGEMENT_MODIFIERS.get(engagement, 0.0)
        prob += engagement_mod
        factors["engagement"] = engagement_mod

        # Clamp to [0.05, 0.95] — always a small chance of noticing/missing
        awareness_prob = max(0.05, min(0.95, prob))

        # Caring probability: how likely they are to engage IF they notice
        caring_prob = self._calculate_caring(entity)

        return AwarenessProfile(
            entity_key=entity.entity_key,
            username=entity.username,
            platform=entity.platform,
            awareness_probability=round(awareness_prob, 3),
            caring_probability=round(caring_prob, 3),
            topic_aware=entity.topic_aware,
            factors=factors,
        )

    def calculate_batch(self, entities: list[ExtractedEntity]) -> list[AwarenessProfile]:
        """Calculate awareness for all entities."""
        profiles = [self.calculate_awareness(e) for e in entities]
        logger.info(
            f"Awareness calculated for {len(profiles)} entities. "
            f"Avg awareness: {sum(p.awareness_probability for p in profiles) / len(profiles):.2f}, "
            f"Avg engagement: {sum(p.engagement_probability for p in profiles) / len(profiles):.2f}"
        )
        return profiles

    def _classify_engagement(self, entity: ExtractedEntity) -> str:
        """Classify engagement level based on post count and patterns."""
        pattern = entity.engagement_pattern.lower() if entity.engagement_pattern else ""
        if any(w in pattern for w in ("active", "frequent", "prolific", "regular")):
            return "high"
        elif any(w in pattern for w in ("occasional", "moderate", "sometimes")):
            return "moderate"
        elif any(w in pattern for w in ("rare", "lurk", "infrequent", "passive")):
            return "low"
        # Fallback: use post count
        if len(entity.posts) >= 5:
            return "high"
        elif len(entity.posts) >= 2:
            return "moderate"
        return "low"

    def _calculate_caring(self, entity: ExtractedEntity) -> float:
        """Calculate how likely entity is to care IF they notice."""
        base = self.DEFAULT_CARING_BASE

        if entity.topic_aware:
            base += 0.35

        openness = entity.openness_to_new.lower() if entity.openness_to_new else "neutral"
        if openness in ("eager", "curious"):
            base += 0.15
        elif openness in ("skeptical", "resistant"):
            base -= 0.10

        return max(0.10, min(0.95, base))
