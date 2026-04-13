"""
Entity Extractor.

Takes raw scraped posts and uses LLM to identify real entities (people, accounts),
deduplicate them across platforms, and enrich with behavioral summaries.
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Optional

from .social_scraper import ScrapedPost, ScrapeResult, XScraper

logger = logging.getLogger("realityfish.entity_extractor")

EXTRACTION_SYSTEM_PROMPT = """You are an entity extraction agent. Given a batch of social media posts, identify distinct real people or accounts that appear in them.

For each entity, extract:
- username: their handle/username on the platform
- platform: "x" or "reddit"
- display_name: their display name if available
- topic_aware: true if they are discussing the research topic directly, false if they match the audience profile but aren't talking about it
- relevance_reason: brief explanation of why this person is relevant (1 sentence)
- sentiment_summary: brief summary of their stance/attitude based on their posts (1 sentence)
- post_ids: list of post IDs from the input that belong to this entity

IMPORTANT:
- Deduplicate: if the same person appears in multiple posts, merge them into one entity
- Skip bot-looking accounts, deleted users, or accounts with no meaningful content
- Focus on REAL people who could participate in a simulation
- Be concise in summaries

Return a JSON object with key "entities" containing an array of entity objects."""

ENRICHMENT_SYSTEM_PROMPT = """You are a behavioral profiling agent. Given a person's social media posts, create a rich behavioral profile.

Analyze:
1. Communication style (formal/casual, verbose/concise, emotional/analytical)
2. Topics they care about (what they discuss most)
3. Topics they DON'T discuss (notable absences given their profile)
4. Community engagement patterns (do they post, comment, lurk?)
5. Likely response to new information (early adopter, skeptic, indifferent?)

Return a JSON object with these keys:
- communication_style: string (1 sentence)
- core_topics: list of strings (3-5 topics)
- absent_topics: list of strings (2-3 notable gaps)
- engagement_pattern: string (1 sentence)
- openness_to_new: string ("eager", "curious", "neutral", "skeptical", "resistant")
- personality_summary: string (2-3 sentences capturing who this person is)"""


@dataclass
class ExtractedEntity:
    username: str
    platform: str
    display_name: str = ""
    topic_aware: bool = False
    relevance_reason: str = ""
    sentiment_summary: str = ""
    post_ids: list[str] = field(default_factory=list)
    posts: list[ScrapedPost] = field(default_factory=list)

    # Profile metadata (populated from scraper raw_data)
    bio: str = ""
    followers: int = 0
    following: int = 0
    verified: bool = False
    location: str = ""

    # Audience scoring (populated by score_against_audiences)
    audience_scores: dict = field(default_factory=dict)

    # Enrichment fields (populated by enrich_entity)
    communication_style: str = ""
    core_topics: list[str] = field(default_factory=list)
    absent_topics: list[str] = field(default_factory=list)
    engagement_pattern: str = ""
    openness_to_new: str = ""
    personality_summary: str = ""

    @property
    def entity_key(self) -> str:
        return f"{self.platform}:{self.username.lower()}"

    def to_dict(self) -> dict:
        d = {
            "username": self.username,
            "platform": self.platform,
            "display_name": self.display_name,
            "bio": self.bio,
            "followers": self.followers,
            "verified": self.verified,
            "location": self.location,
            "topic_aware": self.topic_aware,
            "relevance_reason": self.relevance_reason,
            "sentiment_summary": self.sentiment_summary,
            "post_count": len(self.posts),
            "audience_scores": self.audience_scores,
            "communication_style": self.communication_style,
            "core_topics": self.core_topics,
            "absent_topics": self.absent_topics,
            "engagement_pattern": self.engagement_pattern,
            "openness_to_new": self.openness_to_new,
            "personality_summary": self.personality_summary,
        }
        return d


class EntityExtractor:
    """Extracts and enriches entities from scraped social media data."""

    def __init__(self, llm_client=None):
        if llm_client is None:
            from ..utils.llm_client import LLMClient
            llm_client = LLMClient()
        self.llm = llm_client

    def extract_entities(
        self,
        scrape_results: list[ScrapeResult],
        research_question: str = "",
    ) -> list[ExtractedEntity]:
        """
        Extract entities from multiple scrape results.
        Deduplicates across results and platforms.
        """
        all_posts = []
        for result in scrape_results:
            if not result.error:
                all_posts.extend(result.posts)

        if not all_posts:
            logger.warning("No posts to extract entities from")
            return []

        # Process in batches to stay within token limits
        batch_size = 30
        all_entities: dict[str, ExtractedEntity] = {}

        for i in range(0, len(all_posts), batch_size):
            batch = all_posts[i:i + batch_size]
            batch_entities = self._extract_batch(batch, research_question)

            for entity in batch_entities:
                key = entity.entity_key
                if key in all_entities:
                    existing = all_entities[key]
                    existing.post_ids.extend(entity.post_ids)
                    existing.posts.extend(entity.posts)
                    if entity.topic_aware:
                        existing.topic_aware = True
                else:
                    all_entities[key] = entity

        entities = list(all_entities.values())
        logger.info(f"Extracted {len(entities)} unique entities from {len(all_posts)} posts")
        return entities

    def _extract_batch(
        self,
        posts: list[ScrapedPost],
        research_question: str,
    ) -> list[ExtractedEntity]:
        """Extract entities from a batch of posts using LLM."""
        posts_text = self._format_posts_for_llm(posts)

        user_prompt = f"""Research context: {research_question}

