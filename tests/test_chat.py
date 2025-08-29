"""Tests for chat endpoints"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from fastapi.testclient import TestClient

from app.main import app
from app.models import ChatCompletionRequest, RegenerateRequest


@pytest.fixture
def client():
    """Test client fixture"""
    return TestClient(app)


@pytest.fixture
def mock_user_profile():
    """Mock user profile"""
    return MagicMock(
        id="test-user-id",
        litellm_key="sk-test-key",
        email="test@example.com",
        spend=0.5,
        max_budget=10.0,
        available_balance=9.5
    )


@pytest.fixture
def mock_auth_header():
    """Mock authorization header"""
    return "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0LXVzZXItaWQifQ.test"


class TestChatCompletions:
    """Test chat completions endpoint"""
    
    def test_chat_completions_missing_auth(self, client):
        """Test chat completions without authorization header"""
        request_data = {
            "message": "Hello, world!",
            "stream": True
        }
        
        response = client.post("/v1/chat/completions", json=request_data)
        assert response.status_code == 422  # Unprocessable Entity (missing header)
    
    def test_chat_completions_invalid_request(self, client, mock_auth_header):
        """Test chat completions with invalid request data"""
        request_data = {
            # Missing required 'message' field
            "stream": True
        }
        
        response = client.post(
            "/v1/chat/completions",
            json=request_data,
            headers={"Authorization": mock_auth_header}
        )
        assert response.status_code == 422  # Validation error
    
    @pytest.mark.asyncio
    async def test_chat_request_model_validation(self):
        """Test ChatCompletionRequest model validation"""
        # Valid request
        valid_request = ChatCompletionRequest(
            message="Hello, world!",
            stream=True,
            temperature=0.7
        )
        assert valid_request.message == "Hello, world!"
        assert valid_request.stream is True
        assert valid_request.temperature == 0.7
        
        # Invalid temperature
        with pytest.raises(ValueError):
            ChatCompletionRequest(
                message="Hello",
                temperature=3.0  # Too high
            )
    
    @pytest.mark.asyncio
    async def test_regenerate_request_model_validation(self):
        """Test RegenerateRequest model validation"""
        # Valid request
        valid_request = RegenerateRequest(
            conversation_id="test-conv-id",
            message_id="test-msg-id",
            model="gpt-4"
        )
        assert valid_request.conversation_id == "test-conv-id"
        assert valid_request.message_id == "test-msg-id"
        assert valid_request.model == "gpt-4"


class TestHealthEndpoints:
    """Test health check endpoints"""
    
    def test_health_check(self, client):
        """Test health check endpoint"""
        response = client.get("/health")
        assert response.status_code == 200
        
        data = response.json()
        assert "status" in data
        assert "version" in data
        assert "services" in data
    
    def test_readiness_check(self, client):
        """Test readiness check endpoint"""
        response = client.get("/ready")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "ready"
    
    def test_liveness_check(self, client):
        """Test liveness check endpoint"""
        response = client.get("/live")
        assert response.status_code == 200
        
        data = response.json()
        assert data["status"] == "alive"


class TestInfoEndpoint:
    """Test info endpoint"""
    
    def test_info_endpoint(self, client):
        """Test service info endpoint"""
        response = client.get("/info")
        assert response.status_code == 200
        
        data = response.json()
        assert "service" in data
        assert "version" in data
        assert "features" in data
        assert "endpoints" in data
        
        # Check features
        features = data["features"]
        assert features["streaming"] is True
        assert features["authentication"] is True
        assert features["regeneration"] is True


class TestRootEndpoint:
    """Test root endpoint"""
    
    def test_root_endpoint(self, client):
        """Test root endpoint"""
        response = client.get("/")
        
        # Should either redirect to docs (in debug) or return info
        assert response.status_code in [200, 307]  # 307 for redirect


class TestErrorHandling:
    """Test error handling"""
    
    def test_404_not_found(self, client):
        """Test 404 error handling"""
        response = client.get("/nonexistent-endpoint")
        assert response.status_code == 404
    
    def test_405_method_not_allowed(self, client):
        """Test 405 error handling"""
        response = client.patch("/health")  # PATCH not allowed
        assert response.status_code == 405


class TestConversationEndpoints:
    """Test conversation endpoints"""
    
    def test_get_conversation_missing_auth(self, client):
        """Test get conversation without authorization"""
        response = client.get("/v1/conversations/test-conv-id")
        assert response.status_code == 422  # Missing header
    
    def test_list_conversations_placeholder(self, client, mock_auth_header):
        """Test list conversations placeholder"""
        response = client.get(
            "/v1/conversations",
            headers={"Authorization": mock_auth_header}
        )
        # This will fail due to auth validation, but endpoint exists
        assert response.status_code in [401, 422, 500]  # Various auth errors
    
    def test_delete_conversation_not_implemented(self, client, mock_auth_header):
        """Test delete conversation not implemented"""
        response = client.delete(
            "/v1/conversations/test-conv-id",
            headers={"Authorization": mock_auth_header}
        )
        # This will fail due to auth validation, but endpoint exists
        assert response.status_code in [401, 422, 501]  # Auth error or not implemented