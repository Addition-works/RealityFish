"""
Thesis MD parser.

Reads a thesis markdown file and extracts structured data:
- Research question / hypothesis
- Scope parameters (platforms, keywords, geography, time window)
- Target audience profiles (behaviors, interests, demographics)
- Optional known context (products, competitors, market forces)
"""

import re
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AudienceProfile:
    name: str
    description: str
    behaviors: list[str] = field(default_factory=list)
    interests: list[str] = field(default_factory=list)
    demographics: list[str] = field(default_factory=list)


@dataclass
class ScopeParams:
    platforms: list[str] = field(default_factory=lambda: ["x", "reddit"])
    keywords: list[str] = field(default_factory=list)
    geography: str = ""
    time_window_days: int = 30


@dataclass
class Thesis:
    research_question: str
    scope: ScopeParams
    audience_profiles: list[AudienceProfile]
    known_context: str = ""
    raw_text: str = ""

    def validate(self) -> list[str]:
        errors = []
        if not self.research_question.strip():
            errors.append("Research question is empty")
        if not self.audience_profiles:
            errors.append("At least one audience profile is required")
        if not self.scope.keywords:
            errors.append("At least one keyword is required in scope")
        return errors


def parse_thesis(text: str) -> Thesis:
    """
    Parse a thesis markdown file into structured data.

    Expected format (sections identified by ## headings):

    ## Research Question
    <free text>

    ## Scope
    - Platforms: x, reddit
    - Keywords: vibe coding, AI tools, ...
    - Geography: US
    - Time Window: 30 days

    ## Audience Profiles
    ### <Profile Name>
    <description paragraph>
    - Behaviors: ...
    - Interests: ...
    - Demographics: ...

    ## Known Context
    <free text about products, competitors, market>
    """
    sections = _split_sections(text)

    research_question = sections.get("research question", "").strip()

    scope = _parse_scope(sections.get("scope", ""))

    audience_profiles = _parse_audience_profiles(text)

    known_context = sections.get("known context", "").strip()

    return Thesis(
        research_question=research_question,
        scope=scope,
        audience_profiles=audience_profiles,
        known_context=known_context,
        raw_text=text,
    )


def _split_sections(text: str) -> dict[str, str]:
    """Split markdown into sections by ## headings."""
    sections: dict[str, str] = {}
    current_heading = ""
    current_lines: list[str] = []

    for line in text.split("\n"):
        heading_match = re.match(r"^##\s+(.+)$", line.strip())
        if heading_match:
            if current_heading:
                sections[current_heading] = "\n".join(current_lines).strip()
            current_heading = heading_match.group(1).strip().lower()
            current_lines = []
        else:
            current_lines.append(line)

    if current_heading:
        sections[current_heading] = "\n".join(current_lines).strip()

    return sections


def _parse_scope(text: str) -> ScopeParams:
    """Parse scope section into ScopeParams."""
    scope = ScopeParams()
    if not text:
        return scope

    for line in text.split("\n"):
        line = line.strip().lstrip("- ")
        lower = line.lower()

        if lower.startswith("platforms:"):
            raw = line.split(":", 1)[1].strip()
            scope.platforms = [p.strip().lower() for p in raw.split(",") if p.strip()]
        elif lower.startswith("keywords:"):
            raw = line.split(":", 1)[1].strip()
            scope.keywords = [k.strip() for k in raw.split(",") if k.strip()]
        elif lower.startswith("geography:"):
            scope.geography = line.split(":", 1)[1].strip()
        elif lower.startswith("time window:"):
            raw = line.split(":", 1)[1].strip()
            days_match = re.search(r"(\d+)", raw)
            if days_match:
                scope.time_window_days = int(days_match.group(1))

    return scope


def _parse_audience_profiles(text: str) -> list[AudienceProfile]:
    """Parse ### sub-sections under ## Audience Profiles."""
    profiles: list[AudienceProfile] = []

    in_audience_section = False
    current_profile: Optional[AudienceProfile] = None
    desc_lines: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()

        h2_match = re.match(r"^##\s+(.+)$", stripped)
        if h2_match:
            heading = h2_match.group(1).strip().lower()
            if heading == "audience profiles":
                in_audience_section = True
                continue
            else:
                if in_audience_section and current_profile:
                    current_profile.description = "\n".join(desc_lines).strip()
                    profiles.append(current_profile)
                    current_profile = None
                    desc_lines = []
                in_audience_section = False
                continue

        if not in_audience_section:
            continue

        h3_match = re.match(r"^###\s+(.+)$", stripped)
        if h3_match:
            if current_profile:
                current_profile.description = "\n".join(desc_lines).strip()
                profiles.append(current_profile)
            current_profile = AudienceProfile(name=h3_match.group(1).strip(), description="")
            desc_lines = []
            continue

        if current_profile:
            lower = stripped.lower().lstrip("- ")
            if lower.startswith("behaviors:"):
                raw = stripped.split(":", 1)[1].strip()
                current_profile.behaviors = [b.strip() for b in raw.split(",") if b.strip()]
            elif lower.startswith("interests:"):
                raw = stripped.split(":", 1)[1].strip()
                current_profile.interests = [i.strip() for i in raw.split(",") if i.strip()]
            elif lower.startswith("demographics:"):
                raw = stripped.split(":", 1)[1].strip()
                current_profile.demographics = [d.strip() for d in raw.split(",") if d.strip()]
            else:
                desc_lines.append(line)

    if in_audience_section and current_profile:
        current_profile.description = "\n".join(desc_lines).strip()
        profiles.append(current_profile)

    return profiles
