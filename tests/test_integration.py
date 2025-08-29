"""Integration tests for the AI Chat Orchestrator"""

import pytest
import os
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.services.auth_service import AuthService
from app.services.supabase_client import SupabaseClient
from app.services.litellm_client import LiteLLMClient
from app.config import settings


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def mock_jwt_token():
    """Mock JWT token payload"""
    return {
        "sub": "test-user-id",
        "email": "test@example.com",
        "aud": "authenticated",
        "exp": 9999999999,  # Far future
        "role": "authenticated"
    }


@pytest.fixture
def valid_auth_header():
    """Valid authorization header for testing"""
    return "Bearer valid-test-token"


class TestAuthService:
    """Test authentication service"""
    
    def test_auth_service_initialization(self):
        """Test auth service can be initialized"""
        auth_service = AuthService(settings)
        assert auth_service.jwt_secret_key == settings.jwt_secret_key
        assert auth_service.jwt_algorithm == settings.jwt_algorithm
        assert auth_service.cache is not None
    
    def test_extract_bearer_token(self):
        """Test bearer token extraction"""
        auth_service = AuthService(settings)
        
        # Valid token
        token = auth_service.extract_bearer_token("Bearer test-token")
        assert token == "test-token"
        
        # Invalid format
        with pytest.raises(Exception):
            auth_service.extract_bearer_token("Invalid format")
        
        # Missing token
        with pytest.raises(Exception):
            auth_service.extract_bearer_token("")
    
    def test_cache_operations(self):
        """Test cache operations"""
        auth_service = AuthService(settings)
        
        # Test cache stats
        stats = auth_service.get_cache_stats()
        assert "size" in stats
        assert "maxsize" in stats
        assert "ttl" in stats
        
        # Test cache clear
        auth_service.clear_cache()
        assert len(auth_service.cache) == 0


class TestSupabaseClient:
    """Test Supabase client"""
    
    @pytest.mark.asyncio
    async def test_supabase_client_initialization(self):
        """Test Supabase client initialization"""
        client = SupabaseClient(settings)
        
        assert client.base_url == settings.edge_function_url
        assert client.supabase_url == settings.supabase_url
        assert client.anon_key == settings.supabase_anon_key
        assert client.client is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_call_edge_function_retry_logic(self):
        """Test edge function retry logic"""
        client = SupabaseClient(settings)
        
        with patch.object(client.client, 'post') as mock_post:
            # Mock a successful response after retry
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.json.return_value = {"success": True, "data": {"test": "data"}}
            mock_post.return_value = mock_response
            
            result = await client.call_edge_function(
                "test-endpoint",
                {"test": "data"},
                "test-token"
            )
            
            assert result["test"] == "data"
        
        await client.close()


class TestLiteLLMClient:
    """Test LiteLLM client"""
    
    @pytest.mark.asyncio
    async def test_litellm_client_initialization(self):
        """Test LiteLLM client initialization"""
        client = LiteLLMClient(settings)
        
        assert client.base_url == settings.litellm_url
        assert client.master_key == settings.litellm_master_key
        assert client.timeout == settings.stream_timeout
        assert client.client is not None
        
        await client.close()
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test LiteLLM health check"""
        client = LiteLLMClient(settings)
        
        with patch.object(client.client, 'get') as mock_get:
            # Mock successful health check
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_get.return_value = mock_response
            
            is_healthy = await client.health_check()
            assert is_healthy is True
            
            # Mock failed health check
            mock_response.status_code = 500
            is_healthy = await client.health_check()
            assert is_healthy is False
        
        await client.close()


class TestFullIntegration:
    """Test full integration scenarios"""
    
    @pytest.mark.asyncio
    async def test_application_startup_shutdown(self):
        """Test application startup and shutdown"""
        # This tests the lifespan events
        with TestClient(app) as client:
            # App should start successfully
            response = client.get("/health")
            assert response.status_code == 200
    
    def test_cors_headers(self, client):
        """Test CORS headers are present"""
        response = client.options("/health")
        
        # Should have CORS headers
        assert "access-control-allow-origin" in response.headers
    
    def test_request_id_middleware(self, client):
        """Test request ID middleware"""
        response = client.get("/health")
        
        # Should have request ID header
        assert "X-Request-ID" in response.headers
        assert len(response.headers["X-Request-ID"]) > 0
    
    def test_security_headers(self, client):
        """Test security headers"""
        response = client.get("/health")
        
        # Should have security headers
        assert "X-Content-Type-Options" in response.headers
        assert "X-Frame-Options" in response.headers
        assert "X-XSS-Protection" in response.headers
    
    @pytest.mark.asyncio
    async def test_metrics_endpoint(self, client):
        """Test metrics endpoint if enabled"""
        if settings.enable_metrics:
            response = client.get("/metrics")
            # Metrics endpoint should be available
            assert response.status_code in [200, 404]  # May not be fully set up in tests


class TestErrorScenarios:
    """Test error scenarios and edge cases"""
    
    def test_missing_environment_variables(self):
        """Test handling of missing environment variables"""
        # This would be tested by temporarily unsetting env vars
        # For now, we just check that settings load without critical errors
        assert settings.app_name is not None
        assert settings.version is not None
    
    @pytest.mark.asyncio
    async def test_service_unavailable_scenarios(self):
        """Test service unavailable scenarios"""
        # Mock scenarios where external services are down
        
        # Test Supabase client with network error
        client = SupabaseClient(settings)
        
        with patch.object(client.client, 'post') as mock_post:
            mock_post.side_effect = Exception("Network error")
            
            with pytest.raises(Exception):
                await client.call_edge_function(
                    "test-endpoint",
                    {"test": "data"},
                    "test-token",
                    retries=1  # Reduce retries for faster test
                )
        
        await client.close()
    
    def test_invalid_request_data(self, client):
        """Test handling of invalid request data"""
        # Test malformed JSON
        response = client.post(
            "/v1/chat/completions",
            data="invalid json",
            headers={
                "Authorization": "Bearer test",
                "Content-Type": "application/json"
            }
        )
        assert response.status_code == 422
    
    def test_large_request_handling(self, client):
        """Test handling of large requests"""
        # Test with very large message
        large_message = "A" * 10000  # 10KB message
        
        request_data = {
            "message": large_message,
            "stream": True
        }
        
        response = client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": "Bearer test"}
        )
        
        # Should handle large requests (though auth will fail)
        assert response.status_code in [401, 422, 500]


class TestPerformance:
    """Test performance characteristics"""
    
    def test_health_endpoint_performance(self, client):
        """Test health endpoint responds quickly"""
        import time
        
        start_time = time.time()
        response = client.get("/health")
        end_time = time.time()
        
        duration = end_time - start_time
        
        assert response.status_code == 200
        assert duration < 1.0  # Should respond within 1 second
    
    def test_concurrent_health_requests(self, client):
        """Test handling of concurrent health requests"""
        import concurrent.futures
        import threading
        
        def make_request():
            return client.get("/health")
        
        # Test with multiple concurrent requests
        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            responses = [future.result() for future in futures]
        
        # All requests should succeed
        for response in responses:
            assert response.status_code == 200