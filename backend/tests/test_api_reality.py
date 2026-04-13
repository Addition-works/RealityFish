"""Tests for reality API endpoints — validates routing, request/response shapes."""

import sys
import os
import json
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app import create_app

SAMPLE_THESIS = """## Research Question
How are people currently using AI coding tools?

## Scope
- Platforms: x, reddit
- Keywords: vibe coding, AI tools
- Geography: US
- Time Window: 14 days

## Audience Profiles

### Developers
Professional software developers experimenting with AI.
- Behaviors: posting code snippets, reviewing tools
- Interests: programming, AI, productivity
- Demographics: 22-45, tech industry

### Entrepreneurs
Business owners looking for automation.
- Behaviors: asking for tool recommendations
- Interests: small business, efficiency
- Demographics: 25-55, non-technical
"""


def get_client():
    app = create_app()
    app.config['TESTING'] = True
    return app.test_client()


def test_thesis_upload_text():
    client = get_client()
    resp = client.post('/api/reality/thesis/upload',
                       data=json.dumps({"text": SAMPLE_THESIS}),
                       content_type='application/json')
    assert resp.status_code == 200
    data = resp.get_json()
    assert "project_id" in data
    assert data["research_question"].startswith("How are people")
    assert len(data["audience_profiles"]) == 2
    assert data["scope"]["platforms"] == ["x", "reddit"]
    return data["project_id"]


def test_thesis_upload_empty():
    client = get_client()
    resp = client.post('/api/reality/thesis/upload',
                       data=json.dumps({"text": "## Research Question\n\n## Scope\n\n## Audience Profiles\n"}),
                       content_type='application/json')
    assert resp.status_code == 400
    data = resp.get_json()
    assert "error" in data
    assert "details" in data


def test_project_not_found():
    client = get_client()
    resp = client.get('/api/reality/project/nonexistent')
    assert resp.status_code == 404


def test_world_review_not_found():
    client = get_client()
    resp = client.get('/api/reality/world/review/nonexistent')
    assert resp.status_code == 404


def test_scraper_status():
    client = get_client()
    resp = client.get('/api/reality/scraper/status')
    assert resp.status_code == 200
    data = resp.get_json()
    assert "x" in data
    assert "reddit" in data
    assert "available" in data["x"]


def test_full_thesis_then_project():
    """Upload thesis, then check project state."""
    client = get_client()

    resp = client.post('/api/reality/thesis/upload',
                       data=json.dumps({"text": SAMPLE_THESIS}),
                       content_type='application/json')
    assert resp.status_code == 200
    project_id = resp.get_json()["project_id"]

    resp = client.get(f'/api/reality/project/{project_id}')
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["phase"] == "thesis_parsed"
    assert data["entity_count"] == 0


def test_approve_world_without_build():
    """Can approve even before build (in case of manual entity loading)."""
    client = get_client()

    resp = client.post('/api/reality/thesis/upload',
                       data=json.dumps({"text": SAMPLE_THESIS}),
                       content_type='application/json')
    project_id = resp.get_json()["project_id"]

    resp = client.post(f'/api/reality/world/approve/{project_id}',
                       data=json.dumps({"feedback": "Looks good"}),
                       content_type='application/json')
    assert resp.status_code == 200
    assert resp.get_json()["phase"] == "world_approved"


def test_scenario_inject():
    client = get_client()

    resp = client.post('/api/reality/thesis/upload',
                       data=json.dumps({"text": SAMPLE_THESIS}),
                       content_type='application/json')
    project_id = resp.get_json()["project_id"]

    resp = client.post('/api/reality/scenario/inject',
                       data=json.dumps({
                           "project_id": project_id,
                           "scenario": "Google launches AI Studio Mobile app",
                       }),
                       content_type='application/json')
    assert resp.status_code == 200
    assert resp.get_json()["phase"] == "scenario_defined"


def test_scenario_inject_empty():
    client = get_client()

    resp = client.post('/api/reality/thesis/upload',
                       data=json.dumps({"text": SAMPLE_THESIS}),
                       content_type='application/json')
    project_id = resp.get_json()["project_id"]

    resp = client.post('/api/reality/scenario/inject',
                       data=json.dumps({"project_id": project_id, "scenario": ""}),
                       content_type='application/json')
    assert resp.status_code == 400


if __name__ == "__main__":
    test_thesis_upload_text()
    test_thesis_upload_empty()
    test_project_not_found()
    test_world_review_not_found()
    test_scraper_status()
    test_full_thesis_then_project()
    test_approve_world_without_build()
    test_scenario_inject()
    test_scenario_inject_empty()
    print("All API reality tests passed!")
