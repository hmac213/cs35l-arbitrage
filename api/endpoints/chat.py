"""Chat API endpoint with OpenAI integration."""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

logger = logging.getLogger(__name__)

router = APIRouter()

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


class ChatMessage(BaseModel):
    """A single chat message."""
    role: str  # "user" or "assistant"
    content: str


class ChatRequest(BaseModel):
    """Request body for chat endpoint."""
    messages: List[ChatMessage]
    market_context: Optional[str] = None


class ChatResponse(BaseModel):
    """Response from chat endpoint."""
    message: str


SYSTEM_PROMPT = """You are an expert arbitrage trading assistant for a prediction markets dashboard.
You help users understand and take advantage of arbitrage opportunities between Kalshi and Polymarket.

Your role is to:
1. Explain arbitrage opportunities in simple terms
2. Help users understand the risks and potential returns
3. Suggest which opportunities might be best based on their budget
4. Answer questions about prediction markets and trading strategies

When given market data context, analyze it to provide specific recommendations.
Be concise but thorough. Use numbers and percentages when discussing potential returns.
Always remind users that trading involves risk and past performance doesn't guarantee future results.

Format your responses clearly with bullet points or numbered lists when appropriate."""


@router.post(
    "/chat",
    response_model=ChatResponse,
    summary="Chat with AI assistant",
    description="Send a message to the AI assistant and receive a response with market context awareness.",
    tags=["chat"]
)
async def chat(request: ChatRequest) -> ChatResponse:
    """Chat with the AI assistant.

    Args:
        request: ChatRequest containing messages and optional market context.

    Returns:
        ChatResponse with the assistant's message.
    """
    try:
        # Build messages for OpenAI
        openai_messages = [{"role": "system", "content": SYSTEM_PROMPT}]

        # Add market context if provided
        if request.market_context:
            openai_messages.append({
                "role": "system",
                "content": f"Current market data:\n{request.market_context}"
            })

        # Add conversation history
        for msg in request.messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Call OpenAI API
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            messages=openai_messages,
            max_tokens=500,
            temperature=0.7,
        )

        assistant_message = response.choices[0].message.content

        return ChatResponse(message=assistant_message)

    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get response from AI: {str(e)}"
        )
