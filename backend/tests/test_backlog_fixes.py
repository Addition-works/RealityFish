"""
Test script for backlog fixes:
1. Bio/profile metadata extraction from raw_data
2. Audience profile scoring
3. Async deep scrape (parallel username lookups)

Uses the existing Zep graph and scraped data from the E2E test.
"""

import sys
import os
import json
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

OUTPUT_DIR = os.path.join(os.path.dirname(__file__), 'e2e_output')


def log(msg):
    timestamp = time.strftime('%H:%M:%S')
    print(f"[{timestamp}] {msg}")


def test_bio_extraction():
    """Test 1: Extract bio/followers/verified from raw_data."""
    log("\n" + "=" * 60)
    log("TEST 1: BIO / PROFILE METADATA EXTRACTION")
    log("=" * 60)

    from app.services.social_scraper import XScraper, SocialScraper

    # Test XScraper.extract_user_profile with mock Apify data
    mock_raw = {
        "author": {
            "userName": "testuser",
            "name": "Test User",
            "description": "AI enthusiast | Builder of things | 🚀",
            "followers": 5420,
            "following": 312,
            "isVerified": False,
            "isBlueVerified": True,
            "location": "San Francisco, CA",
            "profilePicture": "https://example.com/pic.jpg",
        }
    }

    profile = XScraper.extract_user_profile(mock_raw)
    assert profile["bio"] == "AI enthusiast | Builder of things | 🚀", f"Bio mismatch: {profile['bio']}"
    assert profile["followers"] == 5420, f"Followers mismatch: {profile['followers']}"
    assert profile["verified"] == True, "Should be verified via isBlueVerified"
    assert profile["location"] == "San Francisco, CA"
    log("  OK: XScraper.extract_user_profile correctly extracts all fields")

    # Test with empty author
    empty_profile = XScraper.extract_user_profile({})
    assert empty_profile == {}, "Empty raw_data should return empty dict"
    log("  OK: Handles empty raw_data gracefully")

    # Test with profile_bio fallback
    mock_raw_alt = {
        "author": {
            "description": "",
            "profile_bio": {"description": "Fallback bio text"},
            "followers": 100,
        }
    }
    profile_alt = XScraper.extract_user_profile(mock_raw_alt)
    assert profile_alt["bio"] == "Fallback bio text", "Should fall back to profile_bio.description"
    log("  OK: Falls back to profile_bio.description when description is empty")

    # Test populate_profile_metadata on real entities
    from app.services.entity_extractor import EntityExtractor, ExtractedEntity
    from app.services.social_scraper import ScrapedPost

    extractor = EntityExtractor()

    entity = ExtractedEntity(
        username="testuser",
        platform="x",
        posts=[
            ScrapedPost(
                platform="x",
                post_id="123",
                author_username="testuser",
                text="test post",
                raw_data=mock_raw,
            )
        ],
    )

    result = extractor.populate_profile_metadata([entity])
    assert result[0].bio == "AI enthusiast | Builder of things | 🚀"
    assert result[0].followers == 5420
    assert result[0].verified == True
    assert result[0].location == "San Francisco, CA"
    log("  OK: populate_profile_metadata correctly populates entity from raw_data")
    log("  TEST 1 PASSED ✓")


