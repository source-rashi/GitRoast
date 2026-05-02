"""
GitRoast — Webhook Notifier (Phase 5)
========================================
Send GitRoast results to Slack, Discord, or any webhook-compatible service.

Supported platforms:
- Slack (Incoming Webhooks)
- Discord (Webhook URLs)
- Generic (any URL accepting POST with JSON)

Converts Markdown output into platform-specific formats:
- Slack: Block Kit JSON with sections + dividers
- Discord: Embed objects with color-coded fields
- Generic: Raw Markdown text in a JSON payload

No paid APIs required. Just a webhook URL.
"""

import re
import httpx
from typing import Optional
from pydantic import BaseModel
from loguru import logger


# ---------------------------------------------------------------------------
# Pydantic Models
# ---------------------------------------------------------------------------

class WebhookResult(BaseModel):
    success: bool = False
    platform: str = "unknown"
    status_code: int = 0
    message: str = ""


# ---------------------------------------------------------------------------
# Platform detection
# ---------------------------------------------------------------------------

def detect_platform(url: str) -> str:
    """Detect webhook platform from URL."""
    if "hooks.slack.com" in url:
        return "slack"
    elif "discord.com/api/webhooks" in url or "discordapp.com/api/webhooks" in url:
        return "discord"
    return "generic"


# ---------------------------------------------------------------------------
# Formatting helpers
# ---------------------------------------------------------------------------

def _truncate(text: str, max_len: int = 2000) -> str:
    """Truncate text to fit platform limits."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."


def _extract_title(content: str) -> str:
    """Extract the first heading from markdown content."""
    for line in content.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return "GitRoast Report"


def _md_to_plain(text: str) -> str:
    """Very basic markdown to plain text conversion."""
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)   # bold
    text = re.sub(r"\*(.*?)\*", r"\1", text)        # italic
    text = re.sub(r"`(.*?)`", r"\1", text)          # code
    text = re.sub(r"#{1,6}\s*", "", text)            # headings
    return text


# ---------------------------------------------------------------------------
# Slack formatter
# ---------------------------------------------------------------------------

def _format_slack(content: str, title: str) -> dict:
    """Format content as Slack Block Kit payload."""
    content = _truncate(content, 2800)

    blocks = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"🔥 {title}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": content,
            },
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {
                    "type": "mrkdwn",
                    "text": "Sent by *GitRoast* — AI Developer Intelligence • 100% Free",
                }
            ],
        },
    ]

    return {"blocks": blocks}


# ---------------------------------------------------------------------------
# Discord formatter
# ---------------------------------------------------------------------------

def _format_discord(content: str, title: str) -> dict:
    """Format content as Discord webhook embed payload."""
    content = _truncate(content, 3500)

    # Pick color based on content type
    color = 0xFF6B35  # GitRoast orange
    if "roast" in title.lower() or "🔥" in title:
        color = 0xFF4444  # Red
    elif "quality" in title.lower() or "🔬" in title:
        color = 0x6495ED  # Blue
    elif "debate" in title.lower() or "⚖️" in title:
        color = 0xFFAA00  # Gold
    elif "team" in title.lower() or "👥" in title:
        color = 0x8B5CF6  # Purple

    embed = {
        "title": f"🔥 {title}",
        "description": content,
        "color": color,
        "footer": {
            "text": "GitRoast — AI Developer Intelligence • 100% Free",
        },
    }

    return {"embeds": [embed]}


# ---------------------------------------------------------------------------
# Generic formatter
# ---------------------------------------------------------------------------

def _format_generic(content: str, title: str) -> dict:
    """Format content as a generic JSON payload."""
    return {
        "title": title,
        "text": content,
        "source": "GitRoast",
    }


# ---------------------------------------------------------------------------
# WebhookNotifier
# ---------------------------------------------------------------------------

class WebhookNotifier:
    """Sends GitRoast results to external webhook services."""

    TIMEOUT = 15  # seconds

    async def send(
        self,
        webhook_url: str,
        content: str,
        title: Optional[str] = None,
    ) -> WebhookResult:
        """Send content to a webhook URL.

        Args:
            webhook_url: The webhook endpoint URL.
            content: Markdown-formatted content to send.
            title: Optional title override. Auto-detected from content if None.
        """
        if not webhook_url or not webhook_url.startswith("http"):
            return WebhookResult(
                success=False,
                message="Invalid webhook URL. Must start with http:// or https://",
            )

        if not content or not content.strip():
            return WebhookResult(
                success=False,
                message="No content to send.",
            )

        platform = detect_platform(webhook_url)
        title = title or _extract_title(content)

        # Format payload based on platform
        if platform == "slack":
            payload = _format_slack(content, title)
        elif platform == "discord":
            payload = _format_discord(content, title)
        else:
            payload = _format_generic(content, title)

        # Send
        try:
            async with httpx.AsyncClient(timeout=self.TIMEOUT) as client:
                response = await client.post(webhook_url, json=payload)

            success = response.status_code in (200, 201, 204)

            if success:
                logger.info(f"Webhook sent to {platform}: {response.status_code}")
            else:
                logger.warning(
                    f"Webhook failed for {platform}: {response.status_code} — {response.text[:200]}"
                )

            return WebhookResult(
                success=success,
                platform=platform,
                status_code=response.status_code,
                message=(
                    f"✅ Sent to {platform.title()}!"
                    if success
                    else f"❌ Failed ({response.status_code}): {response.text[:200]}"
                ),
            )

        except httpx.TimeoutException:
            return WebhookResult(
                success=False,
                platform=platform,
                message=f"❌ Webhook timed out after {self.TIMEOUT}s",
            )
        except Exception as exc:
            logger.exception(f"Webhook send failed: {exc}")
            return WebhookResult(
                success=False,
                platform=platform,
                message=f"❌ Webhook error: {exc}",
            )

    def format_send_result(self, result: WebhookResult) -> str:
        """Format the webhook result for user display."""
        if result.success:
            return (
                f"## 🔔 Webhook Sent Successfully\n\n"
                f"- **Platform:** {result.platform.title()}\n"
                f"- **Status:** {result.status_code}\n\n"
                f"{result.message}"
            )
        else:
            return (
                f"## 🔔 Webhook Failed\n\n"
                f"- **Platform:** {result.platform.title()}\n"
                f"- **Error:** {result.message}\n\n"
                "**Troubleshooting:**\n"
                "- Check that the webhook URL is valid and active\n"
                "- Slack: Create at api.slack.com/messaging/webhooks\n"
                "- Discord: Server Settings → Integrations → Webhooks\n"
            )
