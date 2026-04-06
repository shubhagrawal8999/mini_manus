from pydantic import BaseModel
from typing import Dict, Any, Optional
from enum import Enum

class IntentType(str, Enum):
    POST_LINKEDIN = "post_linkedin"
    SEND_EMAIL = "send_email"
    DEEP_SEARCH = "deep_search"
    SNAPSHOT = "snapshot"
    UNKNOWN = "unknown"

class UserMessage(BaseModel):
    user_id: str
    text: str

class ActionResult(BaseModel):
    success: bool
    message: str
    data: Optional[Dict[str, Any]] = None
    error_signature: Optional[str] = None
