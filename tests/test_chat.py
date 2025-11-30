"""Tests for the chat API endpoint."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from fastapi.testclient import TestClient

from api.main import app
from api.endpoints.chat import ChatRequest, ChatMessage, ChatResponse, get_openai_client


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI response."""
    mock_response = Mock()
    mock_response.choices = [Mock()]
    mock_response.choices[0].message = Mock()
    mock_response.choices[0].message.content = "This is a test response from the AI assistant."
    return mock_response


@pytest.fixture
def mock_openai_client(mock_openai_response):
    """Create a mock OpenAI client."""
    mock_client = Mock()
    mock_client.chat.completions.create = Mock(return_value=mock_openai_response)
    return mock_client


class TestChatEndpoint:
    """Tests for the /api/chat endpoint."""

    def test_chat_success(self, client, mock_openai_client):
        """Test successful chat request."""
        with patch('api.endpoints.chat.get_openai_client', return_value=mock_openai_client):
            response = client.post(
                "/api/chat",
                json={
                    "messages": [
                        {"role": "user", "content": "Hello, what's the best arbitrage opportunity?"}
                    ]
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert data["message"] == "This is a test response from the AI assistant."

    def test_chat_with_market_context(self, client, mock_openai_client):
        """Test chat request with market context."""
        with patch('api.endpoints.chat.get_openai_client', return_value=mock_openai_client):
            response = client.post(
                "/api/chat",
                json={
                    "messages": [
                        {"role": "user", "content": "What's the best opportunity?"}
                    ],
                    "market_context": "Total markets: 10\nActive opportunities: 3"
                }
            )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data
            assert len(data["message"]) > 0

    def test_chat_with_conversation_history(self, client, mock_openai_client):
        """Test chat request with conversation history."""
        with patch('api.endpoints.chat.get_openai_client', return_value=mock_openai_client):
            response = client.post(
                "/api/chat",
                json={
                    "messages": [
                        {"role": "user", "content": "Hello"},
                        {"role": "assistant", "content": "Hi there!"},
                        {"role": "user", "content": "What's arbitrage?"}
                    ]
                }
            )

            assert response.status_code == 200
            # Verify the OpenAI client was called with all messages
            call_args = mock_openai_client.chat.completions.create.call_args
            messages = call_args.kwargs['messages']
            # Should have system prompt + conversation messages
            assert len(messages) >= 3

    def test_chat_empty_messages(self, client, mock_openai_client):
        """Test chat request with empty messages list."""
        with patch('api.endpoints.chat.get_openai_client', return_value=mock_openai_client):
            response = client.post(
                "/api/chat",
                json={
                    "messages": []
                }
            )

            # Should still work - OpenAI will just get system prompt
            assert response.status_code == 200

    def test_chat_missing_messages_field(self, client):
        """Test chat request without messages field."""
        response = client.post(
            "/api/chat",
            json={}
        )

        assert response.status_code == 422  # Validation error

    def test_chat_openai_error(self, client):
        """Test handling of OpenAI API errors."""
        mock_client = Mock()
        mock_client.chat.completions.create = Mock(
            side_effect=Exception("OpenAI API error")
        )

        with patch('api.endpoints.chat.get_openai_client', return_value=mock_client):
            response = client.post(
                "/api/chat",
                json={
                    "messages": [
                        {"role": "user", "content": "Hello"}
                    ]
                }
            )

            assert response.status_code == 500
            data = response.json()
            assert "detail" in data
            assert "Failed to get response from AI" in data["detail"]

    def test_chat_response_format(self, client, mock_openai_client):
        """Test that response format matches ChatResponse model."""
        with patch('api.endpoints.chat.get_openai_client', return_value=mock_openai_client):
            response = client.post(
                "/api/chat",
                json={
                    "messages": [
                        {"role": "user", "content": "Test"}
                    ]
                }
            )

            assert response.status_code == 200
            data = response.json()

            # Verify response structure
            assert isinstance(data, dict)
            assert "message" in data
            assert isinstance(data["message"], str)
            # Should NOT have nested structure
            assert "choices" not in data

    def test_chat_null_response_handling(self, client):
        """Test handling when OpenAI returns null content."""
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = None  # Null content

        mock_client = Mock()
        mock_client.chat.completions.create = Mock(return_value=mock_response)

        with patch('api.endpoints.chat.get_openai_client', return_value=mock_client):
            response = client.post(
                "/api/chat",
                json={
                    "messages": [
                        {"role": "user", "content": "Hello"}
                    ]
                }
            )

            # This might cause issues - let's see what happens
            data = response.json()
            # If message is None, this could be the blank response issue
            print(f"Response when content is None: {data}")


class TestChatModels:
    """Tests for chat Pydantic models."""

    def test_chat_message_model(self):
        """Test ChatMessage model."""
        msg = ChatMessage(role="user", content="Hello")
        assert msg.role == "user"
        assert msg.content == "Hello"

    def test_chat_request_model(self):
        """Test ChatRequest model."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")],
            market_context="Some context"
        )
        assert len(request.messages) == 1
        assert request.market_context == "Some context"

    def test_chat_request_without_context(self):
        """Test ChatRequest model without market context."""
        request = ChatRequest(
            messages=[ChatMessage(role="user", content="Hello")]
        )
        assert request.market_context is None

    def test_chat_response_model(self):
        """Test ChatResponse model."""
        response = ChatResponse(message="Test response")
        assert response.message == "Test response"


class TestOpenAIClientInitialization:
    """Tests for OpenAI client initialization."""

    def test_get_openai_client_without_api_key(self):
        """Test that missing API key raises HTTPException."""
        import api.endpoints.chat as chat_module

        # Reset the global client
        chat_module._client = None

        with patch.dict('os.environ', {}, clear=True):
            with patch.object(chat_module, '_client', None):
                with pytest.raises(Exception) as exc_info:
                    # This should raise HTTPException
                    from api.endpoints.chat import get_openai_client
                    # Force reimport to reset state
                    import importlib
                    importlib.reload(chat_module)
                    chat_module._client = None
                    get_openai_client()


@pytest.mark.integration
class TestChatIntegration:
    """Integration tests for chat endpoint (requires real OpenAI API key)."""

    def test_chat_real_api(self, client):
        """Test chat with real OpenAI API."""
        import os
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        response = client.post(
            "/api/chat",
            json={
                "messages": [
                    {"role": "user", "content": "Say 'test successful' and nothing else."}
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert len(data["message"]) > 0
        print(f"Real API response: {data['message']}")

    def test_chat_with_real_market_context(self, client):
        """Test chat with market context using real API."""
        import os
        if not os.getenv("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set")

        response = client.post(
            "/api/chat",
            json={
                "messages": [
                    {"role": "user", "content": "How many opportunities are there?"}
                ],
                "market_context": "Total market pairs tracked: 5\nActive arbitrage opportunities: 2"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        # The response should mention the numbers from context
        print(f"Context-aware response: {data['message']}")
