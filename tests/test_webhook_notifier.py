"""
Tests for WebhookNotifier — Phase 5
"""
import pytest
from mcp_server.tools.webhook_notifier import (
    WebhookNotifier,
    WebhookResult,
    detect_platform,
    _format_slack,
    _format_discord,
    _format_generic,
    _extract_title,
    _truncate,
    _md_to_plain,
)


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

class TestDetectPlatform:
    def test_slack_detected(self):
        assert detect_platform("https://hooks.slack.com/services/T00/B00/xxx") == "slack"

    def test_discord_detected(self):
        assert detect_platform("https://discord.com/api/webhooks/123/abc") == "discord"

    def test_discordapp_detected(self):
        assert detect_platform("https://discordapp.com/api/webhooks/123/abc") == "discord"

    def test_generic_for_unknown(self):
        assert detect_platform("https://example.com/webhook") == "generic"

    def test_empty_url(self):
        assert detect_platform("") == "generic"


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

class TestExtractTitle:
    def test_extracts_h1(self):
        assert _extract_title("# My Report\n\nContent here") == "My Report"

    def test_extracts_h2(self):
        assert _extract_title("## Sub Report\n\nContent here") == "Sub Report"

    def test_fallback_when_no_heading(self):
        assert _extract_title("Just some text") == "GitRoast Report"

    def test_handles_emoji_in_heading(self):
        title = _extract_title("# 🔥 Roast Report\n\nContent")
        assert "Roast Report" in title


# ---------------------------------------------------------------------------
# Truncation
# ---------------------------------------------------------------------------

class TestTruncate:
    def test_short_text_unchanged(self):
        assert _truncate("hello", 100) == "hello"

    def test_long_text_truncated(self):
        result = _truncate("a" * 200, 100)
        assert len(result) == 100
        assert result.endswith("...")

    def test_exact_length_unchanged(self):
        text = "a" * 100
        assert _truncate(text, 100) == text


# ---------------------------------------------------------------------------
# Markdown to plain text
# ---------------------------------------------------------------------------

class TestMdToPlain:
    def test_strips_bold(self):
        assert _md_to_plain("**bold text**") == "bold text"

    def test_strips_italic(self):
        assert _md_to_plain("*italic*") == "italic"

    def test_strips_code(self):
        assert _md_to_plain("`code`") == "code"

    def test_strips_headings(self):
        assert _md_to_plain("## Heading").strip() == "Heading"


# ---------------------------------------------------------------------------
# Slack formatting
# ---------------------------------------------------------------------------

class TestSlackFormatting:
    def test_has_blocks(self):
        payload = _format_slack("Test content", "Test Title")
        assert "blocks" in payload
        assert len(payload["blocks"]) >= 2

    def test_header_block_has_title(self):
        payload = _format_slack("Content", "My Title")
        header = payload["blocks"][0]
        assert header["type"] == "header"
        assert "My Title" in header["text"]["text"]

    def test_section_block_has_content(self):
        payload = _format_slack("Some analysis here", "Title")
        section = payload["blocks"][1]
        assert section["type"] == "section"
        assert "analysis" in section["text"]["text"]

    def test_content_truncated_for_slack(self):
        long_content = "x" * 5000
        payload = _format_slack(long_content, "Title")
        section_text = payload["blocks"][1]["text"]["text"]
        assert len(section_text) <= 2800


# ---------------------------------------------------------------------------
# Discord formatting
# ---------------------------------------------------------------------------

class TestDiscordFormatting:
    def test_has_embeds(self):
        payload = _format_discord("Test content", "Test Title")
        assert "embeds" in payload
        assert len(payload["embeds"]) == 1

    def test_embed_has_title(self):
        payload = _format_discord("Content", "My Title")
        assert "My Title" in payload["embeds"][0]["title"]

    def test_embed_has_description(self):
        payload = _format_discord("Some content", "Title")
        assert "Some content" in payload["embeds"][0]["description"]

    def test_embed_has_color(self):
        payload = _format_discord("Content", "Title")
        assert "color" in payload["embeds"][0]

    def test_roast_gets_red_color(self):
        payload = _format_discord("Content", "🔥 Roast Report")
        assert payload["embeds"][0]["color"] == 0xFF4444

    def test_team_gets_purple_color(self):
        payload = _format_discord("Content", "👥 Team Report")
        assert payload["embeds"][0]["color"] == 0x8B5CF6


# ---------------------------------------------------------------------------
# Generic formatting
# ---------------------------------------------------------------------------

class TestGenericFormatting:
    def test_has_text(self):
        payload = _format_generic("Content", "Title")
        assert payload["text"] == "Content"

    def test_has_title(self):
        payload = _format_generic("Content", "My Title")
        assert payload["title"] == "My Title"

    def test_has_source(self):
        payload = _format_generic("Content", "Title")
        assert payload["source"] == "GitRoast"


# ---------------------------------------------------------------------------
# WebhookNotifier — validation
# ---------------------------------------------------------------------------

class TestWebhookNotifierValidation:
    @pytest.mark.asyncio
    async def test_rejects_invalid_url(self):
        notifier = WebhookNotifier()
        result = await notifier.send("not-a-url", "content")
        assert result.success is False
        assert "Invalid" in result.message

    @pytest.mark.asyncio
    async def test_rejects_empty_content(self):
        notifier = WebhookNotifier()
        result = await notifier.send("https://hooks.slack.com/test", "")
        assert result.success is False
        assert "No content" in result.message

    @pytest.mark.asyncio
    async def test_rejects_empty_url(self):
        notifier = WebhookNotifier()
        result = await notifier.send("", "Some content")
        assert result.success is False


# ---------------------------------------------------------------------------
# Format result
# ---------------------------------------------------------------------------

class TestFormatSendResult:
    def test_success_format(self):
        notifier = WebhookNotifier()
        result = WebhookResult(success=True, platform="slack", status_code=200, message="Sent!")
        text = notifier.format_send_result(result)
        assert "Successfully" in text
        assert "Slack" in text

    def test_failure_format(self):
        notifier = WebhookNotifier()
        result = WebhookResult(success=False, platform="discord", message="Connection refused")
        text = notifier.format_send_result(result)
        assert "Failed" in text
        assert "Troubleshooting" in text
