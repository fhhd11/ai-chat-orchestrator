"""Supabase Edge Functions client"""

import json
import asyncio
from typing import Dict, Optional, List
import httpx
from loguru import logger

from ..config import Settings
from ..models import EdgeFunctionResponse, UserProfile
from ..utils.errors import EdgeFunctionError, ServiceUnavailableError


class SupabaseClient:
    """Client for interacting with Supabase Edge Functions and REST API"""
    
    def __init__(self, settings: Settings):
        self.base_url = settings.edge_function_url
        self.supabase_url = settings.supabase_url
        self.anon_key = settings.supabase_anon_key
        self.service_key = settings.supabase_service_key
        
        self.client = httpx.AsyncClient(
            timeout=30.0,
            limits=httpx.Limits(max_connections=100)
        )
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def call_edge_function(
        self, 
        endpoint: str, 
        data: dict, 
        user_token: str,
        retries: int = 3
    ) -> dict:
        """
        Universal method for calling Edge Functions with retry logic and error handling
        
        Args:
            endpoint: Edge function endpoint (e.g., 'add-message')
            data: Request payload
            user_token: User JWT token
            retries: Number of retry attempts
            
        Returns:
            Response data from edge function
            
        Raises:
            EdgeFunctionError: If edge function returns an error
            ServiceUnavailableError: If service is unavailable after retries
        """
        url = f"{self.base_url}/{endpoint}"
        headers = {
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json"
        }
        
        for attempt in range(retries + 1):
            try:
                logger.info(f"Calling Edge Function: {endpoint}, attempt {attempt + 1}")
                
                response = await self.client.post(
                    url,
                    json=data,
                    headers=headers
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get("success"):
                        logger.info(f"Edge Function {endpoint} succeeded")
                        return result["data"]
                    else:
                        error_msg = result.get("error", "Unknown error")
                        logger.error(f"Edge Function {endpoint} failed: {error_msg}")
                        raise EdgeFunctionError(
                            message=f"Edge function error: {error_msg}",
                            code="EDGE_FUNCTION_ERROR",
                            details={"endpoint": endpoint, "error": error_msg}
                        )
                
                elif response.status_code == 401:
                    raise EdgeFunctionError(
                        message="Authentication failed",
                        code="AUTHENTICATION_ERROR",
                        details={"endpoint": endpoint, "status_code": 401}
                    )
                
                elif response.status_code == 404:
                    raise EdgeFunctionError(
                        message="Conversation not found or access denied",
                        code="NOT_FOUND_ERROR",
                        details={"endpoint": endpoint, "status_code": 404}
                    )
                
                else:
                    if attempt < retries:
                        wait_time = 2 ** attempt  # Exponential backoff
                        logger.warning(f"Edge Function {endpoint} failed with status {response.status_code}, retrying in {wait_time}s")
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        raise EdgeFunctionError(
                            message=f"Edge function failed with status {response.status_code}",
                            code="HTTP_ERROR",
                            details={"endpoint": endpoint, "status_code": response.status_code}
                        )
                        
            except httpx.RequestError as e:
                if attempt < retries:
                    wait_time = 2 ** attempt
                    logger.warning(f"Edge Function {endpoint} request failed: {e}, retrying in {wait_time}s")
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Edge Function {endpoint} failed after {retries} retries: {e}")
                    raise ServiceUnavailableError(
                        message=f"Service unavailable: {str(e)}",
                        code="SERVICE_UNAVAILABLE",
                        details={"endpoint": endpoint, "error": str(e)}
                    )
        
        raise ServiceUnavailableError(
            message="Max retries exceeded",
            code="MAX_RETRIES_EXCEEDED",
            details={"endpoint": endpoint}
        )
    
    async def add_message(
        self, 
        user_token: str,
        conversation_id: Optional[str] = None,
        content: str = "",
        role: str = "user",
        parent_id: Optional[str] = None
    ) -> dict:
        """Add message to conversation"""
        data = {
            "conversation_id": conversation_id,
            "content": content,
            "role": role,
            "parent_id": parent_id
        }
        return await self.call_edge_function("add-message", data, user_token)
    
    async def build_context(
        self,
        user_token: str,
        conversation_id: str,
        branch_id: Optional[str] = None,
        max_messages: int = 50
    ) -> dict:
        """Build conversation context"""
        data = {
            "conversation_id": conversation_id,
            "branch_id": branch_id,
            "max_messages": max_messages
        }
        return await self.call_edge_function("build-context", data, user_token)
    
    async def save_response(
        self,
        user_token: str,
        conversation_id: str,
        branch_id: str,
        parent_id: str,
        content: str,
        model: str,
        tokens_count: Optional[int] = None
    ) -> dict:
        """Save assistant response"""
        data = {
            "conversation_id": conversation_id,
            "branch_id": branch_id,
            "parent_id": parent_id,
            "content": content,
            "model": model,
            "tokens_count": tokens_count
        }
        return await self.call_edge_function("save-response", data, user_token)
    
    async def create_branch(
        self,
        user_token: str,
        conversation_id: str,
        from_message_id: str,
        name: Optional[str] = None
    ) -> dict:
        """Create new branch for regeneration"""
        data = {
            "conversation_id": conversation_id,
            "from_message_id": from_message_id,
            "name": name
        }
        return await self.call_edge_function("create-branch", data, user_token)
    
    async def get_user_profile(self, user_id: str, user_token: str) -> UserProfile:
        """Get user profile from Supabase REST API"""
        try:
            url = f"{self.supabase_url}/rest/v1/user_profiles"
            headers = {
                "Authorization": f"Bearer {user_token}",
                "apikey": self.anon_key,
                "Content-Type": "application/json"
            }
            params = {"id": f"eq.{user_id}"}
            
            logger.info(f"Getting user profile for user_id: {user_id}")
            
            response = await self.client.get(url, headers=headers, params=params)
            
            if response.status_code == 200:
                profiles = response.json()
                if profiles:
                    profile_data = profiles[0]
                    return UserProfile(**profile_data)
                else:
                    raise EdgeFunctionError(
                        message="User profile not found",
                        code="USER_NOT_FOUND",
                        details={"user_id": user_id}
                    )
            else:
                raise EdgeFunctionError(
                    message=f"Failed to get user profile: {response.status_code}",
                    code="USER_PROFILE_ERROR",
                    details={"user_id": user_id, "status_code": response.status_code}
                )
                
        except httpx.RequestError as e:
            logger.error(f"Failed to get user profile: {e}")
            raise ServiceUnavailableError(
                message=f"Failed to get user profile: {str(e)}",
                code="SERVICE_UNAVAILABLE",
                details={"user_id": user_id, "error": str(e)}
            )