"""
E2E test: Generate an Existing Reality report from the Zep graph
built in the previous e2e_pipeline_test.py run.

Uses graph_id from step6_graph_summary.json.
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'e2e_output')
LOG_FILE = os.path.join(OUTPUT_DIR, 'e2e_report_log.txt')


def log(msg):
    timestamp = time.strftime('%H:%M:%S')
    line = f"[{timestamp}] {msg}"
    with open(LOG_FILE, 'a') as f:
        f.write(line + '\n')
    print(line)


def main():
    with open(LOG_FILE, 'w') as f:
        f.write("")

    # Load graph_id from previous run
    summary_path = os.path.join(OUTPUT_DIR, 'step6_graph_summary.json')
    if not os.path.exists(summary_path):
        log("ERROR: No step6_graph_summary.json found. Run e2e_pipeline_test.py first.")
        return

    with open(summary_path) as f:
        graph_summary = json.load(f)
    graph_id = graph_summary['graph_id']
    log(f"Using graph: {graph_id} ({graph_summary['node_count']} nodes, {graph_summary['edge_count']} edges)")

    # Check the enriched graph (after focus group loading)
    enriched_path = os.path.join(OUTPUT_DIR, 'step8_graph_after_fg.json')
    if os.path.exists(enriched_path):
        with open(enriched_path) as f:
            enriched = json.load(f)
        log(f"Graph after FG loading: {enriched['node_count']} nodes, {enriched['edge_count']} edges")

    research_question = (
        "How are non-technical entrepreneurs and AI hobbyists in the US currently "
        "discovering and using mobile AI coding tools, and what barriers prevent wider adoption?"
    )

    log("\n" + "=" * 60)
    log("GENERATING EXISTING REALITY REPORT")
    log("=" * 60)
    log(f"Research question: {research_question}")
    log(f"Mode: reality (Phase 1)")

    from app.services.reality_report_adapter import RealityReportAdapter

    adapter = RealityReportAdapter(
        graph_id=graph_id,
        simulation_id="e2e_test_reality",
        research_question=research_question,
        mode="reality",
    )

    def progress_cb(stage, progress, message):
        log(f"  [{int(progress)}%] [{stage}] {message}")

    log("Starting report generation...")
    t0 = time.time()
    report_id = adapter.generate_report(progress_callback=progress_cb)
    elapsed = time.time() - t0
    log(f"\nReport generated in {elapsed:.0f}s ({elapsed/60:.1f} min)")
    log(f"Report ID: {report_id}")

    # Read the report
    report_dir = os.path.join(os.path.dirname(__file__), '..', 'uploads', 'reports', report_id)
    report_path = os.path.join(report_dir, 'full_report.md')
    if os.path.exists(report_path):
        with open(report_path) as f:
            report_text = f.read()
        log(f"Report length: {len(report_text)} chars, {len(report_text.splitlines())} lines")

        # Copy to e2e_output for easy comparison
        output_path = os.path.join(OUTPUT_DIR, 'reality_report.md')
        with open(output_path, 'w') as f:
            f.write(report_text)
        log(f"Saved to: {output_path}")

        # Quick quality checks
        lower = report_text.lower()
        checks = [
            ("Contains 'existing reality' or 'current'", 'existing' in lower or 'current' in lower),
            ("References real people (@usernames)", '@' in report_text),
            ("Has multiple sections (##)", report_text.count('## ') >= 2),
            ("Substantive (>2000 chars)", len(report_text) > 2000),
            ("In English", 'the ' in lower and 'and ' in lower),
        ]
        for desc, ok in checks:
            status = "OK" if ok else "WARN"
            log(f"  {status}: {desc}")
    else:
        log(f"WARNING: Report file not found at {report_path}")
        # List what's in the report dir
        if os.path.exists(report_dir):
            files = os.listdir(report_dir)
            log(f"  Files in report dir: {files}")

    log("\n" + "=" * 60)
    log("REPORT GENERATION COMPLETE")
    log("=" * 60)


if __name__ == '__main__':
    main()
