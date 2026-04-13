"""
Phase 2 E2E test: Scenario injection → OASIS config generation → Simulation run.

Exercises the full Phase 2 pipeline step by step:
  Step 1: Load Phase 1 entities + inject scenario
  Step 2: PhaseBridge → OASIS profiles + awareness_config
  Step 3: Generate simulation_config.json (adapted for real entities)
  Step 4: Run OASIS simulation
  Step 5: Generate Future Prediction Report
"""

import os
import sys
import json
import time
import logging

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(levelname)s: %(message)s", datefmt="%H:%M:%S")
logger = logging.getLogger("e2e_phase2")

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "e2e_output")
GRAPH_ID = "reality_67e962167b0c"

SCENARIO_TEXT = """\
Google AI Studio Mobile — a mobile application extending Google AI Studio to iOS and Android — \
launches in the United States in July 2026. It offers prompt-to-app generation using natural \
language, an AI coding agent that maintains deep project context, Firebase integration with \
auto-provisioned databases, one-tap deploy, and cross-device sync. The free tier provides \
100 daily Gemini 2.5 Pro requests. Paid usage starts at $5 in prepaid credits. \
The app targets non-technical entrepreneurs, AI hobbyists, educators, and students — \
enabling them to build full-stack web apps entirely from a phone.
"""


# ── Step 1: Load Phase 1 entities ──────────────────────────────────────────────

def step1_load_entities():
    """Load the entities we scraped + enriched in Phase 1."""
    logger.info("=" * 60)
    logger.info("STEP 1: Loading Phase 1 entities")

    # Prefer step4 (full 65 entities) over step5 (only 3 enriched)
    entities_path = os.path.join(OUTPUT_DIR, "step4_entities.json")

    with open(entities_path) as f:
        raw = json.load(f)

    from app.services.entity_extractor import ExtractedEntity

    entities = []
    for d in raw:
        e = ExtractedEntity(
            username=d["username"],
            display_name=d.get("display_name", ""),
            platform=d.get("platform", "x"),
            topic_aware=d.get("topic_aware", True),
        )
        e.personality_summary = d.get("personality_summary", "")
        e.relevance_reason = d.get("relevance_reason", "")
        e.sentiment_summary = d.get("sentiment_summary", "")
        e.engagement_pattern = d.get("engagement_pattern", "")
        e.core_topics = d.get("core_topics", [])
        e.communication_style = d.get("communication_style", "")
        e.openness_to_new = d.get("openness_to_new", "neutral")
        entities.append(e)

    logger.info(f"  Loaded {len(entities)} entities")
    logger.info(f"  Topic-aware: {sum(1 for e in entities if e.topic_aware)}")
    logger.info(f"  Audience-profile: {sum(1 for e in entities if not e.topic_aware)}")
    return entities


# ── Step 2: PhaseBridge → OASIS profiles + awareness ─────────────────────────

def step2_bridge(entities):
    """Convert entities to OASIS profiles with awareness probabilities."""
    logger.info("=" * 60)
    logger.info("STEP 2: PhaseBridge → OASIS profiles + awareness_config")

    from app.services.phase_bridge import PhaseBridge

    bridge = PhaseBridge()
    oasis_profiles, awareness_profiles = bridge.convert_entities_to_profiles(
        entities, scenario_description=SCENARIO_TEXT,
    )
    awareness_config = bridge.generate_awareness_config(awareness_profiles)

    logger.info(f"  OASIS profiles: {len(oasis_profiles)}")
    logger.info(f"  Awareness config entries: {len(awareness_config)}")

    # Quick sanity: topic-aware entities should have higher awareness probability
    aware_probs = [awareness_config[str(i)]["awareness_probability"]
                   for i, e in enumerate(entities) if e.topic_aware]
    unaware_probs = [awareness_config[str(i)]["awareness_probability"]
                     for i, e in enumerate(entities) if not e.topic_aware]
    if aware_probs:
        logger.info(f"  Avg awareness (topic-aware): {sum(aware_probs)/len(aware_probs):.2f}")
    if unaware_probs:
        logger.info(f"  Avg awareness (audience-profile): {sum(unaware_probs)/len(unaware_probs):.2f}")

    return oasis_profiles, awareness_profiles, awareness_config


# ── Step 3: Generate simulation_config.json ──────────────────────────────────

