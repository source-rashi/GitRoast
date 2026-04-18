"""
GitRoast — Tests for Personality Engine
=========================================
Covers all 5 personalities, wrapping, validation, and metadata.
"""

import pytest
from mcp_server.personality.engine import PersonalityEngine, VALID_PERSONALITIES


@pytest.fixture
def engine():
    return PersonalityEngine()


# ---------------------------------------------------------------------------
# Wrapping tests
# ---------------------------------------------------------------------------

def test_all_personalities_wrap_content(engine):
    """wrap_response should include the original text for all 5 personalities."""
    for personality in VALID_PERSONALITIES:
        result = engine.wrap_response("hello", personality)
        assert "hello" in result, f"Missing content for personality '{personality}'"


def test_comedian_signoff_contains_mic(engine):
    """Comedian sign-off should reference the iconic mic drop."""
    result = engine.wrap_response("test", "comedian")
    assert "mic" in result.lower()


def test_yc_founder_signoff_contains_sf(engine):
    """YC Founder sign-off should reference SF or a flight."""
    result = engine.wrap_response("test", "yc_founder")
    assert "SF" in result or "flight" in result


def test_invalid_personality_raises_value_error(engine):
    """Passing an unrecognized personality should raise ValueError."""
    with pytest.raises(ValueError) as exc_info:
        engine.validate_personality("clown")
    assert "clown" in str(exc_info.value)
    assert "Valid options" in str(exc_info.value)


def test_personality_header_present(engine):
    """Each personality's output should start with its designated emoji."""
    emoji_map = {
        "comedian": "🎤",
        "yc_founder": "🚀",
        "senior_dev": "😤",
        "zen_mentor": "🧘",
        "stranger": "👻",
    }
    for personality, emoji in emoji_map.items():
        result = engine.wrap_response("body text", personality)
        assert result.startswith(emoji), (
            f"Personality '{personality}' should start with '{emoji}'"
        )


# ---------------------------------------------------------------------------
# List and description tests
# ---------------------------------------------------------------------------

def test_list_personalities_returns_five(engine):
    """list_personalities should return exactly 5 entries."""
    personalities = engine.list_personalities()
    assert len(personalities) == 5


def test_list_personalities_have_required_keys(engine):
    """Every personality entry must include id, name, emoji, description."""
    for p in engine.list_personalities():
        assert "id" in p
        assert "name" in p
        assert "emoji" in p
        assert "description" in p
        assert p["id"] in VALID_PERSONALITIES


def test_get_personality_description_all_modes(engine):
    """Every personality mode should return a non-empty description string."""
    for personality in VALID_PERSONALITIES:
        desc = engine.get_personality_description(personality)
        assert isinstance(desc, str)
        assert len(desc) > 10, f"Description for '{personality}' is too short"


def test_wrap_response_invalid_raises(engine):
    """wrap_response with bad personality should raise ValueError."""
    with pytest.raises(ValueError):
        engine.wrap_response("hello", "robot")


def test_validate_personality_returns_valid(engine):
    """validate_personality should return the personality string when valid."""
    for p in VALID_PERSONALITIES:
        assert engine.validate_personality(p) == p
