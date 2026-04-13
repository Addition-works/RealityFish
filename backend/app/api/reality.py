"""
RealityFish API endpoints.

Covers the full two-phase pipeline:
- Thesis upload and parsing
- World building (scraping + entity extraction)
- World review and approval
- Existing Reality report generation
- Focus groups
- Phase 2 scenario injection and simulation
"""

import os
import uuid
import json
import threading
import logging
from flask import request, jsonify

from . import reality_bp
from ..config import Config
from ..models.task import TaskManager, TaskStatus
from ..services.thesis_parser import parse_thesis
from ..services.world_builder import WorldBuilder
from ..services.entity_extractor import ExtractedEntity
from ..services.social_scraper import SocialScraper
from ..services.reality_graph_builder import RealityGraphBuilder
from ..services.focus_group_engine import FocusGroupEngine
from ..services.reality_report_adapter import RealityReportAdapter
from ..services.phase_bridge import PhaseBridge

logger = logging.getLogger("realityfish.api")

# In-memory project state (would be DB-backed in production)
_projects: dict[str, dict] = {}
_task_manager = TaskManager()


@reality_bp.route('/thesis/upload', methods=['POST'])
def upload_thesis():
    """Upload and parse a thesis MD file."""
    if 'file' not in request.files:
        content = request.get_json()
        if content and 'text' in content:
            text = content['text']
        else:
            return jsonify({"error": "No file or text provided"}), 400
    else:
        file = request.files['file']
        text = file.read().decode('utf-8')

    thesis = parse_thesis(text)
    errors = thesis.validate()
    if errors:
        return jsonify({"error": "Invalid thesis", "details": errors}), 400

    project_id = f"proj_{uuid.uuid4().hex[:12]}"
    _projects[project_id] = {
        "id": project_id,
        "thesis": thesis,
        "phase": "thesis_parsed",
        "entities": [],
        "graph_id": None,
        "focus_group_result": None,
        "reality_report_id": None,
        "future_report_id": None,
    }

    return jsonify({
        "project_id": project_id,
        "research_question": thesis.research_question,
        "scope": {
            "platforms": thesis.scope.platforms,
            "keywords": thesis.scope.keywords,
            "geography": thesis.scope.geography,
            "time_window_days": thesis.scope.time_window_days,
        },
        "audience_profiles": [
            {"name": a.name, "description": a.description[:200]}
            for a in thesis.audience_profiles
        ],
        "known_context_preview": thesis.known_context[:200] if thesis.known_context else "",
    })


@reality_bp.route('/world/build', methods=['POST'])
def start_world_build():
    """Start the world building process (scraping + entity extraction)."""
    data = request.get_json()
    project_id = data.get("project_id")

    if project_id not in _projects:
        return jsonify({"error": "Project not found"}), 404

    project = _projects[project_id]
    thesis = project["thesis"]

    task_id = _task_manager.create_task(
        task_type="world_build",
        metadata={"project_id": project_id},
    )

    project["phase"] = "world_building"
    project["world_build_task_id"] = task_id

    max_entities = data.get("max_entities", 30)
    max_results_per_query = data.get("max_results_per_query", 15)

    thread = threading.Thread(
        target=_world_build_worker,
        args=(task_id, project_id, thesis, max_entities, max_results_per_query),
        daemon=True,
    )
    thread.start()

    return jsonify({"task_id": task_id, "project_id": project_id})


def _world_build_worker(task_id, project_id, thesis, max_entities, max_results_per_query):
    """Background worker for world building."""
    try:
        _task_manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=5, message="Initializing...")

        builder = WorldBuilder()

        _task_manager.update_task(task_id, progress=10, message="Generating search strategy...")
        strategy = builder.generate_search_strategy(thesis)

        def scrape_progress(msg, pct):
            _task_manager.update_task(task_id, progress=10 + int(pct * 30), message=msg)

        _task_manager.update_task(task_id, progress=15, message="Scraping social media...")
        scrape_results = builder.scrape_all(
            strategy=strategy,
            platforms=thesis.scope.platforms,
            recency_days=thesis.scope.time_window_days,
            max_results_per_query=max_results_per_query,
        )

        _task_manager.update_task(task_id, progress=45, message="Extracting entities...")
        entities = builder.extract_and_deduplicate(scrape_results, thesis.research_question)

        _task_manager.update_task(task_id, progress=55, message="Deep scraping top entities...")
        entities = builder.deep_scrape_entities(entities, max_entities=max_entities)

        _task_manager.update_task(task_id, progress=70, message="Enriching entity profiles...")
        entities = builder.enrich_entities(entities)

        _task_manager.update_task(task_id, progress=85, message="Loading into knowledge graph...")
        graph_builder = RealityGraphBuilder()
        graph_id = graph_builder.create_graph(f"Reality: {thesis.research_question[:50]}")

        episode_uuids = graph_builder.load_entities(graph_id, entities)
        graph_builder.wait_for_processing(episode_uuids, timeout=300)

        project = _projects[project_id]
        project["entities"] = entities
        project["graph_id"] = graph_id
        project["phase"] = "world_built"

        summary = graph_builder.get_graph_summary(graph_id)

        _task_manager.complete_task(task_id, {
            "entity_count": len(entities),
            "topic_aware_count": sum(1 for e in entities if e.topic_aware),
            "audience_profile_count": sum(1 for e in entities if not e.topic_aware),
            "graph_id": graph_id,
            "graph_summary": summary,
        })

    except Exception as e:
        import traceback
        _task_manager.fail_task(task_id, f"{e}\n{traceback.format_exc()}")


