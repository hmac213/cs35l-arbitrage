"""Chat API endpoint with OpenAI integration."""

import os
import logging
from typing import List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from openai import OpenAI

logger = logging.getLogger(__name__)

router = APIRouter()

# Lazy-load OpenAI client to ensure env vars are loaded first
_client: Optional[OpenAI] = None


def get_openai_client() -> OpenAI:
    """Get or create the OpenAI client."""
    global _client
    if _client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise HTTPException(
                status_code=500,
                detail="OPENAI_API_KEY environment variable is not set"
            )
        _client = OpenAI(api_key=api_key)
    return _client


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


SYSTEM_PROMPT = """You are an arbitrage assistant for a prediction markets dashboard.

IMPORTANT RESPONSE GUIDELINES:
- Keep responses SHORT and concise (2-4 sentences for simple questions, max 5-6 bullet points for recommendations)
- Always refer to markets by their ACTUAL NAME, never by number (e.g., "Bad Bunny album market" not "#1")
- Skip lengthy explanations unless the user asks for details
- Don't list every opportunity - just mention the top 1-2 relevant ones
- Only mention risks briefly at the end, not a full list

When recommending opportunities:
- Lead with the market name and key profit info
- Give a simple strategy (e.g., "Buy YES on Kalshi, NO on Polymarket")
- One brief risk reminder at the end

Example good response:
"The best opportunity is the Bad Bunny album market - you can make ~74% profit per share by buying YES on Kalshi ($0.05) and NO on Polymarket ($0.03). Max potential profit is around $6,400. As always, execute both sides quickly to lock in the arbitrage."

Be helpful but brief. Users can ask follow-up questions if they want more detail."""


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
        # Build system prompt with market context if provided
        system_content = SYSTEM_PROMPT
        if request.market_context:
            system_content += f"\n\nCurrent market data:\n{request.market_context}"

        # Build messages for OpenAI - single system message
        openai_messages = [{"role": "system", "content": system_content}]

        # Add conversation history
        for msg in request.messages:
            openai_messages.append({
                "role": msg.role,
                "content": msg.content
            })

        # Call OpenAI API
        client = get_openai_client()
        model = os.getenv("OPENAI_MODEL", "gpt-5-nano")
        logger.info(f"Calling OpenAI with model: {model}, messages count: {len(openai_messages)}")

        response = client.chat.completions.create(
            model=model,
            messages=openai_messages,
        )

        # Extract message content with fallback handling
        message_obj = response.choices[0].message
        assistant_message = message_obj.content

        # Handle None or empty responses
        if not assistant_message:
            if hasattr(message_obj, 'refusal') and message_obj.refusal:
                assistant_message = f"AI declined to respond: {message_obj.refusal}"
            else:
                logger.warning("Empty response from OpenAI API")
                assistant_message = "I apologize, but I couldn't generate a response. Please try again."

        return ChatResponse(message=assistant_message)

    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get response from AI: {str(e)}"
        )