Here are the social media posts to analyze:

{posts_text}

Extract all distinct real entities from these posts."""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": EXTRACTION_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.2,
                max_tokens=4096,
            )

            raw_entities = response.get("entities", [])
            posts_by_id = {p.post_id: p for p in posts}

            entities = []
            for raw in raw_entities:
                entity = ExtractedEntity(
                    username=raw.get("username", ""),
                    platform=raw.get("platform", ""),
                    display_name=raw.get("display_name", ""),
                    topic_aware=raw.get("topic_aware", False),
                    relevance_reason=raw.get("relevance_reason", ""),
                    sentiment_summary=raw.get("sentiment_summary", ""),
                    post_ids=raw.get("post_ids", []),
                )
                entity.posts = [posts_by_id[pid] for pid in entity.post_ids if pid in posts_by_id]
                if entity.username:
                    entities.append(entity)

            return entities

        except Exception as e:
            logger.error(f"Entity extraction failed: {e}")
            return self._fallback_extraction(posts)

    def _fallback_extraction(self, posts: list[ScrapedPost]) -> list[ExtractedEntity]:
        """Simple fallback: create one entity per unique author."""
        entities: dict[str, ExtractedEntity] = {}
        for post in posts:
            key = f"{post.platform}:{post.author_username.lower()}"
            if key not in entities and post.author_username and post.author_username != "[deleted]":
                entities[key] = ExtractedEntity(
                    username=post.author_username,
                    platform=post.platform,
                    display_name=post.author_display_name,
                    topic_aware=True,
                    relevance_reason="Found via keyword search",
                    post_ids=[post.post_id],
                    posts=[post],
                )
            elif key in entities:
                entities[key].post_ids.append(post.post_id)
                entities[key].posts.append(post)
        return list(entities.values())

    def populate_profile_metadata(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """Populate bio/followers/verified from raw_data on each entity's posts."""
        for entity in entities:
            if entity.bio:
                continue
            if entity.platform == "x":
                for post in entity.posts:
                    if post.raw_data:
                        profile = XScraper.extract_user_profile(post.raw_data)
                        if profile.get("bio"):
                            entity.bio = profile["bio"]
                            entity.followers = profile.get("followers", 0)
                            entity.following = profile.get("following", 0)
                            entity.verified = profile.get("verified", False)
                            entity.location = profile.get("location", "")
                            break
            elif entity.platform == "reddit":
                for post in entity.posts:
                    if post.raw_data and post.raw_data.get("user_bio"):
                        entity.bio = post.raw_data["user_bio"]
                        break
        populated = sum(1 for e in entities if e.bio)
        logger.info(f"Populated profile metadata: {populated}/{len(entities)} entities have bios")
        return entities

    def enrich_entity(self, entity: ExtractedEntity) -> ExtractedEntity:
        """Add behavioral profile to an entity based on their posts."""
        if not entity.posts:
            return entity

        posts_text = "\n\n".join(
            f"[{p.platform}] @{p.author_username}: {p.text[:300]}"
            for p in entity.posts[:10]
        )

        bio_line = f"\nBio: {entity.bio}" if entity.bio else ""
        followers_line = f"\nFollowers: {entity.followers:,}" if entity.followers else ""
        verified_line = "\nVerified: Yes" if entity.verified else ""
        location_line = f"\nLocation: {entity.location}" if entity.location else ""

        user_prompt = f"""Profile this person based on their social media activity:

Username: @{entity.username} ({entity.platform})
Display name: {entity.display_name}{bio_line}{followers_line}{verified_line}{location_line}

Their recent posts:
{posts_text}"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": ENRICHMENT_SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.3,
                max_tokens=2048,
            )

            entity.communication_style = response.get("communication_style", "")
            entity.core_topics = response.get("core_topics", [])
            entity.absent_topics = response.get("absent_topics", [])
            entity.engagement_pattern = response.get("engagement_pattern", "")
            entity.openness_to_new = response.get("openness_to_new", "neutral")
            entity.personality_summary = response.get("personality_summary", "")

        except Exception as e:
            logger.error(f"Entity enrichment failed for @{entity.username}: {e}")

        return entity

    def score_against_audiences(
        self,
        entities: list[ExtractedEntity],
        audience_profiles: list,
    ) -> list[ExtractedEntity]:
        """Score each entity against the thesis audience profiles using LLM.
        
        Each entity gets a dict like {"Small Business Owners": 0.8, "AI Hobbyists": 0.3}.
        Processed in batches to reduce LLM calls.
        """
        if not audience_profiles:
            return entities

        audiences_desc = "\n".join(
            f"- {a.name}: {a.description}"
            for a in audience_profiles
        )
        audience_names = [a.name for a in audience_profiles]

        system_prompt = f"""You are an audience classification agent. Score how well each person matches the target audience profiles.

