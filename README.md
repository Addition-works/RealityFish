<div align="center">

# RealityFish

**Understand the present. Simulate the future.**

A reality-grounded simulation engine forked from [MiroFish](https://github.com/666ghj/MiroFish).

[![License](https://img.shields.io/badge/License-AGPL--3.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.11--3.12-3776AB?logo=python&logoColor=white)](https://python.org)
[![Vue](https://img.shields.io/badge/Vue-3-4FC08D?logo=vue.js&logoColor=white)](https://vuejs.org)

</div>

---

## What is RealityFish?

MiroFish builds simulated worlds from seed documents and runs multi-agent predictions. **RealityFish extends this** by grounding the simulation in *real* social media entities before predicting how they'll react to a future event.

The core idea is a **two-phase pipeline**:

| Phase | Name | What happens |
|-------|------|-------------|
| **1** | **Existing Reality** | Scrape real X/Twitter and Reddit users, extract entities, build a knowledge graph of the *actual* conversation landscape, generate an Existing Reality Report |
| **2** | **Future Simulation** | Inject a scenario (e.g. a product launch), convert real entities into OASIS simulation agents with calibrated awareness probabilities, run the simulation, generate a Future Prediction Report |

### How is this different from MiroFish?

| Capability | MiroFish | RealityFish |
|-----------|----------|-------------|
| **Data source** | Uploaded seed documents | Real social media scraping (X via Apify, Reddit via PRAW) + seed documents |
| **Entities** | LLM-generated from text | Real users with verified bios, follower counts, post history |
| **Entity validation** | None | Audience scoring against thesis profiles, human review step |
| **Awareness model** | All agents aware of scenario | Calibrated per-agent awareness & caring probabilities |
| **Reports** | Single prediction report | Two reports: Existing Reality + Future Prediction |
| **Anti-hallucination** | None | Fake tool-result stripping, prompt constraints, entity verification |
| **Focus groups** | Not present | LLM-driven focus group discussions before report generation |

## Architecture

```
Thesis (.md)
    │
    ▼
┌──────────────────────────────────────────────────┐
│  Phase 1: Existing Reality                       │
│                                                  │
│  ThesisParser → SocialScraper → EntityExtractor  │
│       → WorldBuilder → Zep Knowledge Graph       │
│       → Human Review → RealityReportAdapter      │
│       → FocusGroupEngine → Existing Reality Rpt  │
└──────────────────────────────────────────────────┘
    │
    ▼  Scenario injection
┌──────────────────────────────────────────────────┐
│  Phase 2: Future Simulation                      │
│                                                  │
│  PhaseBridge → OasisAgentProfiles + Awareness    │
│       → SimulationConfigGenerator                │
│       → OASIS Simulation (Twitter + Reddit)      │
│       → RealityReportAdapter (future mode)       │
│       → Future Prediction Report                 │
└──────────────────────────────────────────────────┘
```

## New Backend Services

These services are **new to RealityFish** (not present in upstream MiroFish):

| Service | Purpose |
|---------|---------|
| `thesis_parser.py` | Parses structured markdown thesis into research question, scope, audience profiles |
| `social_scraper.py` | X/Twitter scraping via Apify, Reddit scraping via PRAW |
| `entity_extractor.py` | LLM-driven entity identification, deduplication, enrichment, audience scoring |
| `world_builder.py` | Orchestrates the full Phase 1 data ingestion pipeline |
| `reality_graph_builder.py` | Builds Zep knowledge graph from real scraped entities |
| `awareness_engine.py` | Computes per-agent awareness and caring probabilities |
| `phase_bridge.py` | Converts Phase 1 `ExtractedEntity` into OASIS `AgentProfile` + `AwarenessProfile` |
| `focus_group_engine.py` | Runs LLM-driven focus group discussions |
| `reality_report_adapter.py` | Adapts `ReportAgent` with mode-specific prompts (existing vs future) |
| `reality_report_prompts.py` | Prompt templates with anti-hallucination rules |

## Modified Upstream Services

These MiroFish services were patched for RealityFish:

- **`report_agent.py`** — Added `_strip_fake_tool_results()` to prevent LLM hallucination of fabricated tool outputs
- **`zep_tools.py`** — Translated Chinese sub-query generation to English
- **`simulation_config_generator.py`** — Adapted to accept `EntityNode` shims from real scraped profiles

## Quick Start

### Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Node.js | 18+ | `node -v` |
| Python | 3.11–3.12 | `python --version` |
| uv | Latest | `uv --version` |

### 1. Configure Environment

```bash
cp .env.example .env
```

**Required variables:**

```env
# LLM API (OpenAI SDK-compatible endpoint)
LLM_API_KEY=your_key
LLM_BASE_URL=https://your-llm-provider/v1
LLM_MODEL_NAME=your-model

# Zep Cloud knowledge graph
ZEP_API_KEY=your_zep_key
```

**RealityFish-specific variables (for social scraping):**

```env
# Apify — X/Twitter scraping
APIFY_API_TOKEN=your_apify_token

# Reddit API (register at https://www.reddit.com/prefs/apps)
REDDIT_CLIENT_ID=your_client_id
REDDIT_CLIENT_SECRET=your_client_secret
REDDIT_USER_AGENT=realityfish-bot/1.0
```

**Optional tuning:**

```env
OASIS_DEFAULT_MAX_ROUNDS=10
FOCUS_GROUPS_ENABLED=true
AWARENESS_BASE_PROBABILITY=0.15
TOPIC_AWARE_BOOST=0.6
```

### 2. Install Dependencies

```bash
npm run setup:all
```

Or step by step:

```bash
npm run setup          # Node dependencies (root + frontend)
npm run setup:backend  # Python dependencies (auto-creates venv)
```

### 3. Start Services

```bash
npm run dev
```

- Frontend: `http://localhost:3000`
- Backend API: `http://localhost:5001`

### Using the RealityFish Pipeline

1. Navigate to `http://localhost:3000` and click **RealityFish Pipeline** in the nav bar
2. Upload a thesis `.md` file defining your research question and audience profiles
3. The system scrapes X and Reddit, extracts and enriches entities
4. Review the entity pool and approve
5. Generate the **Existing Reality Report**
6. Define a future scenario (e.g. "Google launches AI Studio Mobile")
7. The system converts entities to OASIS agents with awareness calibration and runs the simulation
8. View the **Future Prediction Report**

## API Routes

All RealityFish routes are under `/api/reality/`:

| Method | Endpoint | Purpose |
|--------|----------|---------|
| POST | `/thesis/upload` | Parse thesis markdown |
| POST | `/world/build` | Start world-building pipeline |
| GET | `/world/status/<task_id>` | Poll async task status |
| GET | `/world/review/<project_id>` | Get entity pool for review |
| POST | `/world/approve/<project_id>` | Approve entity pool |
| POST | `/reality/report` | Generate Existing Reality report |
| POST | `/focus-group/run` | Run focus group discussions |
| POST | `/scenario/inject` | Set future scenario |
| POST | `/future/simulate` | Run Phase 2 simulation + report |
| GET | `/project/<project_id>` | Get project state |

The original MiroFish routes (`/api/graph`, `/api/simulation`, `/api/report`) remain available for the classic workflow.

## Testing

```bash
cd backend

# Unit tests
python -m pytest tests/test_thesis_parser.py
python -m pytest tests/test_entity_extractor.py
python -m pytest tests/test_social_scraper.py
python -m pytest tests/test_phase_bridge.py
python -m pytest tests/test_awareness_engine.py

# E2E tests (require API keys)
python tests/e2e_pipeline_test.py      # Full Phase 1 pipeline
python tests/e2e_reality_report_test.py # Phase 1 report generation
python tests/e2e_phase2_test.py         # Full Phase 2 pipeline
```

## Roadmap

### Completed

- [x] **Thesis parser** — structured markdown → research question, scope, audience profiles
- [x] **Social scraper** — X/Twitter (Apify) + Reddit (PRAW) keyword and username search
- [x] **Entity extraction & enrichment** — LLM-driven identification, deduplication, bio/followers/audience scoring
- [x] **World builder** — orchestrated Phase 1 pipeline with async deep scraping
- [x] **Zep knowledge graph** — entities, relationships, and focus group transcripts stored in Zep Cloud
- [x] **Human review step** — entity pool review and approval before report generation
- [x] **Existing Reality report** — ReACT-based report grounded in real scraped data
- [x] **Anti-hallucination** — fake tool-result stripping, prompt constraints, entity verification
- [x] **Focus groups** — LLM-driven panel discussions integrated into report generation
- [x] **Phase Bridge** — convert real entities → OASIS agent profiles with awareness probabilities
- [x] **Future simulation** — OASIS multi-agent sim (Twitter + Reddit) from real entity profiles
- [x] **Future Prediction report** — scenario-aware report from simulation output
- [x] **Backend API** — full `/api/reality/` blueprint with async task management
- [x] **RealityView.vue** — dedicated frontend view for the two-phase pipeline
- [x] **Bug fix upstream** — filed [MiroFish #529](https://github.com/666ghj/MiroFish/issues/529) for ReACT hallucination bug

### Remaining Work

#### Frontend (high priority)

- [ ] **Rebrand Home.vue** — replace MiroFish logo, branding, and hero copy with RealityFish identity
- [ ] **Replace `MiroFish_logo_left.jpeg`** in `frontend/src/assets/logo/` with a RealityFish logo asset
- [ ] **i18n for RealityView** — currently English-hardcoded; wire into the `locales/en.json` / `locales/zh.json` system
- [ ] **Unify navigation** — decide whether `/reality` is the primary entry point or coexists with the classic MiroFish `/process/:projectId` flow; update `Home.vue` accordingly
- [ ] **Report viewer for two-phase reports** — the existing `ReportView.vue` renders one report; add UI to view Existing Reality and Future Prediction reports side by side or sequentially
- [ ] **Entity review UX** — the entity grid in `RealityView.vue` is functional but basic; add filtering, sorting, inline editing, and batch approval/rejection
- [ ] **Scenario template library** — pre-built scenario templates users can select instead of free-text only
- [ ] **Error handling & loading states** — add toast notifications, retry buttons, and better progress messaging across all steps

#### Backend (high priority)

- [ ] **Unified run folder** — all outputs for a single pipeline run (entity pool, reality report, simulation config, simulation actions, awareness config, future report, focus group transcripts) must land in one folder keyed by a single `run_id`, not scattered across `uploads/reports/report_<hash>` and `uploads/simulations/sim_<hash>` with separate IDs
- [ ] **Post-simulation agent chat (Phase 3)** — after the Future Prediction report, let the user open MiroFish's existing `InteractionView` chat to talk directly with the simulated agents; use this to explore "what would you need to see to react differently?" and iterate on strategy before re-running

#### Backend (medium priority)

- [ ] **Scraper rate-limit resilience** — add exponential backoff and retry logic for Apify and PRAW API failures
- [ ] **LLM rate-limit handling in OASIS** — simulation stalls when the LLM provider rate-limits; add queuing, backoff, or provider rotation
- [ ] **Entity deduplication across platforms** — same person on X and Reddit should merge into one entity
- [ ] **Awareness config fed into OASIS agent behavior** — `awareness_config.json` is generated but OASIS agents don't yet read per-agent awareness probabilities at runtime; they all participate equally
- [ ] **Simulation result persistence** — save simulation metadata (rounds completed, action counts, duration) to a project-level summary for the UI
- [ ] **Report comparison endpoint** — API route to return both Phase 1 and Phase 2 reports for side-by-side rendering

#### Data privacy & knowledge graph (high priority)

- [ ] **Zep dependency evaluation** — the entire knowledge graph layer (entity storage, relationships, graph search, focus group transcripts) currently runs through Zep Cloud, meaning all scraped entities and thesis content leave the network. Evaluate three paths:
  1. **Stay on Zep Cloud free/pro** — acceptable for public-data-only research; document the data exposure clearly
  2. **Zep Enterprise / self-hosted** — Zep offers a self-hosted option; evaluate cost, feature parity, and ops burden
  3. **Replace Zep with a local graph** — refactor `zep_tools.py`, `zep_entity_reader.py`, `reality_graph_builder.py`, and `zep_graph_memory_updater.py` to use a locally hosted graph DB (e.g. Neo4j, FalkorDB, or a lightweight in-process store like NetworkX + vector search) so confidential data never leaves the host
- [ ] **Audit all external data flows** — beyond Zep, map every service that sends data externally (LLM API, Apify, Reddit API) and document what data is exposed at each stage, so enterprise users can make informed deployment decisions

#### Infrastructure & polish

- [ ] **CI pipeline** — GitHub Actions for linting, unit tests, and E2E smoke tests
- [ ] **Docker update** — `Dockerfile` and `docker-compose.yml` still reference MiroFish; update for RealityFish env vars
- [ ] **Seed document examples** — add sample thesis `.md` files to `seed_documents/` so new users can try the pipeline immediately
- [ ] **Documentation** — API reference, thesis format spec, and architecture deep-dive

## Acknowledgments

RealityFish is forked from [MiroFish](https://github.com/666ghj/MiroFish) by the 666ghj team, which received strategic support from Shanda Group. The simulation engine is powered by [OASIS](https://github.com/camel-ai/oasis) from CAMEL-AI.

## License

[AGPL-3.0](LICENSE)
