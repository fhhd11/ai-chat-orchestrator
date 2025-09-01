"""Universal Edge Function proxy service with intelligent routing and error handling"""

import json
import asyncio
from typing import Dict, Optional, Any, List, Union
import httpx
from fastapi import HTTPException, Request
from loguru import logger

from ..config import settings
from ..models.common import ErrorResponse, PaginatedResponse, PaginationInfo, SuccessResponse
from ..utils.errors import EdgeFunctionError, ServiceUnavailableError


class EdgeFunctionProxy:
    """
    Universal proxy service for Supabase Edge Functions with intelligent routing,
    request/response transformation, error handling, and retry logic.
    """
    
    def __init__(self, base_url: Optional[str] = None):
        self.base_url = base_url or settings.edge_function_url
        self.client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, read=120.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
        
        # Endpoint mappings from FastAPI routes to Edge Function endpoints
        self.endpoint_mappings = {
            # Legacy endpoints (direct mapping)
            "/init-conversation": "/init-conversation",
            "/add-message": "/add-message", 
            "/save-response": "/save-response",
            "/create-branch": "/create-branch",
            "/switch-branch": "/switch-branch",
            "/build-context": "/build-context",
            
            # New REST endpoints mapping
            "/v1/conversations": {
                "GET": "/conversations",
                "POST": "/conversations"
            },
            "/v1/conversations/{id}": {
                "GET": "/conversations/{id}",
                "PATCH": "/conversations/{id}"
            },
            "/v1/conversations/{id}/full": {
                "GET": "/conversations/{id}/full"
            },
            "/v1/conversations/{id}/branches": {
                "GET": "/conversations/{id}/branches",
                "POST": "/conversations/{id}/branches"
            },
            "/v1/conversations/{id}/branches/{branch_id}/activate": {
                "POST": "/conversations/{id}/branches/{branch_id}/activate"
            },
            "/v1/messages/{id}": {
                "GET": "/messages/{id}",
                "PATCH": "/messages/{id}"
            },
            "/v1/messages/{id}/regenerate": {
                "POST": "/messages/{id}/regenerate"
            }
        }
    
    async def close(self):
        """Close the HTTP client"""
        await self.client.aclose()
    
    def _get_edge_endpoint(self, fastapi_path: str, method: str) -> str:
        """
        Map FastAPI endpoint to Edge Function endpoint
        
        Args:
            fastapi_path: FastAPI route path
            method: HTTP method
            
        Returns:
            Corresponding Edge Function endpoint
        """
        # Direct mapping for legacy endpoints
        if fastapi_path in self.endpoint_mappings:
            mapping = self.endpoint_mappings[fastapi_path]
            if isinstance(mapping, str):
                return mapping
            elif isinstance(mapping, dict) and method in mapping:
                return mapping[method]
        
        # Try pattern matching for parameterized routes
        for pattern, mapping in self.endpoint_mappings.items():
            if self._path_matches_pattern(fastapi_path, pattern):
                if isinstance(mapping, dict) and method in mapping:
                    return self._substitute_path_params(mapping[method], fastapi_path, pattern)
                elif isinstance(mapping, str):
                    return self._substitute_path_params(mapping, fastapi_path, pattern)
        
        # Default: use the same path
        return fastapi_path
    
    def _path_matches_pattern(self, path: str, pattern: str) -> bool:
        """Check if path matches a pattern with parameters"""
        path_parts = path.strip('/').split('/')
        pattern_parts = pattern.strip('/').split('/')
        
        if len(path_parts) != len(pattern_parts):
            return False
        
        for path_part, pattern_part in zip(path_parts, pattern_parts):
            if pattern_part.startswith('{') and pattern_part.endswith('}'):
                continue  # Parameter, matches anything
            elif path_part != pattern_part:
                return False
        
        return True
    
    def _substitute_path_params(self, edge_pattern: str, fastapi_path: str, fastapi_pattern: str) -> str:
        """Substitute path parameters from FastAPI path to Edge Function path"""
        fastapi_parts = fastapi_path.strip('/').split('/')
        pattern_parts = fastapi_pattern.strip('/').split('/')
        edge_parts = edge_pattern.strip('/').split('/')
        
        # Extract parameters
        params = {}
        for i, (path_part, pattern_part) in enumerate(zip(fastapi_parts, pattern_parts)):
            if pattern_part.startswith('{') and pattern_part.endswith('}'):
                param_name = pattern_part[1:-1]
                params[param_name] = path_part
        
        # Substitute parameters in edge pattern
        result_parts = []
        for part in edge_parts:
            if part.startswith('{') and part.endswith('}'):
                param_name = part[1:-1]
                if param_name in params:
                    result_parts.append(params[param_name])
                else:
                    result_parts.append(part)
            else:
                result_parts.append(part)
        
        return '/' + '/'.join(result_parts)
    
    def _transform_query_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Transform FastAPI query parameters for Edge Function"""
        transformed = {}
        
        for key, value in params.items():
            if value is not None:
                # Handle pagination parameters
                if key in ['page', 'limit']:
                    transformed[key] = str(value)
                # Handle search/filter parameters
                elif key in ['q', 'model', 'status', 'created_after', 'created_before']:
                    transformed[key] = str(value)
                # Handle sorting parameters
                elif key in ['sort_by', 'sort_order']:
                    transformed[key] = str(value)
                else:
                    transformed[key] = str(value)
        
        return transformed
    
    def _transform_request_body(self, body: Dict[str, Any], endpoint: str) -> Dict[str, Any]:
        """Transform request body for Edge Function compatibility"""
        # Most Edge Functions expect the same structure
        # Add any specific transformations here if needed
        return body
    
    def _transform_response(self, response: Dict[str, Any], endpoint: str, status_code: int) -> Dict[str, Any]:
        """
        Transform Edge Function response to FastAPI standard format
        
        Args:
            response: Raw Edge Function response
            endpoint: Edge Function endpoint
            status_code: HTTP status code
            
        Returns:
            Transformed response in standard format
        """
        # Edge Functions return { success: bool, data?: any, error?: string }
        # Transform to standard FastAPI format
        
        if status_code >= 400:
            # Error response
            error_message = response.get('error', 'Unknown error')
            return ErrorResponse.create(
                message=error_message,
                code=f"EDGE_FUNCTION_ERROR_{status_code}",
                details={
                    "endpoint": endpoint,
                    "original_response": response
                }
            ).model_dump()
        
        if not response.get('success', False):
            # Edge Function returned success=false
            error_message = response.get('error', 'Edge Function returned error')
            return ErrorResponse.create(
                message=error_message,
                code="EDGE_FUNCTION_ERROR",
                details={
                    "endpoint": endpoint,
                    "original_response": response
                }
            ).model_dump()
        
        # Success response
        data = response.get('data', {})
        
        # Check if response contains pagination info
        if isinstance(data, dict) and 'items' in data and 'pagination' in data:
            # Already paginated response
            return SuccessResponse(data=data).model_dump()
        elif isinstance(data, dict) and 'total' in data and 'page' in data:
            # Transform to paginated format
            pagination = PaginationInfo(
                page=data.get('page', 1),
                limit=data.get('limit', 20),
                total=data.get('total', 0),
                pages=data.get('pages', 1),
                has_next=data.get('has_next', False),
                has_prev=data.get('has_prev', False)
            )
            return SuccessResponse(data={
                'items': data.get('items', []),
                'pagination': pagination.model_dump()
            }).model_dump()
        else:
            # Simple success response
            return SuccessResponse(data=data).model_dump()
    
    async def proxy_request(
        self,
        method: str,
        path: str,
        user_token: str,
        query_params: Optional[Dict[str, Any]] = None,
        body: Optional[Dict[str, Any]] = None,
        retries: int = 3
    ) -> Dict[str, Any]:
        """
        Proxy request to Edge Function with intelligent routing and error handling
        
        Args:
            method: HTTP method
            path: FastAPI route path
            user_token: User JWT token
            query_params: Query parameters
            body: Request body
            retries: Number of retry attempts
            
        Returns:
            Transformed response from Edge Function
            
        Raises:
            HTTPException: For client errors (400-499)
            EdgeFunctionError: For Edge Function errors
            ServiceUnavailableError: For service unavailability
        """
        edge_endpoint = self._get_edge_endpoint(path, method)
        url = f"{self.base_url}{edge_endpoint}"
        
        headers = {
            "Authorization": f"Bearer {user_token}",
            "Content-Type": "application/json"
        }
        
        # Transform query parameters
        transformed_params = None
        if query_params:
            transformed_params = self._transform_query_params(query_params)
        
        # Transform request body
        transformed_body = None
        if body:
            transformed_body = self._transform_request_body(body, edge_endpoint)
        
        # Log request
        logger.info(
            f"Proxying {method} {path} -> {edge_endpoint}",
            extra={
                "method": method,
                "fastapi_path": path,
                "edge_endpoint": edge_endpoint,
                "has_body": body is not None,
                "has_params": query_params is not None
            }
        )
        
        for attempt in range(retries + 1):
            try:
                # Make request to Edge Function
                request_kwargs = {
                    "url": url,
                    "headers": headers,
                    "params": transformed_params
                }
                
                if transformed_body:
                    request_kwargs["json"] = transformed_body
                
                response = await self.client.request(method, **request_kwargs)
                
                # Handle response
                if response.status_code == 200:
                    response_data = response.json()
                    transformed_response = self._transform_response(
                        response_data, edge_endpoint, response.status_code
                    )
                    
                    logger.info(f"Edge Function {edge_endpoint} succeeded")
                    return transformed_response
                
                elif response.status_code == 401:
                    logger.warning(f"Authentication failed for {edge_endpoint}")
                    raise HTTPException(
                        status_code=401,
                        detail="Authentication failed"
                    )
                
                elif response.status_code == 403:
                    logger.warning(f"Access forbidden for {edge_endpoint}")
                    raise HTTPException(
                        status_code=403,
                        detail="Access forbidden"
                    )
                
                elif response.status_code == 404:
                    logger.warning(f"Resource not found: {edge_endpoint}")
                    raise HTTPException(
                        status_code=404,
                        detail="Resource not found"
                    )
                
                elif 400 <= response.status_code < 500:
                    # Client error - don't retry
                    try:
                        error_data = response.json()
                        error_message = error_data.get('error', f'Client error: {response.status_code}')
                    except:
                        error_message = f'Client error: {response.status_code}'
                    
                    logger.warning(f"Client error for {edge_endpoint}: {error_message}")
                    raise HTTPException(
                        status_code=response.status_code,
                        detail=error_message
                    )
                
                else:
                    # Server error - retry if not last attempt
                    if attempt < retries:
                        wait_time = 2 ** attempt
                        logger.warning(
                            f"Edge Function {edge_endpoint} failed with status {response.status_code}, "
                            f"retrying in {wait_time}s"
                        )
                        await asyncio.sleep(wait_time)
                        continue
                    else:
                        try:
                            error_data = response.json()
                            error_message = error_data.get('error', f'Server error: {response.status_code}')
                        except:
                            error_message = f'Server error: {response.status_code}'
                        
                        raise EdgeFunctionError(
                            message=f"Edge Function error: {error_message}",
                            code="EDGE_FUNCTION_ERROR",
                            details={
                                "endpoint": edge_endpoint,
                                "status_code": response.status_code
                            }
                        )
                        
            except httpx.RequestError as e:
                if attempt < retries:
                    wait_time = 2 ** attempt
                    logger.warning(
                        f"Edge Function {edge_endpoint} request failed: {e}, "
                        f"retrying in {wait_time}s"
                    )
                    await asyncio.sleep(wait_time)
                    continue
                else:
                    logger.error(f"Edge Function {edge_endpoint} failed after {retries} retries: {e}")
                    raise ServiceUnavailableError(
                        message=f"Service unavailable: {str(e)}",
                        code="SERVICE_UNAVAILABLE",
                        details={
                            "endpoint": edge_endpoint,
                            "error": str(e)
                        }
                    )
            
            except Exception as e:
                logger.error(f"Unexpected error in Edge Function proxy: {e}")
                raise EdgeFunctionError(
                    message=f"Unexpected proxy error: {str(e)}",
                    code="PROXY_ERROR",
                    details={
                        "endpoint": edge_endpoint,
                        "error": str(e)
                    }
                )
        
        # This should never be reached due to the exception handling above
        raise ServiceUnavailableError(
            message="Max retries exceeded",
            code="MAX_RETRIES_EXCEEDED",
            details={"endpoint": edge_endpoint}
        )
    
    async def health_check(self) -> bool:
        """Check if Edge Functions are healthy"""
        try:
            # Use a simple endpoint that doesn't require authentication
            response = await self.client.get(
                f"{self.base_url}/health",
                timeout=5.0
            )
            return response.status_code < 500
        except Exception as e:
            logger.warning(f"Edge Function health check failed: {e}")
            return False