Target Audience Profiles:
{audiences_desc}

For each person, assign a score from 0.0 to 1.0 for EACH audience profile:
- 1.0 = perfect match (clearly belongs to this audience)
- 0.5 = partial match (some signals but not definitive)
- 0.0 = no match

Return JSON: {{"scores": [{{"username": "...", "audience_name_1": 0.8, "audience_name_2": 0.2}}, ...]}}"""

        batch_size = 20
        for i in range(0, len(entities), batch_size):
            batch = entities[i:i + batch_size]
            entity_summaries = []
            for e in batch:
                summary = f"@{e.username} ({e.platform})"
                if e.bio:
                    summary += f" | Bio: {e.bio[:150]}"
                if e.posts:
                    summary += f" | Recent post: {e.posts[0].text[:150]}"
                if e.core_topics:
                    summary += f" | Topics: {', '.join(e.core_topics[:3])}"
                entity_summaries.append(summary)

            user_prompt = f"""Score these {len(batch)} people against the audience profiles:

{chr(10).join(f'{j+1}. {s}' for j, s in enumerate(entity_summaries))}"""

            try:
                response = self.llm.chat_json(
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    temperature=0.2,
                    max_tokens=4096,
                )

                scores_list = response.get("scores", [])
                scores_by_username = {}
                for s in scores_list:
                    uname = s.get("username", "").lstrip("@").lower()
                    scores_by_username[uname] = {
                        k: v for k, v in s.items()
                        if k != "username" and isinstance(v, (int, float))
                    }

                for e in batch:
                    key = e.username.lower()
                    if key in scores_by_username:
                        e.audience_scores = scores_by_username[key]

            except Exception as ex:
                logger.error(f"Audience scoring batch failed: {ex}")

        scored = sum(1 for e in entities if e.audience_scores)
        logger.info(f"Audience scoring complete: {scored}/{len(entities)} entities scored")
        return entities

    def _format_posts_for_llm(self, posts: list[ScrapedPost]) -> str:
        lines = []
        for p in posts:
            lines.append(
                f"[ID: {p.post_id}] [{p.platform}] @{p.author_username}"
                f" ({p.author_display_name}): {p.text[:300]}"
                f" | likes={p.likes} reposts={p.reposts} replies={p.replies}"
            )
        return "\n\n".join(lines)
