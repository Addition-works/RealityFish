"""
End-to-end pipeline test for RealityFish.

Runs each step sequentially, validating outputs at each stage.
Writes detailed logs to backend/tests/e2e_output/ for inspection.

Usage:
    cd backend && uv run python tests/e2e_pipeline_test.py
"""

import sys
import os
import json
import time
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'e2e_output')
os.makedirs(OUTPUT_DIR, exist_ok=True)

LOG_FILE = os.path.join(OUTPUT_DIR, 'e2e_log.txt')


def log(msg, also_print=True):
    """Log to file and optionally print."""
    timestamp = time.strftime('%H:%M:%S')
    line = f"[{timestamp}] {msg}"
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')
    if also_print:
        print(line)


def save_json(filename, data):
    """Save data as JSON for inspection."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, 'w') as f:
        json.dump(data, f, indent=2, default=str)
    log(f"  Saved: {filename}")


def save_text(filename, text):
    """Save text for inspection."""
    path = os.path.join(OUTPUT_DIR, filename)
    with open(path, 'w') as f:
        f.write(text)
    log(f"  Saved: {filename}")


def assert_check(condition, msg):
    """Assert with logging."""
    if not condition:
        log(f"  FAIL: {msg}")
        raise AssertionError(msg)
    log(f"  OK: {msg}")


# ═══════════════════════════════════════════════════════════
# STEP 1: Thesis Parsing
# ═══════════════════════════════════════════════════════════

def step1_parse_thesis():
    log("\n" + "=" * 60)
    log("STEP 1: THESIS PARSING")
    log("=" * 60)

    from app.services.thesis_parser import parse_thesis

    thesis_path = os.path.join(os.path.dirname(__file__), 'test_thesis_e2e.md')
    with open(thesis_path) as f:
        text = f.read()

    thesis = parse_thesis(text)
    errors = thesis.validate()

    assert_check(len(errors) == 0, f"Thesis validates without errors (got: {errors})")
    assert_check(len(thesis.research_question) > 20, f"Research question is substantive ({len(thesis.research_question)} chars)")
    assert_check(len(thesis.scope.keywords) >= 3, f"At least 3 keywords ({thesis.scope.keywords})")
    assert_check(thesis.scope.platforms == ['x', 'reddit'], f"Platforms are x and reddit ({thesis.scope.platforms})")
    assert_check(len(thesis.audience_profiles) == 2, f"2 audience profiles ({len(thesis.audience_profiles)})")
    assert_check(thesis.scope.time_window_days == 14, f"Time window is 14 days")
    assert_check(len(thesis.known_context) > 50, f"Known context is present ({len(thesis.known_context)} chars)")

    save_json('step1_thesis.json', {
        'research_question': thesis.research_question,
        'scope': {
            'platforms': thesis.scope.platforms,
            'keywords': thesis.scope.keywords,
            'geography': thesis.scope.geography,
            'time_window_days': thesis.scope.time_window_days,
        },
        'audience_profiles': [
            {'name': a.name, 'behaviors': a.behaviors, 'interests': a.interests, 'demographics': a.demographics}
            for a in thesis.audience_profiles
        ],
        'known_context': thesis.known_context,
    })

    log("STEP 1 PASSED")
    return thesis


# ═══════════════════════════════════════════════════════════
# STEP 2: Search Strategy Generation (LLM call)
# ═══════════════════════════════════════════════════════════

def step2_search_strategy(thesis):
    log("\n" + "=" * 60)
    log("STEP 2: SEARCH STRATEGY GENERATION (LLM)")
    log("=" * 60)

    from app.services.world_builder import WorldBuilder
    from app.utils.llm_client import LLMClient

    llm = LLMClient()
    builder = WorldBuilder(llm_client=llm)

    log("  Calling LLM to generate search queries...")
    t0 = time.time()
    strategy = builder.generate_search_strategy(thesis)
    elapsed = time.time() - t0
    log(f"  LLM responded in {elapsed:.1f}s")

    assert_check(len(strategy.topic_aware_queries) >= 3, f"At least 3 topic-aware queries ({len(strategy.topic_aware_queries)})")
    assert_check(len(strategy.audience_profile_queries) >= 1, f"At least 1 audience profile query group ({len(strategy.audience_profile_queries)})")

    all_queries = strategy.all_queries
    assert_check(len(all_queries) >= 5, f"At least 5 total queries ({len(all_queries)})")

    # Validate thesis keywords are included
    for kw in thesis.scope.keywords:
        found = any(kw.lower() in q[0].lower() for q in all_queries)
        if not found:
            log(f"  WARN: Thesis keyword '{kw}' not directly in queries (may be paraphrased)")

    save_json('step2_strategy.json', {
        'topic_aware_queries': strategy.topic_aware_queries,
        'audience_profile_queries': strategy.audience_profile_queries,
        'all_queries': [(q, t) for q, t in all_queries],
    })

    log(f"  Topic-aware queries: {strategy.topic_aware_queries}")
    for group in strategy.audience_profile_queries:
        log(f"  Audience '{group.get('audience', '?')}': {group.get('queries', [])}")

    log("STEP 2 PASSED")
    return strategy, builder


# ═══════════════════════════════════════════════════════════
# STEP 3: Social Media Scraping
# ═══════════════════════════════════════════════════════════

def step3_scraping(thesis, strategy, builder):
    log("\n" + "=" * 60)
    log("STEP 3: SOCIAL MEDIA SCRAPING")
    log("=" * 60)

    # Check scraper availability
    log(f"  X (Apify) available: {builder.scraper.x.available}")
    log(f"  Reddit (PRAW) available: {builder.scraper.reddit.available}")

    assert_check(builder.scraper.x.available, "Apify token is configured")
    assert_check(builder.scraper.reddit.available, "Reddit credentials are configured")

    # We'll scrape a subset of queries to save time/cost
    # Pick first 2 topic-aware + first audience group
    limited_queries = strategy.topic_aware_queries[:2]
    if strategy.audience_profile_queries:
        audience_q = strategy.audience_profile_queries[0].get('queries', [])[:2]
        limited_queries += audience_q

    log(f"  Scraping with {len(limited_queries)} queries (limited for testing): {limited_queries}")

    all_results = []
    for query in limited_queries:
        log(f"  --- Scraping '{query}' ---")

        # X search
        log(f"    X keyword search...")
        t0 = time.time()
        x_result = builder.scraper.x.search_keyword(query, max_results=5, recency_days=14)
        elapsed = time.time() - t0
        if x_result.error:
            log(f"    X ERROR: {x_result.error}")
        else:
            log(f"    X: {len(x_result.posts)} tweets in {elapsed:.1f}s")
            all_results.append(x_result)

        # Reddit search
        log(f"    Reddit keyword search...")
        t0 = time.time()
        reddit_result = builder.scraper.reddit.search_keyword(query, max_posts_per_sub=3, time_filter='week')
        elapsed = time.time() - t0
        if reddit_result.error:
            log(f"    Reddit ERROR: {reddit_result.error}")
        else:
            log(f"    Reddit: {len(reddit_result.posts)} posts in {elapsed:.1f}s")
            all_results.append(reddit_result)

    total_posts = sum(len(r.posts) for r in all_results)
    log(f"  Total scraped: {total_posts} posts from {len(all_results)} successful queries")
    assert_check(total_posts >= 1, f"At least 1 post scraped ({total_posts})")

    # Validate post data integrity
    sample_posts = []
    for r in all_results:
        for p in r.posts[:2]:
            assert_check(p.platform in ('x', 'reddit'), f"Platform is valid: {p.platform}")
            assert_check(len(p.author_username) > 0, f"Author is non-empty: @{p.author_username}")
            assert_check(len(p.text) > 0, f"Post text is non-empty ({len(p.text)} chars)")
            sample_posts.append({
                'platform': p.platform,
                'post_id': p.post_id,
                'author': p.author_username,
                'text': p.text[:200],
                'likes': p.likes,
                'replies': p.replies,
            })

    save_json('step3_scrape_results.json', {
        'total_posts': total_posts,
        'results_count': len(all_results),
        'sample_posts': sample_posts,
    })

    log("STEP 3 PASSED")
    return all_results


# ═══════════════════════════════════════════════════════════
# STEP 4: Entity Extraction (LLM call)
# ═══════════════════════════════════════════════════════════

def step4_entity_extraction(thesis, all_results, builder):
    log("\n" + "=" * 60)
    log("STEP 4: ENTITY EXTRACTION (LLM)")
    log("=" * 60)

    log(f"  Extracting entities from {sum(len(r.posts) for r in all_results)} posts...")
    t0 = time.time()
    entities = builder.extractor.extract_entities(all_results, thesis.research_question)
    elapsed = time.time() - t0
    log(f"  Extracted {len(entities)} entities in {elapsed:.1f}s")

    assert_check(len(entities) >= 1, f"At least 1 entity extracted ({len(entities)})")

    # Validate entity data
    for e in entities:
        assert_check(len(e.username) > 0, f"Entity has username: @{e.username}")
        assert_check(e.platform in ('x', 'reddit'), f"Entity platform valid: {e.platform}")
        assert_check(isinstance(e.topic_aware, bool), f"topic_aware is bool: {e.topic_aware}")

    # Check deduplication
    keys = [e.entity_key for e in entities]
    assert_check(len(keys) == len(set(keys)), f"No duplicate entity keys")

    topic_count = sum(1 for e in entities if e.topic_aware)
    audience_count = sum(1 for e in entities if not e.topic_aware)
    log(f"  Topic-aware: {topic_count}, Audience-profile: {audience_count}")

    save_json('step4_entities.json', [
        {
            'username': e.username,
            'platform': e.platform,
            'topic_aware': e.topic_aware,
            'relevance_reason': e.relevance_reason,
            'sentiment_summary': e.sentiment_summary,
            'post_count': len(e.posts),
        }
        for e in entities
    ])

    log("STEP 4 PASSED")
    return entities


# ═══════════════════════════════════════════════════════════
# STEP 5: Entity Enrichment (LLM calls)
# ═══════════════════════════════════════════════════════════

def step5_enrichment(entities, builder):
    log("\n" + "=" * 60)
    log("STEP 5: ENTITY ENRICHMENT (LLM)")
    log("=" * 60)

    # Enrich top 3 entities to save time
    to_enrich = [e for e in entities if len(e.posts) > 0][:3]
    log(f"  Enriching {len(to_enrich)} entities (limited for testing)...")

    for e in to_enrich:
        log(f"  Enriching @{e.username} ({e.platform}, {len(e.posts)} posts)...")
        t0 = time.time()
        builder.extractor.enrich_entity(e)
        elapsed = time.time() - t0
        log(f"    Done in {elapsed:.1f}s")
        log(f"    Style: {e.communication_style}")
        log(f"    Topics: {e.core_topics}")
        log(f"    Openness: {e.openness_to_new}")
        log(f"    Summary: {e.personality_summary[:100] if e.personality_summary else 'N/A'}")

        if e.personality_summary:
            assert_check(len(e.personality_summary) > 10, f"Personality summary is substantive")
            assert_check(len(e.core_topics) >= 1, f"At least 1 core topic")
            assert_check(e.openness_to_new in ('eager', 'curious', 'neutral', 'skeptical', 'resistant'),
                        f"Openness is valid: {e.openness_to_new}")

    save_json('step5_enriched_entities.json', [e.to_dict() for e in to_enrich])

    log("STEP 5 PASSED")
    return entities


# ═══════════════════════════════════════════════════════════
# STEP 6: Zep Graph Loading
# ═══════════════════════════════════════════════════════════

def step6_zep_loading(entities):
    log("\n" + "=" * 60)
    log("STEP 6: ZEP GRAPH LOADING")
    log("=" * 60)

    from app.services.reality_graph_builder import RealityGraphBuilder

    graph_builder = RealityGraphBuilder()

    # Test entity formatting
    log("  Testing entity formatting...")
    for e in entities[:2]:
        text = graph_builder._format_entity_as_episode(e)
        assert_check(len(text) > 50, f"Episode text is substantive ({len(text)} chars)")
        assert_check(f"@{e.username}" in text, f"Username in episode text")
        log(f"    @{e.username}: {len(text)} chars")

    # Create graph
    log("  Creating Zep graph...")
    t0 = time.time()
    graph_id = graph_builder.create_graph("E2E Test: Mobile Vibe Coding")
    elapsed = time.time() - t0
    log(f"  Graph created: {graph_id} in {elapsed:.1f}s")
    assert_check(graph_id.startswith('reality_'), f"Graph ID format correct: {graph_id}")

    # Load entities
    log(f"  Loading {len(entities)} entities into graph...")
    t0 = time.time()
    episode_uuids = graph_builder.load_entities(graph_id, entities, batch_size=3)
    elapsed = time.time() - t0
    log(f"  Loaded {len(episode_uuids)} episodes in {elapsed:.1f}s")
    assert_check(len(episode_uuids) >= 1, f"At least 1 episode created")

    # Wait for processing
    log("  Waiting for Zep to process episodes...")
    t0 = time.time()
    graph_builder.wait_for_processing(episode_uuids, timeout=120,
        progress_callback=lambda msg, pct: log(f"    {msg}"))
    elapsed = time.time() - t0
    log(f"  Processing complete in {elapsed:.1f}s")

    # Get summary
    log("  Getting graph summary...")
    summary = graph_builder.get_graph_summary(graph_id)
    log(f"  Nodes: {summary['node_count']}, Edges: {summary['edge_count']}")
    log(f"  Entity types: {summary['entity_types']}")

    save_json('step6_graph_summary.json', summary)

    log("STEP 6 PASSED")
    return graph_id, graph_builder


# ═══════════════════════════════════════════════════════════
# STEP 7: Focus Groups (LLM calls)
# ═══════════════════════════════════════════════════════════

def step7_focus_groups(entities, thesis):
    log("\n" + "=" * 60)
    log("STEP 7: FOCUS GROUPS")
    log("=" * 60)

    from app.services.focus_group_engine import FocusGroupEngine

    engine = FocusGroupEngine()

    # Test panel composition
    panels = engine.compose_panels(entities, panel_size=3, max_panels=1)
    assert_check(len(panels) >= 1, f"At least 1 panel composed ({len(panels)})")
    log(f"  Composed {len(panels)} panel(s)")

    panel = panels[0]
    log(f"  Panel 1: {len(panel)} participants: {[e.username for e in panel]}")

    # Run mini focus group (2 rounds to save time)
    log("  Running focus group (2 rounds, 1 panel)...")
    t0 = time.time()
    result = engine.run_focus_group(
        entities=entities,
        research_question=thesis.research_question,
        mode="reality",
        num_rounds=2,
        panel_size=3,
        max_panels=1,
    )
    elapsed = time.time() - t0
    log(f"  Focus group complete in {elapsed:.1f}s")

    assert_check(len(result.panels) >= 1, f"At least 1 panel in result")
    panel = result.panels[0]
    assert_check(len(panel.messages) >= 3, f"At least 3 messages (moderator + responses)")

    # Validate transcript
    transcript = panel.transcript_text
    assert_check("MODERATOR" in transcript, "Moderator appears in transcript")
    assert_check(len(transcript) > 200, f"Transcript is substantive ({len(transcript)} chars)")

    save_text('step7_focus_group_transcript.md', result.full_transcript)
    log(f"  Transcript length: {len(transcript)} chars")
    log(f"  Messages: {len(panel.messages)}")

    # Log first few messages
    for msg in panel.messages[:5]:
        speaker = "MODERATOR" if msg.role == "moderator" else f"@{msg.role}"
        log(f"    [{speaker}]: {msg.content[:100]}...")

    log("STEP 7 PASSED")
    return result


# ═══════════════════════════════════════════════════════════
# STEP 8: Focus Group Transcript → Zep
# ═══════════════════════════════════════════════════════════

def step8_fg_to_zep(graph_id, graph_builder, fg_result):
    log("\n" + "=" * 60)
    log("STEP 8: FOCUS GROUP TRANSCRIPTS → ZEP")
    log("=" * 60)

    log(f"  Loading {len(fg_result.panels)} focus group transcripts into graph {graph_id}...")
    t0 = time.time()
    fg_uuids = graph_builder.load_focus_group_transcripts(graph_id, fg_result)
    elapsed = time.time() - t0
    log(f"  Loaded {len(fg_uuids)} episodes in {elapsed:.1f}s")

    log("  Waiting for Zep to process...")
    graph_builder.wait_for_processing(fg_uuids, timeout=120,
        progress_callback=lambda msg, pct: log(f"    {msg}"))

    summary = graph_builder.get_graph_summary(graph_id)
    log(f"  Updated graph — Nodes: {summary['node_count']}, Edges: {summary['edge_count']}")

    save_json('step8_graph_after_fg.json', summary)
    log("STEP 8 PASSED")
    return summary


# ═══════════════════════════════════════════════════════════
# STEP 9: Phase Bridge — Awareness Profiles
# ═══════════════════════════════════════════════════════════

def step9_phase_bridge(entities):
    log("\n" + "=" * 60)
    log("STEP 9: PHASE BRIDGE — AWARENESS PROFILES")
    log("=" * 60)

    from app.services.phase_bridge import PhaseBridge

    bridge = PhaseBridge()
    oasis_profiles, awareness_profiles = bridge.convert_entities_to_profiles(entities)

    assert_check(len(oasis_profiles) == len(entities), f"1 OASIS profile per entity")
    assert_check(len(awareness_profiles) == len(entities), f"1 awareness profile per entity")

    for i, (op, ap) in enumerate(zip(oasis_profiles, awareness_profiles)):
        log(f"  @{op.user_name}: awareness={ap.awareness_probability:.2f} caring={ap.caring_probability:.2f} "
            f"engagement={ap.engagement_probability:.2f} topic_aware={ap.topic_aware}")
        assert_check(0.05 <= ap.awareness_probability <= 0.95, "Awareness in range")
        assert_check(0.10 <= ap.caring_probability <= 0.95, "Caring in range")
        assert_check(len(op.persona) > 20, f"Persona is substantive ({len(op.persona)} chars)")

    # Verify topic-aware entities have higher awareness
    aware_probs = [ap.awareness_probability for ap in awareness_profiles if ap.topic_aware]
    audience_probs = [ap.awareness_probability for ap in awareness_profiles if not ap.topic_aware]
    if aware_probs and audience_probs:
        avg_aware = sum(aware_probs) / len(aware_probs)
        avg_audience = sum(audience_probs) / len(audience_probs)
        log(f"  Avg awareness (topic-aware): {avg_aware:.2f}")
        log(f"  Avg awareness (audience-profile): {avg_audience:.2f}")
        assert_check(avg_aware > avg_audience, "Topic-aware entities have higher awareness on average")

    awareness_config = bridge.generate_awareness_config(awareness_profiles)
    save_json('step9_awareness_config.json', awareness_config)
    save_json('step9_oasis_profiles.json', [op.to_dict() for op in oasis_profiles])

    log("STEP 9 PASSED")


# ═══════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════

def main():
    # Clear previous log
    with open(LOG_FILE, 'w') as f:
        f.write("")

    log("=" * 60)
    log("REALITYFISH END-TO-END PIPELINE TEST")
    log(f"Started at {time.strftime('%Y-%m-%d %H:%M:%S')}")
    log("=" * 60)

    t_start = time.time()
    passed = []
    failed = []

    steps = [
        ("Step 1: Thesis Parsing", lambda: step1_parse_thesis()),
        ("Step 2: Search Strategy", lambda: None),  # placeholder, filled below
        ("Step 3: Scraping", lambda: None),
        ("Step 4: Entity Extraction", lambda: None),
        ("Step 5: Entity Enrichment", lambda: None),
        ("Step 6: Zep Graph Loading", lambda: None),
        ("Step 7: Focus Groups", lambda: None),
        ("Step 8: FG → Zep", lambda: None),
        ("Step 9: Phase Bridge", lambda: None),
    ]

    # Run step by step, passing data between steps
    try:
        thesis = step1_parse_thesis()
        passed.append("Step 1")
    except Exception as e:
        log(f"\nFATAL: Step 1 failed: {e}\n{traceback.format_exc()}")
        failed.append("Step 1")
        return

    try:
        strategy, builder = step2_search_strategy(thesis)
        passed.append("Step 2")
    except Exception as e:
        log(f"\nFATAL: Step 2 failed: {e}\n{traceback.format_exc()}")
        failed.append("Step 2")
        return

    try:
        scrape_results = step3_scraping(thesis, strategy, builder)
        passed.append("Step 3")
    except Exception as e:
        log(f"\nFATAL: Step 3 failed: {e}\n{traceback.format_exc()}")
        failed.append("Step 3")
        return

    try:
        entities = step4_entity_extraction(thesis, scrape_results, builder)
        passed.append("Step 4")
    except Exception as e:
        log(f"\nFATAL: Step 4 failed: {e}\n{traceback.format_exc()}")
        failed.append("Step 4")
        return

    try:
        entities = step5_enrichment(entities, builder)
        passed.append("Step 5")
    except Exception as e:
        log(f"\nFATAL: Step 5 failed: {e}\n{traceback.format_exc()}")
        failed.append("Step 5")
        return

    try:
        graph_id, graph_builder = step6_zep_loading(entities)
        passed.append("Step 6")
    except Exception as e:
        log(f"\nFATAL: Step 6 failed: {e}\n{traceback.format_exc()}")
        failed.append("Step 6")
        # Continue to later steps if possible
        graph_id = None
        graph_builder = None

    try:
        fg_result = step7_focus_groups(entities, thesis)
        passed.append("Step 7")
    except Exception as e:
        log(f"\nFATAL: Step 7 failed: {e}\n{traceback.format_exc()}")
        failed.append("Step 7")
        fg_result = None

    if graph_id and graph_builder and fg_result:
        try:
            step8_fg_to_zep(graph_id, graph_builder, fg_result)
            passed.append("Step 8")
        except Exception as e:
            log(f"\nFATAL: Step 8 failed: {e}\n{traceback.format_exc()}")
            failed.append("Step 8")
    else:
        log("\nSKIPPED: Step 8 (missing graph or focus group data)")

    try:
        step9_phase_bridge(entities)
        passed.append("Step 9")
    except Exception as e:
        log(f"\nFATAL: Step 9 failed: {e}\n{traceback.format_exc()}")
        failed.append("Step 9")

    # Final summary
    total_time = time.time() - t_start
    log("\n" + "=" * 60)
    log("FINAL SUMMARY")
    log("=" * 60)
    log(f"Total time: {total_time:.0f}s ({total_time / 60:.1f} minutes)")
    log(f"Passed: {len(passed)}/{len(passed) + len(failed)} — {', '.join(passed)}")
    if failed:
        log(f"Failed: {', '.join(failed)}")
    else:
        log("ALL STEPS PASSED")
    log(f"Output files saved to: {OUTPUT_DIR}")
    log("=" * 60)


if __name__ == '__main__':
    main()
