from typing import Optional, Dict, Any
from fastapi import Request

def get_current_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Retrieves the current user from the session.
    """
    user = request.session.get("user")
    if not user:
        return None
    return user
