from src.plugins.base import ActionPlugin
from src.models import ActionResult
import httpx
from src.config import Config

class LinkedInPlugin(ActionPlugin):
    name = "linkedin"
    
    async def execute(self, params: dict, memory, user_id: str) -> ActionResult:
        content = params.get("content", "")
        # Retrieve user's LinkedIn style preference
        prefs = await memory.retrieve_preferences(user_id, "linkedin post style", top_k=1)
        if prefs:
            style = prefs[0]["metadata"].get("style", "")
            content = f"{content}\n\n{style}"   # simplistic
        
        # Call LinkedIn API (mock)
        # In real: use requests with access token
        async with httpx.AsyncClient() as client:
            resp = await client.post(
                "https://api.linkedin.com/v2/ugcPosts",
                headers={"Authorization": f"Bearer {Config.LINKEDIN_ACCESS_TOKEN}"},
                json={"author": "urn:li:person:abc", "lifecycleState": "PUBLISHED", "specificContent": {"com.linkedin.ugc.ShareContent": {"shareCommentary": {"text": content}, "shareMediaCategory": "NONE"}}}
            )
            if resp.status_code == 201:
                return ActionResult(success=True, message="Posted to LinkedIn", data={"post_id": resp.json().get("id")})
            else:
                raise Exception(f"LinkedIn API error: {resp.text}")