def step3_generate_config(oasis_profiles, awareness_config, sim_dir):
    """
    Generate simulation_config.json using the existing SimulationConfigGenerator,
    adapted to work with OasisAgentProfile objects instead of Zep EntityNodes.
    """
    logger.info("=" * 60)
    logger.info("STEP 3: Generating simulation_config.json")

    from app.services.simulation_config_generator import SimulationConfigGenerator
    from app.services.zep_entity_reader import EntityNode
    from app.services.oasis_profile_generator import OasisProfileGenerator

    # Adapt OasisAgentProfiles → EntityNode-like objects for the config generator
    entity_nodes = []
    for p in oasis_profiles:
        node = EntityNode(
            uuid=p.source_entity_uuid or f"agent_{p.user_id}",
            name=p.name or p.user_name,
            labels=["Entity", "ScrapedEntity"],
            summary=p.persona[:500] if p.persona else p.bio,
            attributes={
                "platform": "x" if "x:" in (p.source_entity_uuid or "") else "reddit",
                "username": p.user_name,
                "topics": p.interested_topics,
            },
        )
        entity_nodes.append(node)

    logger.info(f"  Adapted {len(entity_nodes)} profiles → EntityNode shims")

    simulation_id = f"sim_phase2_{int(time.time())}"

    config_gen = SimulationConfigGenerator()

    def progress_cb(step, total, msg):
        logger.info(f"  Config gen [{step}/{total}]: {msg}")

    sim_params = config_gen.generate_config(
        simulation_id=simulation_id,
        project_id="realityfish_phase2",
        graph_id=GRAPH_ID,
        simulation_requirement=SCENARIO_TEXT,
        document_text=SCENARIO_TEXT,
        entities=entity_nodes,
        enable_twitter=True,
        enable_reddit=True,
        progress_callback=progress_cb,
    )

    # Save config
    config_path = os.path.join(sim_dir, "simulation_config.json")
    with open(config_path, "w") as f:
        f.write(sim_params.to_json())
    logger.info(f"  Saved simulation_config.json ({len(sim_params.agent_configs)} agents)")

    # Save awareness_config alongside
    awareness_path = os.path.join(sim_dir, "awareness_config.json")
    with open(awareness_path, "w") as f:
        json.dump(awareness_config, f, indent=2)
    logger.info(f"  Saved awareness_config.json")

    # Save profiles
    profile_gen = OasisProfileGenerator()
    reddit_path = os.path.join(sim_dir, "reddit_profiles.json")
    profile_gen.save_profiles(oasis_profiles, reddit_path, platform="reddit")
    logger.info(f"  Saved reddit_profiles.json")

    twitter_path = os.path.join(sim_dir, "twitter_profiles.csv")
    profile_gen.save_profiles(oasis_profiles, twitter_path, platform="twitter")
    logger.info(f"  Saved twitter_profiles.csv")

    # Summary
    tc = sim_params.time_config
    logger.info(f"  Simulation: {tc.total_simulation_hours}h, {tc.minutes_per_round}min/round")
    logger.info(f"  Agents/hour: {tc.agents_per_hour_min}-{tc.agents_per_hour_max}")
    logger.info(f"  Hot topics: {sim_params.event_config.hot_topics[:5]}")
    logger.info(f"  Initial posts: {len(sim_params.event_config.initial_posts)}")

    return simulation_id, sim_params


# ── Step 4: Run OASIS simulation ─────────────────────────────────────────────

def step4_run_simulation(simulation_id, sim_dir, max_rounds=10):
    """Run the OASIS simulation via SimulationRunner."""
    logger.info("=" * 60)
    logger.info(f"STEP 4: Running OASIS simulation (max_rounds={max_rounds})")

    from app.services.simulation_runner import SimulationRunner, RunnerStatus

    # Save a state.json so SimulationManager recognizes this sim
    state_path = os.path.join(sim_dir, "state.json")
    with open(state_path, "w") as f:
        json.dump({
            "simulation_id": simulation_id,
            "project_id": "realityfish_phase2",
            "graph_id": GRAPH_ID,
            "status": "ready",
            "enable_twitter": True,
            "enable_reddit": True,
        }, f, indent=2)

    run_state = SimulationRunner.start_simulation(
        simulation_id=simulation_id,
        platform="parallel",
        max_rounds=max_rounds,
        enable_graph_memory_update=False,
    )

    logger.info(f"  Started: pid={run_state.process_pid}, total_rounds={run_state.total_rounds}")

    # Poll until done
    poll_interval = 10
    max_wait = 600  # 10 min
    elapsed = 0

    while elapsed < max_wait:
        time.sleep(poll_interval)
        elapsed += poll_interval

        state = SimulationRunner.get_run_state(simulation_id)
        if not state:
            logger.warning("  Lost run state!")
            break

        logger.info(
            f"  [{elapsed}s] round={state.current_round}/{state.total_rounds} "
            f"tw_actions={state.twitter_actions_count} rd_actions={state.reddit_actions_count} "
            f"status={state.runner_status.value}"
        )

        if state.runner_status in (RunnerStatus.COMPLETED, RunnerStatus.STOPPED, RunnerStatus.FAILED):
            break

    final = SimulationRunner.get_run_state(simulation_id)
    logger.info(f"  Final status: {final.runner_status.value}")
    logger.info(f"  Total actions: tw={final.twitter_actions_count}, rd={final.reddit_actions_count}")

    if final.error:
        logger.error(f"  Error: {final.error[:500]}")

    return final


