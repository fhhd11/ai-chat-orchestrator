"""Direct Supabase client for user profile operations"""

import httpx
from typing import Dict, Optional, Any
from loguru import logger

from ..config import settings
from ..utils.errors import ServiceUnavailableError


class SupabaseDirectClient:
    """Direct Supabase client for operations not available in Edge Functions"""
    
    def __init__(self):
        self.base_url = f"{settings.supabase_url}/rest/v1"
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0),
            headers={
                "apikey": settings.supabase_anon_key,
                "Content-Type": "application/json"
            }
        )
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    async def get_user_profile(self, user_id: str, user_token: str) -> Dict[str, Any]:
        """Get user profile directly from Supabase"""
        try:
            headers = {
                "Authorization": f"Bearer {user_token}",
                "apikey": settings.supabase_anon_key
            }
            
            response = await self.client.get(
                f"{self.base_url}/user_profiles?id=eq.{user_id}&select=*",
                headers=headers
            )
            
            if response.status_code == 200:
                data = response.json()
                if data:
                    return data[0]  # Return first (and only) result
                else:
                    # Create default profile if not exists
                    return await self._create_default_profile(user_id, user_token)
            else:
                logger.error(f"Failed to get user profile: {response.status_code} - {response.text}")
                raise ServiceUnavailableError(f"Failed to get user profile: {response.status_code}")
                
        except httpx.RequestError as e:
            logger.error(f"Request error getting user profile: {e}")
            raise ServiceUnavailableError(f"Failed to connect to user service: {str(e)}")
    
    async def _create_default_profile(self, user_id: str, user_token: str) -> Dict[str, Any]:
        """Create a default user profile"""
        try:
            headers = {
                "Authorization": f"Bearer {user_token}",
                "apikey": settings.supabase_anon_key,
                "Prefer": "return=representation"
            }
            
            profile_data = {
                "id": user_id,
                "spend": 0,
                "max_budget": 100,
                "litellm_key": None
            }
            
            response = await self.client.post(
                f"{self.base_url}/user_profiles",
                headers=headers,
                json=profile_data
            )
            
            if response.status_code in [200, 201]:
                return response.json()[0]
            else:
                logger.error(f"Failed to create user profile: {response.status_code} - {response.text}")
                # Return minimal profile if creation fails
                return profile_data
                
        except Exception as e:
            logger.error(f"Error creating user profile: {e}")
            return {
                "id": user_id,
                "spend": 0,
                "max_budget": 100,
                "litellm_key": None,
                "available_balance": 100
            }