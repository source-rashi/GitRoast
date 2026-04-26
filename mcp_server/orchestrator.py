"""
GitRoast — Session Orchestrator
=================================
Manages session state across a conversation.
Caches DeveloperProfiles so follow-up questions don't re-fetch GitHub.
Handles multi-turn conversation history for Groq.

Max history: 20 messages (trims oldest to avoid token overflow)
"""

from typing import Optional, TYPE_CHECKING
from loguru import logger

from mcp_server.tools.github_scraper import DeveloperProfile
from mcp_server.personality.engine import PersonalityEngine

if TYPE_CHECKING:
    from mcp_server.tools.idea_debater import DebateResult

MAX_HISTORY_LENGTH = 20


class GitRoastOrchestrator:
    """Manages session state, profile caching, and conversation history."""

    def __init__(self, groq_client):
        self.groq_client = groq_client
        self.session_profiles: dict[str, DeveloperProfile] = {}
        self.current_personality: str = "comedian"
        self.conversation_history: list[dict] = []
        self.current_username: Optional[str] = None
        self.last_debate_result: Optional["DebateResult"] = None
        logger.info("GitRoastOrchestrator initialized.")

    # ------------------------------------------------------------------
    # Profile caching
    # ------------------------------------------------------------------

    async def get_or_fetch_profile(
        self, username: str, scraper, force_refresh: bool = False
    ) -> DeveloperProfile:
        """Return cached profile or fetch fresh data from GitHub."""
        key = username.lower()

        # Clear conversation history when switching to a different user
        if self.current_username and self.current_username != key:
            self.conversation_history.clear()
            logger.info(f"Switched user from {self.current_username} to {key}, cleared history.")

        if key in self.session_profiles and not force_refresh:
            logger.info(f"Using cached profile for {username}")
            return self.session_profiles[key]

        logger.info(f"Fetching fresh profile for {username} from GitHub...")
        profile = await scraper.scrape_developer(username)
        self.session_profiles[key] = profile
        self.current_username = key
        return profile

    # ------------------------------------------------------------------
    # Follow-up questions
    # ------------------------------------------------------------------

    async def answer_followup(self, question: str) -> str:
        """Answer a follow-up question about the current developer."""
        if not self.current_username:
            return (
                "No developer has been analyzed yet. "
                "Ask me to analyze a GitHub username first!"
            )

        profile = self.session_profiles[self.current_username]
        system_message = {
            "role": "system",
            "content": (
                f"You are GitRoast. You have already analyzed {self.current_username}'s "
                "GitHub profile. Answer follow-up questions using the profile data. "
                f"Be in {self.current_personality} mode."
            ),
        }

        self.conversation_history.append({"role": "user", "content": question})

        # Trim history to avoid token overflow
        while len(self.conversation_history) > MAX_HISTORY_LENGTH:
            self.conversation_history.pop(0)
            if self.conversation_history:
                self.conversation_history.pop(0)

        messages = [system_message] + self.conversation_history

        response = self.groq_client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=messages,
        )

        reply = response.choices[0].message.content
        self.conversation_history.append({"role": "assistant", "content": reply})
        return reply

    # ------------------------------------------------------------------
    # Personality management
    # ------------------------------------------------------------------

    def set_personality(self, personality: str, engine: PersonalityEngine) -> str:
        """Switch the roast personality for this session."""
        engine.validate_personality(personality)
        self.current_personality = personality
        description = engine.get_personality_description(personality)
        return f"Personality switched to **{personality}** mode. {description}"

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def clear_session(self) -> str:
        """Clear all session data."""
        self.session_profiles.clear()
        self.conversation_history.clear()
        self.current_username = None
        self.current_personality = "comedian"
        logger.info("Session cleared.")
        return "Session cleared. Fresh roast incoming."

    def get_session_summary(self) -> str:
        """Return a markdown summary of the current session state."""
        cached = (
            ", ".join(f"`{u}`" for u in self.session_profiles.keys())
            if self.session_profiles
            else "None yet"
        )
        current = f"`{self.current_username}`" if self.current_username else "None"
        return (
            "## 📊 GitRoast Session Summary\n\n"
            f"- **Current personality:** `{self.current_personality}`\n"
            f"- **Cached profiles:** {cached}\n"
            f"- **Conversation length:** {len(self.conversation_history)} messages\n"
            f"- **Currently analyzing:** {current}\n"
        )