@reality_bp.route('/world/status/<task_id>', methods=['GET'])
def world_build_status(task_id):
    """Check world building progress."""
    task = _task_manager.get_task(task_id)
    if not task:
        return jsonify({"error": "Task not found"}), 404
    return jsonify(task.to_dict())


@reality_bp.route('/world/review/<project_id>', methods=['GET'])
def review_world(project_id):
    """Get the entity pool for human review."""
    if project_id not in _projects:
        return jsonify({"error": "Project not found"}), 404

    project = _projects[project_id]
    entities = project.get("entities", [])

    return jsonify({
        "project_id": project_id,
        "phase": project["phase"],
        "entity_count": len(entities),
        "topic_aware_count": sum(1 for e in entities if e.topic_aware),
        "audience_profile_count": sum(1 for e in entities if not e.topic_aware),
        "entities": [e.to_dict() for e in entities],
        "graph_id": project.get("graph_id"),
    })


@reality_bp.route('/world/approve/<project_id>', methods=['POST'])
def approve_world(project_id):
    """User approves the entity pool (Human Review 1)."""
    if project_id not in _projects:
        return jsonify({"error": "Project not found"}), 404

    project = _projects[project_id]
    data = request.get_json() or {}
    feedback = data.get("feedback", "")

    project["phase"] = "world_approved"
    project["review_feedback"] = feedback

    return jsonify({
        "project_id": project_id,
        "phase": "world_approved",
        "message": "World approved. Ready for Existing Reality report generation.",
    })


@reality_bp.route('/reality/report', methods=['POST'])
def generate_reality_report():
    """Generate the Existing Reality report (Phase 1)."""
    data = request.get_json()
    project_id = data.get("project_id")

    if project_id not in _projects:
        return jsonify({"error": "Project not found"}), 404

    project = _projects[project_id]
    if not project.get("graph_id"):
        return jsonify({"error": "World must be built and approved first"}), 400

    task_id = _task_manager.create_task(
        task_type="reality_report",
        metadata={"project_id": project_id},
    )

    project["phase"] = "generating_reality_report"

    thread = threading.Thread(
        target=_reality_report_worker,
        args=(task_id, project_id),
        daemon=True,
    )
    thread.start()

    return jsonify({"task_id": task_id, "project_id": project_id})


def _reality_report_worker(task_id, project_id):
    """Background worker for Existing Reality report."""
    try:
        project = _projects[project_id]
        thesis = project["thesis"]

        _task_manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=5, message="Starting report...")

        run_focus_groups = Config.FOCUS_GROUPS_ENABLED
        if run_focus_groups and project.get("entities"):
            _task_manager.update_task(task_id, progress=10, message="Running focus groups...")
            fg_engine = FocusGroupEngine()
            fg_result = fg_engine.run_focus_group(
                entities=project["entities"],
                research_question=thesis.research_question,
                mode="reality",
            )
            project["focus_group_result"] = fg_result

            # Load transcripts into Zep
            _task_manager.update_task(task_id, progress=30, message="Loading focus group transcripts...")
            graph_builder = RealityGraphBuilder()
            fg_uuids = graph_builder.load_focus_group_transcripts(project["graph_id"], fg_result)
            graph_builder.wait_for_processing(fg_uuids, timeout=300)

        _task_manager.update_task(task_id, progress=40, message="Generating report from real data...")

        adapter = RealityReportAdapter(
            graph_id=project["graph_id"],
            simulation_id=project_id,
            research_question=thesis.research_question,
            mode="reality",
        )

        def progress_cb(msg, pct):
            _task_manager.update_task(task_id, progress=40 + int(pct * 55), message=msg)

        report_id = adapter.generate_report(progress_callback=progress_cb)
        project["reality_report_id"] = report_id
        project["phase"] = "reality_report_complete"

        _task_manager.complete_task(task_id, {"report_id": report_id})

    except Exception as e:
        import traceback
        _task_manager.fail_task(task_id, f"{e}\n{traceback.format_exc()}")


