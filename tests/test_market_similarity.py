"""Unit tests for market similarity service components."""

import pytest
from unittest.mock import Mock, MagicMock, patch
from datetime import date, time

from db.models import DatabaseMarket, MarketPair
from vector_db.client import SupabaseVectorStore
from engine.llm_verifier import LLMVerifier
from engine.market_similarity import MarketSimilarityService
from engine.verification_queue import VerificationQueue
from engine.errors import VectorStoreError, LLMVerificationError, SimilarityError


@pytest.fixture
def sample_market_kalshi():
    """Create a sample Kalshi market."""
    return DatabaseMarket(
        id="uuid-1",
        market_id="KX-TEST-123",
        exchange="kalshi",
        name="Will it rain tomorrow?",
        rules="This market resolves to YES if it rains on 2025-12-01, otherwise NO.",
        resolve_date=date(2025, 12, 1),
        resolve_time=time(12, 0, 0),
        category="Weather"
    )


@pytest.fixture
def sample_market_polymarket():
    """Create a sample Polymarket market."""
    return DatabaseMarket(
        id="uuid-2",
        market_id="will-it-rain-tomorrow",
        exchange="polymarket",
        name="Will it rain tomorrow?",
        rules="This market resolves to YES if it rains on 2025-12-01, otherwise NO.",
        resolve_date=date(2025, 12, 1),
        resolve_time=time(12, 0, 0),
        category="Weather"
    )


@pytest.fixture
def mock_vector_store():
    """Create a mock vector store."""
    store = Mock(spec=SupabaseVectorStore)
    store.embed_market = Mock(return_value=[0.1] * 3072)  # Mock embedding (text-embedding-3-large has 3072 dims)
    store.upsert_market = Mock()
    store.search_similar_markets = Mock(return_value=[])
    store.update_market = Mock()
    store.delete_market = Mock()
    return store


@pytest.fixture
def mock_llm_verifier():
    """Create a mock LLM verifier."""
    verifier = Mock(spec=LLMVerifier)
    verifier.verify_markets_identical = Mock(return_value={
        "is_identical": True,
        "confidence": 0.95,
        "reasoning": "Both markets ask the same question"
    })
    return verifier


@pytest.fixture
def mock_db_client():
    """Create a mock database client."""
    client = Mock()
    client.get_market = Mock()
    client.upsert_market_pair = Mock(return_value={"id": "pair-uuid"})
    client.get_market_pairs_by_market = Mock(return_value=[])
    return client


class TestSupabaseVectorStore:
    """Tests for SupabaseVectorStore."""
    
    @patch('vector_db.client.OpenAI')
    def test_init_success(self, mock_openai):
        """Test successful initialization."""
        mock_db_client = Mock()
        
        store = SupabaseVectorStore(
            db_client=mock_db_client,
            embedding_model="text-embedding-3-small"
        )
        
        assert store.openai_client is not None
        assert store.db_client == mock_db_client
    
    @patch('vector_db.client.OpenAI')
    def test_init_missing_api_key(self, mock_openai):
        """Test initialization fails without API key."""
        mock_db_client = Mock()
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(VectorStoreError, match="API key is required"):
                SupabaseVectorStore(db_client=mock_db_client)
    
    @patch('vector_db.client.OpenAI')
    def test_get_market_text(self, mock_openai):
        """Test market text generation."""
        mock_db_client = Mock()
        store = SupabaseVectorStore(db_client=mock_db_client)
        
        market = DatabaseMarket(
            market_id="TEST-123",
            exchange="kalshi",
            name="Test Market",
            rules="Test rules",
            description="Test description",
            category="Test"
        )
        
        # Access the private method via the instance
        text = store._get_market_text(market)
        
        assert "Test Market" in text
        assert "Test rules" in text
        assert "Test description" in text
        assert "Test" in text  # Category


class TestLLMVerifier:
    """Tests for LLMVerifier."""
    
    @patch('engine.llm_verifier.OpenAI')
    def test_init_success(self, mock_openai):
        """Test successful initialization."""
        verifier = LLMVerifier(api_key="test-key")
        assert verifier.client is not None
    
    def test_init_missing_api_key(self):
        """Test initialization fails without API key."""
        with pytest.raises(LLMVerificationError, match="API key is required"):
            LLMVerifier(api_key=None)
    
    @patch('engine.llm_verifier.OpenAI')
    def test_verify_markets_identical(self, mock_openai_class, sample_market_kalshi, sample_market_polymarket):
        """Test market verification."""
        mock_client = Mock()
        mock_openai_class.return_value = mock_client
        
        # Mock the chat completion response
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.tool_calls = [Mock()]
        mock_response.choices[0].message.tool_calls[0].function = Mock()
        mock_response.choices[0].message.tool_calls[0].function.arguments = '{"is_identical": true, "confidence": 0.9}'
        
        mock_client.chat.completions.create = Mock(return_value=mock_response)
        
        verifier = LLMVerifier(api_key="test-key")
        
        import json
        with patch('json.loads', return_value={"is_identical": True, "confidence": 0.9}):
            result = verifier.verify_markets_identical(sample_market_kalshi, sample_market_polymarket)
        
        assert result["is_identical"] is True
        assert result["confidence"] == 0.9


