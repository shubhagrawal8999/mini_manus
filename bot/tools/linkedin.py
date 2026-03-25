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

LINKEDIN_API_BASE_V2 = "https://api.linkedin.com/v2"
LINKEDIN_API_BASE_REST = "https://api.linkedin.com/rest"
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

        # LinkedIn UGC v2 payload (legacy but still supported for many apps)
        payload_v2 = {
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

        headers_v2 = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        # LinkedIn REST Posts API payload (newer)
        payload_rest = {
            "author": self._person_urn,
            "commentary": final_text,
            "visibility": "PUBLIC",
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
            "isReshareDisabledByAuthor": False,
        }
        headers_rest = {
            "Authorization": f"Bearer {self._token}",
            "Content-Type": "application/json",
            "LinkedIn-Version": "202401",
            "X-Restli-Protocol-Version": "2.0.0",
        }

        try:
            async with aiohttp.ClientSession() as session:
                # Try REST endpoint first
                async with session.post(
                    f"{LINKEDIN_API_BASE_REST}/posts",
                    headers=headers_rest,
                    json=payload_rest,
                    timeout=TIMEOUT,
                ) as resp:
                    body = await resp.text()
                    if resp.status in (200, 201):
                        parsed = json.loads(body) if body.strip() else {}
                        post_id = parsed.get("id", "unknown")
                        return ToolResult(
                            status="success",
                            message="✅ LinkedIn post published successfully!",
                            data={
                                "post_id": post_id,
                                "api_version": "rest/posts",
                                "preview": final_text[:200],
                            },
                        )
                    rest_error = f"REST /posts HTTP {resp.status}: {body[:300]}"

                # Fallback to v2 UGC endpoint
                async with session.post(
                    f"{LINKEDIN_API_BASE_V2}/ugcPosts",
                    headers=headers_v2,
                    json=payload_v2,
                    timeout=TIMEOUT,
                ) as resp:
                    body = await resp.text()
                    if resp.status in (200, 201):
                        parsed = json.loads(body) if body.strip() else {}
                        post_id = parsed.get("id", "unknown")
                        return ToolResult(
                            status="success",
                            message="✅ LinkedIn post published successfully!",
                            data={
                                "post_id": post_id,
                                "api_version": "v2/ugcPosts",
                                "preview": final_text[:200],
                            },
                        )
                    if resp.status == 401:
                        return ToolResult(
                            status="error",
                            message=(
                                "LinkedIn token expired or invalid. "
                                "Please refresh LINKEDIN_ACCESS_TOKEN."
                            ),
                            error=f"{rest_error} | v2/ugcPosts HTTP 401: {body[:300]}",
                            retryable=False,
                        )

                    return ToolResult(
                        status="error",
                        message="LinkedIn API rejected the request on both endpoints.",
                        error=f"{rest_error} | v2/ugcPosts HTTP {resp.status}: {body[:300]}",
                        retryable=resp.status >= 500,
                    )

        except Exception as exc:
            return ToolResult(
                status="error",
                message=f"LinkedIn post failed: {exc}",
                error=str(exc),
                retryable=True,
            )