@reality_bp.route('/focus-group/run', methods=['POST'])
def run_focus_group():
    """Run focus groups independently (useful for testing)."""
    data = request.get_json()
    project_id = data.get("project_id")
    mode = data.get("mode", "reality")
    scenario = data.get("scenario", "")

    if project_id not in _projects:
        return jsonify({"error": "Project not found"}), 404

    project = _projects[project_id]
    entities = project.get("entities", [])
    if not entities:
        return jsonify({"error": "No entities available. Build world first."}), 400

    task_id = _task_manager.create_task(
        task_type="focus_group",
        metadata={"project_id": project_id, "mode": mode},
    )

    thread = threading.Thread(
        target=_focus_group_worker,
        args=(task_id, project_id, mode, scenario),
        daemon=True,
    )
    thread.start()

    return jsonify({"task_id": task_id})


def _focus_group_worker(task_id, project_id, mode, scenario):
    try:
        project = _projects[project_id]
        thesis = project["thesis"]

        _task_manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=10, message="Composing panels...")

        engine = FocusGroupEngine()
        result = engine.run_focus_group(
            entities=project["entities"],
            research_question=thesis.research_question,
            mode=mode,
            scenario_description=scenario,
        )

        project["focus_group_result"] = result

        # Load into Zep if graph exists
        if project.get("graph_id"):
            _task_manager.update_task(task_id, progress=80, message="Loading transcripts into Zep...")
            graph_builder = RealityGraphBuilder()
            fg_uuids = graph_builder.load_focus_group_transcripts(project["graph_id"], result)
            graph_builder.wait_for_processing(fg_uuids, timeout=300)

        _task_manager.complete_task(task_id, {
            "panel_count": len(result.panels),
            "total_messages": sum(len(p.messages) for p in result.panels),
        })

    except Exception as e:
        import traceback
        _task_manager.fail_task(task_id, f"{e}\n{traceback.format_exc()}")


@reality_bp.route('/scenario/inject', methods=['POST'])
def inject_scenario():
    """Define the future scenario for Phase 2 (Human Review 2)."""
    data = request.get_json()
    project_id = data.get("project_id")
    scenario = data.get("scenario", "")

    if project_id not in _projects:
        return jsonify({"error": "Project not found"}), 404

    if not scenario:
        return jsonify({"error": "Scenario description is required"}), 400

    project = _projects[project_id]
    project["scenario"] = scenario
    project["phase"] = "scenario_defined"

    return jsonify({
        "project_id": project_id,
        "phase": "scenario_defined",
        "message": "Scenario defined. Ready for Phase 2 simulation.",
    })


@reality_bp.route('/future/simulate', methods=['POST'])
def start_future_simulation():
    """Start Phase 2: Future simulation with awareness mechanics."""
    data = request.get_json()
    project_id = data.get("project_id")

    if project_id not in _projects:
        return jsonify({"error": "Project not found"}), 404

    project = _projects[project_id]
    if not project.get("scenario"):
        return jsonify({"error": "Scenario must be defined first"}), 400

    task_id = _task_manager.create_task(
        task_type="future_simulation",
        metadata={"project_id": project_id},
    )

    project["phase"] = "future_simulating"

    thread = threading.Thread(
        target=_future_simulation_worker,
        args=(task_id, project_id, data.get("max_rounds", 50)),
        daemon=True,
    )
    thread.start()

    return jsonify({"task_id": task_id, "project_id": project_id})


