"""
Reality Graph Builder.

Extends the existing GraphBuilderService to load scraped entities (with metadata
like topic_aware, source_platform) into Zep, and to store focus group transcripts.
"""

import uuid
import time
import logging
import threading
from typing import Optional, Callable

from zep_cloud.client import Zep
from zep_cloud import EpisodeData

from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..utils.zep_paging import fetch_all_nodes, fetch_all_edges
from .entity_extractor import ExtractedEntity
from .focus_group_engine import FocusGroupResult

logger = logging.getLogger("realityfish.reality_graph")


class RealityGraphBuilder:
    """
    Builds a Zep knowledge graph from scraped entities and focus group transcripts.

    Entity data is formatted as text episodes that Zep's graph engine can parse
    into nodes and edges. Each entity becomes a rich text block describing who
    they are, what they've said, and how they relate to the research topic.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or Config.ZEP_API_KEY
        if not self.api_key:
            raise ValueError("ZEP_API_KEY not configured")
        self.client = Zep(api_key=self.api_key)
        self.task_manager = TaskManager()

    def create_graph(self, project_name: str = "RealityFish Research") -> str:
        """Create a new Zep graph for the project."""
        graph_id = f"reality_{uuid.uuid4().hex[:12]}"
        self.client.graph.create(
            graph_id=graph_id,
            name=project_name,
            description="RealityFish — scraped entities and social context",
        )
        logger.info(f"Created reality graph: {graph_id}")
        return graph_id

    def load_entities(
        self,
        graph_id: str,
        entities: list[ExtractedEntity],
        batch_size: int = 5,
        progress_callback: Optional[Callable] = None,
    ) -> list[str]:
        """
        Load scraped entities into a Zep graph as text episodes.

        Each entity is formatted as a structured text block that Zep's
        graph engine will parse into nodes and edges.
        """
        episodes_data = []
        for entity in entities:
            text = self._format_entity_as_episode(entity)
            episodes_data.append(text)

        episode_uuids = []
        total = len(episodes_data)

        for i in range(0, total, batch_size):
            batch = episodes_data[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            if progress_callback:
                progress_callback(
                    f"Loading entity batch {batch_num}/{total_batches}",
                    (i + len(batch)) / total,
                )

            episodes = [EpisodeData(data=text, type="text") for text in batch]

            try:
                batch_result = self.client.graph.add_batch(
                    graph_id=graph_id,
                    episodes=episodes,
                )
                if batch_result and isinstance(batch_result, list):
                    for ep in batch_result:
                        ep_uuid = getattr(ep, 'uuid_', None) or getattr(ep, 'uuid', None)
                        if ep_uuid:
                            episode_uuids.append(ep_uuid)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Entity batch {batch_num} failed: {e}")
                raise

        logger.info(f"Loaded {total} entities into graph {graph_id}")
        return episode_uuids

    def load_focus_group_transcripts(
        self,
        graph_id: str,
        focus_group_result: FocusGroupResult,
    ) -> list[str]:
        """Load focus group transcripts into the Zep graph as episodes."""
        episode_uuids = []

        for panel in focus_group_result.panels:
            transcript = panel.transcript_text
            episodes = [EpisodeData(data=transcript, type="text")]

            try:
                batch_result = self.client.graph.add_batch(
                    graph_id=graph_id,
                    episodes=episodes,
                )
                if batch_result and isinstance(batch_result, list):
                    for ep in batch_result:
                        ep_uuid = getattr(ep, 'uuid_', None) or getattr(ep, 'uuid', None)
                        if ep_uuid:
                            episode_uuids.append(ep_uuid)
                time.sleep(1)
            except Exception as e:
                logger.error(f"Focus group transcript load failed: {e}")
                raise

        logger.info(f"Loaded {len(focus_group_result.panels)} focus group transcripts")
        return episode_uuids

    def wait_for_processing(
        self,
        episode_uuids: list[str],
        timeout: int = 600,
        progress_callback: Optional[Callable] = None,
    ):
        """Wait for all episodes to be processed by Zep."""
        if not episode_uuids:
            return

        start_time = time.time()
        pending = set(episode_uuids)
        completed = 0
        total = len(episode_uuids)

        while pending:
            if time.time() - start_time > timeout:
                logger.warning(f"Timeout: {completed}/{total} episodes processed")
                break

            for ep_uuid in list(pending):
                try:
                    episode = self.client.graph.episode.get(uuid_=ep_uuid)
                    if getattr(episode, 'processed', False):
                        pending.remove(ep_uuid)
                        completed += 1
                except Exception:
                    pass

            if progress_callback:
                elapsed = int(time.time() - start_time)
                progress_callback(
                    f"Zep processing: {completed}/{total} episodes ({elapsed}s)",
                    completed / total if total > 0 else 0,
                )

            if pending:
                time.sleep(3)

    def get_graph_summary(self, graph_id: str) -> dict:
        """Get a summary of the graph (node/edge counts and types)."""
        nodes = fetch_all_nodes(self.client, graph_id)
        edges = fetch_all_edges(self.client, graph_id)

        entity_types = set()
        for node in nodes:
            if node.labels:
                for label in node.labels:
                    if label not in ("Entity", "Node"):
                        entity_types.add(label)

        return {
            "graph_id": graph_id,
            "node_count": len(nodes),
            "edge_count": len(edges),
            "entity_types": sorted(entity_types),
        }

    def get_entity_pool_summary(self, graph_id: str) -> dict:
        """Get a human-readable summary of the entity pool for review."""
        nodes = fetch_all_nodes(self.client, graph_id)
        edges = fetch_all_edges(self.client, graph_id)

        node_map = {}
        for node in nodes:
            node_map[node.uuid_] = {
                "name": node.name,
                "labels": node.labels or [],
                "summary": node.summary or "",
            }

        relationships = []
        for edge in edges:
            source = node_map.get(edge.source_node_uuid, {}).get("name", "?")
            target = node_map.get(edge.target_node_uuid, {}).get("name", "?")
            relationships.append({
                "source": source,
                "relationship": edge.name or edge.fact or "",
                "target": target,
            })

        return {
            "graph_id": graph_id,
            "entities": [
                {"name": n["name"], "types": n["labels"], "summary": n["summary"]}
                for n in node_map.values()
            ],
            "relationships": relationships[:50],
            "total_entities": len(nodes),
            "total_relationships": len(edges),
        }

    def _format_entity_as_episode(self, entity: ExtractedEntity) -> str:
        """Format an entity as a rich text block for Zep ingestion."""
        lines = []

        lines.append(f"Social Media Entity Profile: @{entity.username}")
        lines.append(f"Platform: {entity.platform}")
        if entity.display_name:
            lines.append(f"Display Name: {entity.display_name}")

        topic_status = "actively discusses the research topic" if entity.topic_aware else "has not discussed the research topic directly"
        lines.append(f"Topic Awareness: @{entity.username} {topic_status}.")

        if entity.relevance_reason:
            lines.append(f"Relevance: {entity.relevance_reason}")
        if entity.sentiment_summary:
            lines.append(f"Current Stance: {entity.sentiment_summary}")

        if entity.personality_summary:
            lines.append(f"\nBehavioral Profile: {entity.personality_summary}")
        if entity.communication_style:
            lines.append(f"Communication Style: {entity.communication_style}")
        if entity.core_topics:
            lines.append(f"Core Topics: {', '.join(entity.core_topics)}")
        if entity.absent_topics:
            lines.append(f"Notably Absent Topics: {', '.join(entity.absent_topics)}")
        if entity.engagement_pattern:
            lines.append(f"Engagement Pattern: {entity.engagement_pattern}")
        if entity.openness_to_new:
            lines.append(f"Openness to New Ideas: {entity.openness_to_new}")

        if entity.posts:
            lines.append(f"\nRecent Activity ({len(entity.posts)} posts):")
            for post in entity.posts[:8]:
                text = post.text[:200].replace("\n", " ")
                lines.append(f"- [{post.platform}] {text} (likes: {post.likes}, replies: {post.replies})")

        return "\n".join(lines)
