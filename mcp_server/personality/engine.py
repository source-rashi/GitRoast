"""
GitRoast — Personality Engine
================================
Wraps every tool response in the chosen persona voice.
Every word the user reads comes through this engine.

Personalities:
- comedian: Stand-up roast energy, crowd work, punchlines, mic drops
- yc_founder: Intense startup energy, market questions, "why now?", metrics
- senior_dev: Tired, seen-it-all, zero tolerance for bad code, sardonic
- zen_mentor: Tough love, patient, growth-focused, mindful but direct
- stranger: Unfiltered, chaotic, weirdly specific, oddly accurate
"""

from loguru import logger


VALID_PERSONALITIES = ["comedian", "yc_founder", "senior_dev", "zen_mentor", "stranger"]

PERSONALITY_HEADERS = {
    "comedian": (
        "🎤 *[GitRoast — Stand-up Comedian Mode]*\n"
        "*adjusts mic* Alright, let's talk about this GitHub profile...\n\n"
    ),
    "yc_founder": (
        "🚀 *[GitRoast — YC Co-Founder Mode]*\n"
        "Okay I've looked at the metrics. Let me be direct with you.\n\n"
    ),
    "senior_dev": (
        "😤 *[GitRoast — Senior Dev Mode]*\n"
        "*sighs deeply and pulls up your profile*\n"
        "Alright. Let's go through this.\n\n"
    ),
    "zen_mentor": (
        "🧘 *[GitRoast — Zen Mentor Mode]*\n"
        "*takes a breath* I've reviewed your work with care. Here is what I see.\n\n"
    ),
    "stranger": (
        "👻 *[GitRoast — Anonymous Stranger Mode]*\n"
        "I don't know you. I've looked at your code. I have thoughts.\n\n"
    ),
}

PERSONALITY_SIGNOFFS = {
    "comedian": (
        "\n\n---\n"
        "*— GitRoast 🎤 drops mic*\n"
        "*crowd goes wild*"
    ),
    "yc_founder": (
        "\n\n---\n"
        "*— GitRoast 🚀 books next flight to SF*\n"
        "*sends calendar invite titled 'Tough Love'*"
    ),
    "senior_dev": (
        "\n\n---\n"
        "*— GitRoast 😤 returns to standing desk*\n"
        "*goes back to reviewing 10-year-old codebase*"
    ),
    "zen_mentor": (
        "\n\n---\n"
        "*— GitRoast 🧘 returns to meditation*\n"
        "*lights incense*"
    ),
    "stranger": (
        "\n\n---\n"
        "*— GitRoast 👻 vanishes into the void*\n"
        "*was never here*"
    ),
}


class PersonalityEngine:
    """Wraps LLM output in a chosen persona voice."""

    def __init__(self):
        logger.info("PersonalityEngine initialized.")

    def validate_personality(self, personality: str) -> str:
        """Raise ValueError if personality is not recognized."""
        if personality not in VALID_PERSONALITIES:
            valid = ", ".join(f"'{p}'" for p in VALID_PERSONALITIES)
            raise ValueError(
                f"Unknown personality '{personality}'. "
                f"Valid options are: {valid}"
            )
        return personality

    def wrap_response(self, text: str, personality: str) -> str:
        """Wrap text with the header and sign-off for a personality."""
        self.validate_personality(personality)
        return PERSONALITY_HEADERS[personality] + text + PERSONALITY_SIGNOFFS[personality]

    def get_personality_description(self, personality: str) -> str:
        """Return a one-sentence description of a personality mode."""
        self.validate_personality(personality)
        descriptions = {
            "comedian": (
                "Brutal roast energy — every flaw becomes a punchline, "
                "every win gets a round of applause."
            ),
            "yc_founder": (
                "Startup intensity — your code is a product, your GitHub is a pitch deck, "
                "and right now it's not fundable."
            ),
            "senior_dev": (
                "Tired veteran energy — they've seen your mistakes before, in 2009, "
                "and they're disappointed it's still happening."
            ),
            "zen_mentor": (
                "Tough love with patience — honest about your gaps, "
                "genuinely invested in your growth."
            ),
            "stranger": (
                "Unfiltered chaos — somehow knows exactly what's wrong "
                "and says it in the most unexpected way."
            ),
        }
        return descriptions[personality]

    def list_personalities(self) -> list[dict]:
        """Return metadata for all available personalities."""
        return [
            {
                "id": "comedian",
                "name": "Stand-up Comedian",
                "emoji": "🎤",
                "description": self.get_personality_description("comedian"),
            },
            {
                "id": "yc_founder",
                "name": "YC Co-Founder",
                "emoji": "🚀",
                "description": self.get_personality_description("yc_founder"),
            },
            {
                "id": "senior_dev",
                "name": "Senior Developer",
                "emoji": "😤",
                "description": self.get_personality_description("senior_dev"),
            },
            {
                "id": "zen_mentor",
                "name": "Zen Mentor",
                "emoji": "🧘",
                "description": self.get_personality_description("zen_mentor"),
            },
            {
                "id": "stranger",
                "name": "Anonymous Stranger",
                "emoji": "👻",
                "description": self.get_personality_description("stranger"),
            },
        ]
