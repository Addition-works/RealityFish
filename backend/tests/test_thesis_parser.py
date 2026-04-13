"""Tests for thesis_parser.py"""

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from app.services.thesis_parser import parse_thesis, Thesis, AudienceProfile, ScopeParams


SAMPLE_THESIS = """# Understanding Mobile Vibe Coding Adoption

## Research Question
How are non-technical entrepreneurs and small business owners in the US currently thinking about AI-powered coding tools, and what would drive them to adopt a mobile-first vibe coding solution?

## Scope
- Platforms: x, reddit
- Keywords: vibe coding, AI coding, no-code mobile, build app without coding, AI app builder
- Geography: US
- Time Window: 30 days

## Audience Profiles

### Non-Technical Entrepreneurs
Small business owners who run businesses like food trucks, Etsy shops, local services. They solve problems with spreadsheets and manual processes, not code. They may have heard of AI but haven't tried coding tools.
- Behaviors: posting about business challenges, sharing growth milestones, asking for tool recommendations
- Interests: small business, entrepreneurship, side hustles, automation
- Demographics: 25-55, US-based, non-technical background

### AI Hobbyists
People who experiment with AI tools for fun or personal projects. They follow AI news, try new tools early, and share results on social media. They are already in the conversation.
- Behaviors: sharing AI project screenshots, reviewing tools, participating in AI communities
- Interests: artificial intelligence, machine learning, coding, tech gadgets
- Demographics: 18-40, tech-savvy, early adopters

### Educators
Teachers and professors exploring how AI can be used in education. Some are using tools in classrooms, others are skeptical.
- Behaviors: discussing pedagogy, sharing classroom experiences, debating AI in education
- Interests: education technology, STEM teaching, curriculum design
- Demographics: 28-60, education sector, mixed technical background

## Known Context
Google AI Studio is a free platform for building AI-powered applications. A mobile version is launching that enables "vibe coding" on the go. Key competitors include Replit Mobile, Rork, and Vibe Studio. Claude Code from Anthropic is the current market leader in AI-assisted coding.
"""


def test_parse_research_question():
    thesis = parse_thesis(SAMPLE_THESIS)
    assert "non-technical entrepreneurs" in thesis.research_question.lower()
    assert "mobile-first" in thesis.research_question.lower()


def test_parse_scope():
    thesis = parse_thesis(SAMPLE_THESIS)
    assert thesis.scope.platforms == ["x", "reddit"]
    assert "vibe coding" in thesis.scope.keywords
    assert "AI app builder" in thesis.scope.keywords
    assert len(thesis.scope.keywords) == 5
    assert thesis.scope.geography == "US"
    assert thesis.scope.time_window_days == 30


def test_parse_audience_profiles():
    thesis = parse_thesis(SAMPLE_THESIS)
    assert len(thesis.audience_profiles) == 3

    entrepreneurs = thesis.audience_profiles[0]
    assert entrepreneurs.name == "Non-Technical Entrepreneurs"
    assert "food trucks" in entrepreneurs.description.lower()
    assert "small business" in entrepreneurs.interests
    assert "25-55" in entrepreneurs.demographics

    hobbyists = thesis.audience_profiles[1]
    assert hobbyists.name == "AI Hobbyists"
    assert "sharing AI project screenshots" in hobbyists.behaviors

    educators = thesis.audience_profiles[2]
    assert educators.name == "Educators"
    assert "education technology" in educators.interests


def test_parse_known_context():
    thesis = parse_thesis(SAMPLE_THESIS)
    assert "Google AI Studio" in thesis.known_context
    assert "Claude Code" in thesis.known_context
    assert "Replit Mobile" in thesis.known_context


def test_raw_text_preserved():
    thesis = parse_thesis(SAMPLE_THESIS)
    assert thesis.raw_text == SAMPLE_THESIS


def test_validation_passes():
    thesis = parse_thesis(SAMPLE_THESIS)
    errors = thesis.validate()
    assert errors == [], f"Unexpected validation errors: {errors}"


def test_validation_empty_question():
    thesis = Thesis(
        research_question="",
        scope=ScopeParams(keywords=["test"]),
        audience_profiles=[AudienceProfile(name="Test", description="test")],
    )
    errors = thesis.validate()
    assert "Research question is empty" in errors


def test_validation_no_profiles():
    thesis = Thesis(
        research_question="Some question?",
        scope=ScopeParams(keywords=["test"]),
        audience_profiles=[],
    )
    errors = thesis.validate()
    assert "At least one audience profile is required" in errors


def test_validation_no_keywords():
    thesis = Thesis(
        research_question="Some question?",
        scope=ScopeParams(),
        audience_profiles=[AudienceProfile(name="Test", description="test")],
    )
    errors = thesis.validate()
    assert "At least one keyword is required in scope" in errors


def test_minimal_thesis():
    minimal = """## Research Question
What do people think?

## Scope
- Platforms: x
- Keywords: AI tools

## Audience Profiles

### General Users
Anyone using tech.
"""
    thesis = parse_thesis(minimal)
    assert thesis.research_question == "What do people think?"
    assert thesis.scope.platforms == ["x"]
    assert thesis.scope.keywords == ["AI tools"]
    assert len(thesis.audience_profiles) == 1
    assert thesis.audience_profiles[0].name == "General Users"
    assert thesis.known_context == ""
    assert thesis.validate() == []


if __name__ == "__main__":
    test_parse_research_question()
    test_parse_scope()
    test_parse_audience_profiles()
    test_parse_known_context()
    test_raw_text_preserved()
    test_validation_passes()
    test_validation_empty_question()
    test_validation_no_profiles()
    test_validation_no_keywords()
    test_minimal_thesis()
    print("All thesis_parser tests passed!")
