"""
LinkedIn posting via the official LinkedIn API v2.

SETUP (one-time):
  1. Go to https://www.linkedin.com/developers/apps → Create App.
  2. Add the "Share on LinkedIn" and "Sign In with LinkedIn" products.
  3. Under "Auth", copy your Client ID and Client Secret.
  4. Generate an access token via OAuth 2.0 (3-legged) OR use the
     LinkedIn token generator tool in the developer portal for a
     60-day personal token.
  5. Add to your .env:
       LINKEDIN_ACCESS_TOKEN=AQV...
       LINKEDIN_PERSON_URN=urn:li:person:XXXXXXXX   ← from /v2/me

HOW TO GET YOUR PERSON URN:
  curl -H "Authorization: Bearer <token>" https://api.linkedin.com/v2/me
  → copy the "id" field, format it as  urn:li:person:<id>

TOKEN REFRESH:
  LinkedIn tokens expire in 60 days.  Implement OAuth refresh flow for
  production, or rotate the token manually for personal use.

TEMPLATES PROVIDED:
  - professional_update   : career / project announcement
  - thought_leadership    : opinion / insight post
  - engagement_hook       : question-based post for comments
  - none                  : raw body, no wrapper
"""

import asyncio
import json
import os
from typing import Literal

import aiohttp

from bot.tools.base import Tool, ToolResult

LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
TIMEOUT = aiohttp.ClientTimeout(total=15)


class LinkedInTool(Tool):
    name = "post_linkedin"
    description = (
        "Post a text update to LinkedIn on your behalf. "
        "Supports templates: professional_update, thought_leadership, "
        "engagement_hook, or a raw custom post. "
        "Requires LINKEDIN_ACCESS_TOKEN and LINKEDIN_PERSON_URN."
    )

    parameters = {
        "type": "object",
        "properties": {
            "content": {
                "type": "string",
                "description": "The main body of the LinkedIn post.",
            },
            "template": {
                "type": "string",
                "enum": [
                    "professional_update",
                    "thought_leadership",
                    "engagement_hook",
                    "none",
                ],
                "description": "Optional template to style the post.",
            },
            "hashtags": {
                "type": "array",
                "items": {"type": "string"},
                "description": (
                    "Optional list of hashtags to append, e.g. ['AI', 'Startup']. "
                    "Do NOT include the # symbol — it will be added automatically."
                ),
            },
        },
        "required": ["content"],
    }

    def __init__(self):
        self._token = os.getenv("LINKEDIN_ACCESS_TOKEN", "")
        self._person_urn = os.getenv("LINKEDIN_PERSON_URN", "")
        self._setup_error = ""

        if not self._token:
            self._setup_error = "LINKEDIN_ACCESS_TOKEN not set."
        elif not self._person_urn:
            self._setup_error = "LINKEDIN_PERSON_URN not set."

    # ──────────────────────────────────────────────────────────────────
    # Template helpers
    # ──────────────────────────────────────────────────────────────────
    @staticmethod
    def _apply_template(
        content: str,
        template: str,
        hashtags: list[str],
    ) -> str:
        tags_str = " ".join(f"#{tag.lstrip('#')}" for tag in hashtags) if hashtags else ""

        if template == "professional_update":
            post = (
                f"🚀 Excited to share an update!\n\n"
                f"{content}\n\n"
                f"Always grateful for the journey ahead. "
                f"Would love to hear your thoughts in the comments! 👇"
            )
        elif template == "thought_leadership":
            post = (
                f"💡 Here's something I've been thinking about:\n\n"
                f"{content}\n\n"
                f"What's your take? Drop a comment — I read every one."
            )
        elif template == "engagement_hook":
            post = (
                f"🤔 Quick question for my network:\n\n"
                f"{content}\n\n"
                f"Comment below — I'd love to know what you think! ♻️ Repost if this resonates."
            )
        else:
            post = content

        if tags_str:
            post = f"{post}\n\n{tags_str}"

        return post

    # ──────────────────────────────────────────────────────────────────
    # Core execution
    # ──────────────────────────────────────────────────────────────────
    async def execute(
        self,
        content: str,
        template: Literal[
            "professional_update", "thought_leadership", "engagement_hook", "none"
        ] = "none",
        hashtags: list[str] | None = None,
    ) -> ToolResult:

        if self._setup_error:
            return ToolResult(
                status="error",
                message=f"LinkedIn not configured: {self._setup_error}",
                error=self._setup_error,
                retryable=False,
            )

        final_text = self._apply_template(content, template, hashtags or [])

        # LinkedIn Share API v2 payload
        payload = {
            "author": self._person_urn,
            "lifecycleState": "PUBLISHED",
            "specificContent": {
                "com.linkedin.ugc.ShareContent": {
                    "shareCommentary": {"text": final_text},
                    "shareMediaCategory": "NONE",
                }
            },
            "visibility": {
                "com.linkedin.ugc.MemberNetworkVisibility": "PUBLIC"
            },
        }

        headers = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        def _post_blocking():
            """Synchronous fallback using urllib (no extra deps)."""
            import urllib.request
            data = json.dumps(payload).encode()
            req = urllib.request.Request(
                f"{LINKEDIN_API_BASE}/ugcPosts",
                data=data,
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=15) as resp:
                return resp.status, resp.read().decode()

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    f"{LINKEDIN_API_BASE}/ugcPosts",
                    headers=headers,
                    json=payload,
                    timeout=TIMEOUT,
                ) as resp:
                    body = await resp.text()

                    if resp.status in (200, 201):
                        post_id = json.loads(body).get("id", "unknown")
                        return ToolResult(
                            status="success",
                            message="✅ LinkedIn post published successfully!",
                            data={"post_id": post_id, "preview": final_text[:200]},
                        )

                    # Token expired
                    if resp.status == 401:
                        return ToolResult(
                            status="error",
                            message=(
                                "LinkedIn token expired or invalid. "
                                "Please refresh LINKEDIN_ACCESS_TOKEN."
                            ),
                            error=f"HTTP 401: {body}",
                            retryable=False,
                        )

                    return ToolResult(
                        status="error",
                        message=f"LinkedIn API error (HTTP {resp.status}): {body[:300]}",
                        error=body[:500],
                        retryable=resp.status >= 500,
                    )

        except Exception as exc:
            return ToolResult(
                status="error",
                message=f"LinkedIn post failed: {exc}",
                error=str(exc),
                retryable=True,
            )