class TestMarketSimilarityService:
    """Tests for MarketSimilarityService."""
    
    def test_process_new_market(self, mock_vector_store, mock_llm_verifier, mock_db_client, sample_market_kalshi):
        """Test processing a new market."""
        queue = VerificationQueue()
        service = MarketSimilarityService(
            vector_store=mock_vector_store,
            llm_verifier=mock_llm_verifier,
            db_client=mock_db_client,
            verification_queue=queue
        )
        
        # Mock search to return a candidate
        mock_vector_store.search_similar_markets.return_value = [{
            "market_id": "POLY-TEST-123",
            "exchange": "polymarket",
            "score": 0.85,
            "metadata": {}
        }]
        
        candidates = service.process_new_market(sample_market_kalshi)
        
        assert candidates is not None
        assert len(candidates) == 1
        mock_vector_store.embed_market.assert_called_once()
        mock_vector_store.upsert_market.assert_called_once()
        assert queue.size() == 1  # One task queued
    
    def test_verify_and_create_pair(self, mock_vector_store, mock_llm_verifier, mock_db_client, sample_market_kalshi, sample_market_polymarket):
        """Test verifying and creating a market pair."""
        service = MarketSimilarityService(
            vector_store=mock_vector_store,
            llm_verifier=mock_llm_verifier,
            db_client=mock_db_client
        )
        
        pair = service.verify_and_create_pair(
            sample_market_kalshi,
            sample_market_polymarket,
            0.85
        )
        
        assert pair is not None
        mock_llm_verifier.verify_markets_identical.assert_called_once()
        mock_db_client.upsert_market_pair.assert_called_once()
    
    def test_verify_and_create_pair_not_identical(self, mock_vector_store, mock_llm_verifier, mock_db_client, sample_market_kalshi, sample_market_polymarket):
        """Test verification when markets are not identical."""
        mock_llm_verifier.verify_markets_identical.return_value = {
            "is_identical": False,
            "confidence": 0.3,
            "reasoning": "Different questions"
        }
        
        service = MarketSimilarityService(
            vector_store=mock_vector_store,
            llm_verifier=mock_llm_verifier,
            db_client=mock_db_client
        )
        
        pair = service.verify_and_create_pair(
            sample_market_kalshi,
            sample_market_polymarket,
            0.85
        )
        
        assert pair is None
        mock_db_client.upsert_market_pair.assert_not_called()


class TestVerificationQueue:
    """Tests for VerificationQueue."""
    
    def test_enqueue_dequeue(self):
        """Test queue operations."""
        queue = VerificationQueue()
        
        queue.enqueue("M1", "kalshi", "M2", "polymarket", 0.85)
        
        assert queue.size() == 1
        
        task = queue.dequeue()
        assert task is not None
        assert task.market1_id == "M1"
        assert task.market2_id == "M2"
        assert task.similarity_score == 0.85
        assert queue.size() == 0
    
    def test_clear(self):
        """Test clearing the queue."""
        queue = VerificationQueue()
        queue.enqueue("M1", "kalshi", "M2", "polymarket", 0.85)
        queue.enqueue("M3", "kalshi", "M4", "polymarket", 0.90)
        
        assert queue.size() == 2
        queue.clear()
        assert queue.size() == 0


class TestMarketPair:
    """Tests for MarketPair model."""
    
    def test_from_markets(self, sample_market_kalshi, sample_market_polymarket):
        """Test creating MarketPair from two markets."""
        pair = MarketPair.from_markets(
            sample_market_kalshi,
            sample_market_polymarket,
            0.85,
            llm_verified=True,
            llm_confidence=0.95
        )
        
        assert pair.market_1_id == sample_market_kalshi.id
        assert pair.market_2_id == sample_market_polymarket.id
        assert pair.similarity_score == 0.85
        assert pair.llm_verified is True
        assert pair.llm_confidence == 0.95
    
    def test_from_markets_same_exchange(self, sample_market_kalshi):
        """Test that creating pair from same exchange raises error."""
        market2 = DatabaseMarket(
            id="uuid-3",
            market_id="KX-TEST-456",
            exchange="kalshi",
            name="Another market"
        )
        
        with pytest.raises(ValueError, match="different exchanges"):
            MarketPair.from_markets(sample_market_kalshi, market2, 0.85)
    
    def test_to_dict(self, sample_market_kalshi, sample_market_polymarket):
        """Test converting MarketPair to dictionary."""
        pair = MarketPair.from_markets(
            sample_market_kalshi,
            sample_market_polymarket,
            0.85,
            llm_verified=True,
            llm_confidence=0.95
        )
        
        data = pair.to_dict()
        
        assert data['market_1_id'] == sample_market_kalshi.id
        assert data['market_2_id'] == sample_market_polymarket.id
        assert data['similarity_score'] == 0.85
        assert data['llm_verified'] is True
        assert data['llm_confidence'] == 0.95

