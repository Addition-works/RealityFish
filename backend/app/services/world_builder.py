"""
World Builder Agent.

Reads a thesis, generates search strategies (topic-aware + audience-profile queries),
orchestrates scraping across platforms, extracts entities, and performs deep profile
enrichment. Produces a complete entity pool for the Existing Reality phase.
"""

import logging
from dataclasses import dataclass, field
from typing import Optional

from .thesis_parser import Thesis
from .social_scraper import SocialScraper, ScrapeResult
from .entity_extractor import EntityExtractor, ExtractedEntity

logger = logging.getLogger("realityfish.world_builder")

QUERY_GENERATION_PROMPT = """You are a research strategist. Given a thesis about a topic and target audience profiles, generate two types of search queries for social media research.

TYPE 1 — TOPIC-AWARE QUERIES:
Keywords that find people already discussing the thesis topic.
These people are "in the conversation."

TYPE 2 — AUDIENCE-PROFILE QUERIES:
Keywords that find people who match the target audience description but may have NEVER discussed the thesis topic.
These queries should target behaviors, interests, and contexts described in the audience profiles.
Example: if the audience is "small business owners who don't code," search for terms like "my Etsy shop", "small business tips", "hiring first employee" — NOT "AI coding."

Return a JSON object with:
{
    "topic_aware_queries": ["query1", "query2", ...],
    "audience_profile_queries": [
        {
            "audience": "Name of the audience profile",
            "queries": ["query1", "query2", ...]
        },
        ...
    ]
}

Generate 3-5 topic-aware queries and 2-4 audience-profile queries per audience profile.
Queries should be concise (2-4 words each) and work well as social media search terms."""


@dataclass
class SearchStrategy:
    topic_aware_queries: list[str] = field(default_factory=list)
    audience_profile_queries: list[dict] = field(default_factory=list)

    @property
    def all_queries(self) -> list[tuple[str, str]]:
        """All queries as (query, type) tuples."""
        result = [(q, "topic_aware") for q in self.topic_aware_queries]
        for group in self.audience_profile_queries:
            for q in group.get("queries", []):
                result.append((q, f"audience:{group.get('audience', 'unknown')}"))
        return result


@dataclass
class WorldBuildProgress:
    """Tracks world building progress for UI updates."""
    phase: str = "idle"
    total_queries: int = 0
    completed_queries: int = 0
    total_entities: int = 0
    enriched_entities: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def progress_pct(self) -> int:
        if self.phase == "scraping" and self.total_queries > 0:
            return int(30 * self.completed_queries / self.total_queries)
        elif self.phase == "extracting":
            return 30
        elif self.phase == "enriching" and self.total_entities > 0:
            return 30 + int(60 * self.enriched_entities / self.total_entities)
        elif self.phase == "complete":
            return 100
        return 0