# ── Step 5: Generate Future Prediction Report ────────────────────────────────

def step5_generate_report():
    """Generate the Future Prediction report using the Zep graph + simulation data."""
    logger.info("=" * 60)
    logger.info("STEP 5: Generating Future Prediction Report")

    from app.services.reality_report_adapter import RealityReportAdapter

    research_q = (
        "How will non-technical entrepreneurs and AI hobbyists in the US "
        "react to the launch of Google AI Studio Mobile?\n\n"
        f"Scenario: {SCENARIO_TEXT}"
    )

    adapter = RealityReportAdapter(
        graph_id=GRAPH_ID,
        simulation_id="realityfish_phase2",
        research_question=research_q,
        mode="future",
    )

    def progress_cb(stage, progress, message):
        logger.info(f"  Report [{progress}%] [{stage}] {message}")

    report_id = adapter.generate_report(progress_callback=progress_cb)
    logger.info(f"  Report generated: {report_id}")

    report_path = os.path.join(
        os.path.dirname(__file__), "..",
        "uploads", "reports", report_id, "full_report.md"
    )
    if os.path.exists(report_path):
        with open(report_path) as f:
            content = f.read()
        logger.info(f"  Report length: {len(content)} chars, {len(content.split())} words")

        # Save a copy to e2e_output
        out_path = os.path.join(OUTPUT_DIR, "future_report.md")
        with open(out_path, "w") as f:
            f.write(content)
        logger.info(f"  Saved copy to {out_path}")

    return report_id


# ── Main ─────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Phase 2 E2E test")
    parser.add_argument("--step", type=int, default=0, help="Run only this step (0=all)")
    parser.add_argument("--max-rounds", type=int, default=10, help="Max simulation rounds")
    args = parser.parse_args()

    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Set up simulation directory
    sim_base = os.path.join(os.path.dirname(__file__), "..", "uploads", "simulations")
    os.makedirs(sim_base, exist_ok=True)

    run_all = args.step == 0

    entities = None
    oasis_profiles = None
    awareness_config = None
    simulation_id = None
    sim_dir = None

    if run_all or args.step == 1:
        entities = step1_load_entities()

    if run_all or args.step == 2:
        if entities is None:
            entities = step1_load_entities()
        oasis_profiles, awareness_profiles, awareness_config = step2_bridge(entities)

    if run_all or args.step == 3:
        if oasis_profiles is None:
            entities = step1_load_entities()
            oasis_profiles, awareness_profiles, awareness_config = step2_bridge(entities)

        # Create temp sim dir for config generation
        tmp_sim_id = f"sim_phase2_{int(time.time())}"
        sim_dir = os.path.join(sim_base, tmp_sim_id)
        os.makedirs(sim_dir, exist_ok=True)

        simulation_id, sim_params = step3_generate_config(oasis_profiles, awareness_config, sim_dir)
        # The actual sim_dir might differ — update
        actual_dir = os.path.join(sim_base, simulation_id)
        if actual_dir != sim_dir:
            import shutil
            if os.path.exists(actual_dir):
                shutil.rmtree(actual_dir)
            os.rename(sim_dir, actual_dir)
            sim_dir = actual_dir

    if run_all or args.step == 4:
        if simulation_id is None or sim_dir is None:
            # Try to find the most recent sim dir
            sim_dirs = sorted(
                [d for d in os.listdir(sim_base) if d.startswith("sim_phase2_")],
                reverse=True,
            )
            if sim_dirs:
                simulation_id = sim_dirs[0]
                sim_dir = os.path.join(sim_base, simulation_id)
                logger.info(f"  Using existing simulation: {simulation_id}")
            else:
                logger.error("Must run steps 1-3 first (or run all)")
                sys.exit(1)
        step4_run_simulation(simulation_id, sim_dir, max_rounds=args.max_rounds)

    if run_all or args.step == 5:
        step5_generate_report()

    logger.info("=" * 60)
    logger.info("PHASE 2 E2E TEST COMPLETE")
    logger.info("=" * 60)