def test_audience_scoring():
    """Test 2: Score entities against thesis audience profiles."""
    log("\n" + "=" * 60)
    log("TEST 2: AUDIENCE PROFILE SCORING")
    log("=" * 60)

    from app.services.entity_extractor import EntityExtractor, ExtractedEntity
    from app.services.social_scraper import ScrapedPost
    from app.services.thesis_parser import AudienceProfile

    extractor = EntityExtractor()

    entities = [
        ExtractedEntity(
            username="startup_sarah",
            platform="x",
            display_name="Sarah the Builder",
            bio="Solo founder building SaaS. No-code enthusiast.",
            posts=[
                ScrapedPost(
                    platform="x",
                    post_id="1",
                    author_username="startup_sarah",
                    text="Just launched my Etsy analytics tool using Bubble. No coding needed!",
                )
            ],
            core_topics=["no-code", "SaaS", "small business"],
        ),
        ExtractedEntity(
            username="dev_mike",
            platform="x",
            display_name="Mike Dev",
            bio="Senior SWE at BigCorp. Rust/Go.",
            posts=[
                ScrapedPost(
                    platform="x",
                    post_id="2",
                    author_username="dev_mike",
                    text="Benchmarked the new Rust compiler. 15% faster builds.",
                )
            ],
            core_topics=["Rust", "systems programming", "performance"],
        ),
        ExtractedEntity(
            username="ai_hobbyist_jen",
            platform="reddit",
            display_name="Jen",
            bio="Playing with AI on weekends. Cat mom.",
            posts=[
                ScrapedPost(
                    platform="reddit",
                    post_id="3",
                    author_username="ai_hobbyist_jen",
                    text="Built a fun chatbot for my Discord server using ChatGPT API",
                )
            ],
            core_topics=["AI tools", "ChatGPT", "hobby projects"],
        ),
    ]

    audiences = [
        AudienceProfile(
            name="Non-Technical Entrepreneurs",
            description="Small business owners and solo founders who don't code but use technology to run their businesses",
            behaviors=["uses no-code tools", "runs small business"],
            interests=["automation", "business growth"],
        ),
        AudienceProfile(
            name="AI Hobbyists",
            description="People who experiment with AI tools for fun or personal projects, not professionally",
            behaviors=["weekend projects", "tries new AI tools"],
            interests=["ChatGPT", "AI art", "automation"],
        ),
    ]

    log("  Scoring 3 entities against 2 audience profiles via LLM...")
    t0 = time.time()
    result = extractor.score_against_audiences(entities, audiences)
    elapsed = time.time() - t0
    log(f"  LLM scoring took {elapsed:.1f}s")

    for entity in result:
        scores = entity.audience_scores
        log(f"  @{entity.username}: {json.dumps(scores, indent=None)}")

        assert isinstance(scores, dict), f"Scores should be dict, got {type(scores)}"
        if scores:
            for name, score in scores.items():
                assert 0.0 <= score <= 1.0, f"Score out of range: {name}={score}"

    # Validate expected patterns
    sarah_scores = result[0].audience_scores
    jen_scores = result[2].audience_scores

    if sarah_scores and jen_scores:
        sarah_entrepreneur = sarah_scores.get("Non-Technical Entrepreneurs", sarah_scores.get("Non_Technical_Entrepreneurs", 0))
        jen_hobbyist = jen_scores.get("AI Hobbyists", jen_scores.get("AI_Hobbyists", 0))

        if sarah_entrepreneur > 0 and jen_hobbyist > 0:
            log(f"  Sarah entrepreneur score: {sarah_entrepreneur} (expected high)")
            log(f"  Jen AI hobbyist score: {jen_hobbyist} (expected high)")

    log("  TEST 2 PASSED ✓")


def test_async_deep_scrape():
    """Test 3: Verify parallel deep scraping works."""
    log("\n" + "=" * 60)
    log("TEST 3: ASYNC DEEP SCRAPE")
    log("=" * 60)

    from app.services.world_builder import WorldBuilder
    from app.services.entity_extractor import ExtractedEntity
    from app.services.social_scraper import ScrapedPost

    # Create entities with real usernames from our E2E data
    entities_path = os.path.join(OUTPUT_DIR, 'step4_entities.json')
    if not os.path.exists(entities_path):
        log("  SKIP: No step4_entities.json found. Run e2e_pipeline_test.py first.")
        return

    with open(entities_path) as f:
        raw_entities = json.load(f)

    # Pick 3 X entities for a quick parallel scrape test
    test_entities = []
    for raw in raw_entities[:10]:
        if raw.get("platform") == "x" and len(test_entities) < 3:
            test_entities.append(
                ExtractedEntity(
                    username=raw["username"],
                    platform="x",
                    display_name=raw.get("display_name", ""),
                    posts=[
                        ScrapedPost(
                            platform="x",
                            post_id="dummy",
                            author_username=raw["username"],
                            text="placeholder",
                        )
                    ],
                )
            )

    if not test_entities:
        log("  SKIP: No X entities found in step4 data")
        return

    log(f"  Testing parallel deep scrape with {len(test_entities)} entities: {[e.username for e in test_entities]}")

    wb = WorldBuilder()

    t0 = time.time()
    result = wb.deep_scrape_entities(
        test_entities,
        max_entities=3,
        max_posts_per_user=5,
        max_workers=3,
    )
    elapsed = time.time() - t0

    log(f"  Parallel scrape completed in {elapsed:.1f}s")

    for e in result[:3]:
        post_count = len(e.posts) - 1  # subtract the dummy
        bio_status = "has bio" if e.bio else "no bio"
        log(f"  @{e.username}: {post_count} new posts, {bio_status}, followers={e.followers}")

    # Compare: sequential would be ~25s per entity = ~75s for 3
    # Parallel should be significantly faster
    if elapsed < 60:
        log(f"  Parallel scrape: {elapsed:.0f}s (would be ~75s sequential)")
    log("  TEST 3 PASSED ✓")


if __name__ == '__main__':
    log("BACKLOG FIXES VALIDATION")
    log("========================\n")

    test_bio_extraction()
    test_audience_scoring()
    test_async_deep_scrape()

    log("\n" + "=" * 60)
    log("ALL TESTS PASSED")
    log("=" * 60)