class WorldBuilder:
    """
    Orchestrates the full world-building pipeline:
    1. Generate search strategy from thesis
    2. Scrape across platforms
    3. Extract entities from scraped data
    4. Deep-scrape top entities by username
    5. Enrich entities with behavioral profiles
    """

    def __init__(self, llm_client=None, scraper: Optional[SocialScraper] = None):
        if llm_client is None:
            from ..utils.llm_client import LLMClient
            llm_client = LLMClient()
        self.llm = llm_client
        self.scraper = scraper or SocialScraper()
        self.extractor = EntityExtractor(llm_client=self.llm)
        self.progress = WorldBuildProgress()

    def generate_search_strategy(self, thesis: Thesis) -> SearchStrategy:
        """Use LLM to generate topic-aware and audience-profile search queries."""
        self.progress.phase = "planning"

        audience_text = "\n".join(
            f"### {a.name}\n{a.description}\n"
            f"Behaviors: {', '.join(a.behaviors)}\n"
            f"Interests: {', '.join(a.interests)}"
            for a in thesis.audience_profiles
        )

        user_prompt = f"""Research Question: {thesis.research_question}

Scope Keywords: {', '.join(thesis.scope.keywords)}
Geography: {thesis.scope.geography or 'global'}

Target Audiences:
{audience_text}

Known Context:
{thesis.known_context or 'None provided'}"""

        try:
            response = self.llm.chat_json(
                messages=[
                    {"role": "system", "content": QUERY_GENERATION_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0.4,
                max_tokens=2048,
            )

            strategy = SearchStrategy(
                topic_aware_queries=response.get("topic_aware_queries", thesis.scope.keywords),
                audience_profile_queries=response.get("audience_profile_queries", []),
            )

            # Ensure thesis keywords are included
            for kw in thesis.scope.keywords:
                if kw not in strategy.topic_aware_queries:
                    strategy.topic_aware_queries.append(kw)

            logger.info(
                f"Generated search strategy: {len(strategy.topic_aware_queries)} topic queries, "
                f"{sum(len(g.get('queries', [])) for g in strategy.audience_profile_queries)} audience queries"
            )
            return strategy

        except Exception as e:
            logger.error(f"Strategy generation failed, using thesis keywords as fallback: {e}")
            return SearchStrategy(topic_aware_queries=thesis.scope.keywords)

    def scrape_all(
        self,
        strategy: SearchStrategy,
        platforms: list[str],
        recency_days: int = 30,
        max_results_per_query: int = 15,
    ) -> list[ScrapeResult]:
        """Execute all search queries across specified platforms."""
        self.progress.phase = "scraping"
        all_queries = strategy.all_queries
        self.progress.total_queries = len(all_queries) * len(platforms)
        self.progress.completed_queries = 0

        all_results: list[ScrapeResult] = []

        for query, query_type in all_queries:
            results = self.scraper.search_keyword(
                query=query,
                platforms=platforms,
                max_results=max_results_per_query,
                recency_days=recency_days,
            )
            for r in results:
                if r.error:
                    self.progress.errors.append(f"{r.platform}: {r.error}")
                else:
                    all_results.append(r)
                self.progress.completed_queries += 1

        total_posts = sum(len(r.posts) for r in all_results)
        logger.info(f"Scraping complete: {total_posts} posts from {len(all_results)} successful queries")
        return all_results

    def extract_and_deduplicate(
        self,
        scrape_results: list[ScrapeResult],
        research_question: str,
    ) -> list[ExtractedEntity]:
        """Extract entities from scrape results and deduplicate."""
        self.progress.phase = "extracting"
        entities = self.extractor.extract_entities(scrape_results, research_question)
        self.progress.total_entities = len(entities)
        return entities

    def deep_scrape_entities(
        self,
        entities: list[ExtractedEntity],
        max_entities: int = 30,
        max_posts_per_user: int = 20,
        max_workers: int = 5,
    ) -> list[ExtractedEntity]:
        """Deep-scrape the top entities by username for richer profiles.
        
        Uses ThreadPoolExecutor for parallel username lookups.
        """
        from concurrent.futures import ThreadPoolExecutor, as_completed

        self.progress.phase = "deep_scraping"

        sorted_entities = sorted(entities, key=lambda e: len(e.posts), reverse=True)
        top_entities = sorted_entities[:max_entities]

        def _scrape_one(entity: ExtractedEntity) -> tuple[ExtractedEntity, int]:
            try:
                result = self.scraper.search_username(
                    username=entity.username,
                    platform=entity.platform,
                    max_results=max_posts_per_user,
                    max_submissions=max_posts_per_user,
                )
                if not result.error:
                    existing_ids = {p.post_id for p in entity.posts}
                    new_posts = [p for p in result.posts if p.post_id not in existing_ids]
                    entity.posts.extend(new_posts)

                    if result.users:
                        user = result.users[0]
                        if user.bio and not entity.bio:
                            entity.bio = user.bio
                        if user.followers and not entity.followers:
                            entity.followers = user.followers
                        if user.verified:
                            entity.verified = True

                    if not entity.bio and entity.platform == "x" and new_posts:
                        from .social_scraper import XScraper
                        for p in new_posts:
                            if p.raw_data:
                                profile = XScraper.extract_user_profile(p.raw_data)
                                if profile.get("bio"):
                                    entity.bio = profile["bio"]
                                    entity.followers = entity.followers or profile.get("followers", 0)
                                    entity.verified = entity.verified or profile.get("verified", False)
                                    entity.location = entity.location or profile.get("location", "")
                                    break

                    return entity, len(new_posts)
                else:
                    logger.warning(f"Deep scrape error for @{entity.username}: {result.error}")
                    return entity, 0
            except Exception as e:
                logger.warning(f"Deep scrape failed for @{entity.username}: {e}")
                return entity, 0

        completed = 0
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(_scrape_one, e): e for e in top_entities}
            for future in as_completed(futures):
                entity, new_count = future.result()
                completed += 1
                if new_count > 0:
                    logger.info(f"Deep scraped @{entity.username}: +{new_count} posts [{completed}/{len(top_entities)}]")

        logger.info(f"Deep scrape complete: {completed} entities processed in parallel (max_workers={max_workers})")
        return entities

    def enrich_entities(self, entities: list[ExtractedEntity]) -> list[ExtractedEntity]:
        """Enrich all entities with behavioral profiles."""
        self.progress.phase = "enriching"
        self.progress.enriched_entities = 0

        for entity in entities:
            self.extractor.enrich_entity(entity)
            self.progress.enriched_entities += 1

        self.progress.phase = "complete"
        return entities

    def build_world(
        self,
        thesis: Thesis,
        max_entities: int = 30,
        max_results_per_query: int = 15,
    ) -> list[ExtractedEntity]:
        """
        Full world-building pipeline.

        1. Generate search strategy from thesis
        2. Scrape across platforms
        3. Extract and deduplicate entities
        4. Populate profile metadata (bio, followers, verified)
        5. Deep-scrape top entities (parallel)
        6. Score against thesis audience profiles
        7. Enrich with behavioral profiles

        Returns the complete entity pool.
        """
        logger.info("Starting world build")

        strategy = self.generate_search_strategy(thesis)

        scrape_results = self.scrape_all(
            strategy=strategy,
            platforms=thesis.scope.platforms,
            recency_days=thesis.scope.time_window_days,
            max_results_per_query=max_results_per_query,
        )

        entities = self.extract_and_deduplicate(
            scrape_results=scrape_results,
            research_question=thesis.research_question,
        )

        entities = self.extractor.populate_profile_metadata(entities)

        entities = self.deep_scrape_entities(entities, max_entities=max_entities)

        entities = self.extractor.score_against_audiences(
            entities, thesis.audience_profiles,
        )

        entities = self.enrich_entities(entities)

        logger.info(f"World build complete: {len(entities)} entities")
        return entities
