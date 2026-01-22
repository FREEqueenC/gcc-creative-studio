import os
import asyncio
from typing import Optional, Dict, Any
from fastapi import Request, HTTPException, status
from google.oauth2 import id_token
from google.auth.transport import requests as google_auth_requests
import firebase_admin
from firebase_admin import auth
from firebase_admin import credentials
from src.config.config_service import config_service # Import config_service

ENVIRONMENT = config_service.ENVIRONMENT

# Initialize Firebase Admin SDK if not already done
if ENVIRONMENT == "local" and not firebase_admin._apps:
    try:
        # Attempt to load default credentials. This works in many environments.
        cred = credentials.ApplicationDefault()
        firebase_admin.initialize_app(cred)
        print("Firebase Admin SDK initialized with Application Default Credentials.")
    except Exception as e:
        print(f"Failed to initialize Firebase Admin SDK with Application Default Credentials: {e}")
        # Fallback or alternative initialization can be added here if needed

import logging
logger = logging.getLogger(__name__)

async def get_session_user(request: Request) -> Optional[Dict[str, Any]]:
    """
    Retrieves the current user from the Authorization header (Bearer Token).
    Verifies the Google ID Token or Firebase ID Token based on environment.
    Returns the claims.
    """
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return None

    if not auth_header.startswith("Bearer "):
        return None

    token = auth_header.split(" ")[1]
    
    try:
        decoded_token = {}

        if ENVIRONMENT == "local":
            # --- Local: Use Firebase Auth ---  
            if not firebase_admin._apps:
                 logger.error("Firebase Admin SDK not initialized. Cannot verify token.")
                 raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Firebase Admin SDK not initialized."
                )
            logger.info("Verifying token using Firebase Admin SDK...")
            decoded_token = await asyncio.to_thread(auth.verify_id_token, token)
        else:
            # --- Development/Production: Use Google Identity Platform (OIDC) ---
            logger.info("Verifying token using Google OIDC...")
            GOOGLE_TOKEN_AUDIENCE = config_service.GOOGLE_TOKEN_AUDIENCE
            if not GOOGLE_TOKEN_AUDIENCE:
                logger.error("GOOGLE_TOKEN_AUDIENCE not set. Cannot verify token.")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="GOOGLE_TOKEN_AUDIENCE not set."
                )
                
            decoded_token = await asyncio.to_thread(
                id_token.verify_oauth2_token,
                token,
                google_auth_requests.Request(),
                audience=GOOGLE_TOKEN_AUDIENCE,
            )
        
        return decoded_token

    except auth.ExpiredIdTokenError:
        logger.error("[get_session_user - auth.ExpiredIdTokenError]")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication token has expired.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except auth.InvalidIdTokenError as e:
        logger.error(f"[get_session_user - auth.InvalidIdTokenError]: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid authentication token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except ValueError as e:
        # Invalid token from id_token.verify_oauth2_token
        logger.error(f"[get_session_user - ValueError]: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Google ID token: {e}",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except HTTPException as e: # Re-raise HTTPExceptions
        raise e
    except Exception as e:
        logger.error(f"[get_session_user - Exception]: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An unexpected error occurred during token verification: {e}",
        )