def _future_simulation_worker(task_id, project_id, max_rounds):
    """Background worker for Phase 2 simulation + report."""
    try:
        project = _projects[project_id]
        thesis = project["thesis"]

        _task_manager.update_task(task_id, status=TaskStatus.PROCESSING, progress=5, message="Converting entities to OASIS profiles...")

        bridge = PhaseBridge()
        oasis_profiles, awareness_profiles = bridge.convert_entities_to_profiles(
            project["entities"],
            scenario_description=project["scenario"],
        )
        awareness_config = bridge.generate_awareness_config(awareness_profiles)

        project["oasis_profiles"] = oasis_profiles
        project["awareness_config"] = awareness_config

        _task_manager.update_task(task_id, progress=15, message="Profiles created. Preparing OASIS simulation...")

        from ..services.simulation_config_generator import SimulationConfigGenerator
        from ..services.simulation_runner import SimulationRunner, RunnerStatus
        from ..services.oasis_profile_generator import OasisProfileGenerator
        from ..services.zep_entity_reader import EntityNode
        import time as _time

        simulation_id = f"sim_future_{project_id}"
        sim_base = os.path.join(os.path.dirname(__file__), '../../uploads/simulations')
        sim_dir = os.path.join(sim_base, simulation_id)
        os.makedirs(sim_dir, exist_ok=True)

        # Adapt profiles → EntityNode shims for config generator
        entity_nodes = []
        for p in oasis_profiles:
            node = EntityNode(
                uuid=p.source_entity_uuid or f"agent_{p.user_id}",
                name=p.name or p.user_name,
                labels=["Entity", "ScrapedEntity"],
                summary=p.persona[:500] if p.persona else p.bio,
                attributes={"username": p.user_name, "topics": p.interested_topics},
            )
            entity_nodes.append(node)

        config_gen = SimulationConfigGenerator()
        sim_params = config_gen.generate_config(
            simulation_id=simulation_id,
            project_id=project_id,
            graph_id=project["graph_id"],
            simulation_requirement=project["scenario"],
            document_text=project["scenario"],
            entities=entity_nodes,
            enable_twitter=True,
            enable_reddit=True,
        )

        config_path = os.path.join(sim_dir, "simulation_config.json")
        with open(config_path, "w") as f:
            f.write(sim_params.to_json())

        with open(os.path.join(sim_dir, "awareness_config.json"), "w") as f:
            json.dump(awareness_config, f, indent=2)

        profile_gen = OasisProfileGenerator()
        profile_gen.save_profiles(oasis_profiles, os.path.join(sim_dir, "reddit_profiles.json"), platform="reddit")
        profile_gen.save_profiles(oasis_profiles, os.path.join(sim_dir, "twitter_profiles.csv"), platform="twitter")

        with open(os.path.join(sim_dir, "state.json"), "w") as f:
            json.dump({"simulation_id": simulation_id, "project_id": project_id,
                        "graph_id": project["graph_id"], "status": "ready",
                        "enable_twitter": True, "enable_reddit": True}, f, indent=2)

        _task_manager.update_task(task_id, progress=25, message="Running OASIS simulation...")

        run_state = SimulationRunner.start_simulation(
            simulation_id=simulation_id, platform="parallel",
            max_rounds=max_rounds, enable_graph_memory_update=False,
        )

        while True:
            _time.sleep(10)
            state = SimulationRunner.get_run_state(simulation_id)
            if not state or state.runner_status in (RunnerStatus.COMPLETED, RunnerStatus.STOPPED, RunnerStatus.FAILED):
                break
            pct = min(45, 25 + int(state.current_round / max(state.total_rounds, 1) * 20))
            _task_manager.update_task(task_id, progress=pct,
                message=f"Simulating... round {state.current_round}/{state.total_rounds}")

        _task_manager.update_task(task_id, progress=50, message="Generating future prediction report...")

        run_focus_groups = Config.FOCUS_GROUPS_ENABLED
        if run_focus_groups and project.get("entities"):
            _task_manager.update_task(task_id, progress=55, message="Running future focus groups...")
            fg_engine = FocusGroupEngine()
            fg_result = fg_engine.run_focus_group(
                entities=project["entities"],
                research_question=thesis.research_question,
                mode="future",
                scenario_description=project["scenario"],
            )

            if project.get("graph_id"):
                graph_builder = RealityGraphBuilder()
                fg_uuids = graph_builder.load_focus_group_transcripts(project["graph_id"], fg_result)
                graph_builder.wait_for_processing(fg_uuids, timeout=300)

        _task_manager.update_task(task_id, progress=70, message="Generating report...")

        adapter = RealityReportAdapter(
            graph_id=project["graph_id"],
            simulation_id=project_id,
            research_question=f"{thesis.research_question}\n\nScenario: {project['scenario']}",
            mode="future",
        )

        report_id = adapter.generate_report()
        project["future_report_id"] = report_id
        project["phase"] = "future_report_complete"

        _task_manager.complete_task(task_id, {"report_id": report_id})

    except Exception as e:
        import traceback
        _task_manager.fail_task(task_id, f"{e}\n{traceback.format_exc()}")


@reality_bp.route('/project/<project_id>', methods=['GET'])
def get_project(project_id):
    """Get full project state."""
    if project_id not in _projects:
        return jsonify({"error": "Project not found"}), 404

    project = _projects[project_id]
    thesis = project["thesis"]

    return jsonify({
        "id": project_id,
        "phase": project["phase"],
        "research_question": thesis.research_question,
        "graph_id": project.get("graph_id"),
        "entity_count": len(project.get("entities", [])),
        "reality_report_id": project.get("reality_report_id"),
        "future_report_id": project.get("future_report_id"),
        "scenario": project.get("scenario"),
    })


@reality_bp.route('/scraper/status', methods=['GET'])
def scraper_status():
    """Check which scrapers are configured and available."""
    scraper = SocialScraper()
    return jsonify(scraper.status)
