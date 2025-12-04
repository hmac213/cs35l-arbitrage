"""Chat API endpoint with OpenAI integration."""

import os
import json
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
    market_references: Optional[List[str]] = None  # List of pair_ids mentioned in the response


SYSTEM_PROMPT = """You are an arbitrage assistant for a prediction markets dashboard.

CRITICAL: Your response MUST be valid JSON with this exact structure:
{
  "message": "Your natural language response here - this is what the user will see",
  "market_references": ["pair_id_1", "pair_id_2"]  // Array of pair_ids for markets you mention
}

IMPORTANT RESPONSE GUIDELINES:
- Keep the "message" field SHORT and concise (2-4 sentences for simple questions, max 5-6 bullet points for recommendations)
- Always refer to markets by their ACTUAL NAME in the message, never by number (e.g., "Bad Bunny album market" not "#1")
- Skip lengthy explanations unless the user asks for details
- Don't list every opportunity - just mention the top 1-2 relevant ones
- Only mention risks briefly at the end, not a full list

When recommending opportunities in the "message" field:
- Lead with the market name and key profit info
- Give a simple strategy (e.g., "Buy YES on Kalshi, NO on Polymarket")
- One brief risk reminder at the end

CRITICAL FOR market_references:
- When you mention a market in your message, find its pair_id in the market context (format: [pair_id:xxx])
- Add that pair_id to the market_references array
- Only include pair_ids for markets you explicitly mention or recommend
- If you don't mention any markets, use an empty array: []
- NEVER include "market_references" text in the message field - it goes ONLY in the JSON structure

Example good response JSON:
{
  "message": "The best opportunity is the Bad Bunny album market - you can make ~74% profit per share by buying YES on Kalshi ($0.05) and NO on Polymarket ($0.03). Max potential profit is around $6,400. As always, execute both sides quickly to lock in the arbitrage.",
  "market_references": ["c05002fe-762e-4bc7-8d64-994e6b27bcf0"]
}

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

        # Call OpenAI API with structured output
        client = get_openai_client()
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        logger.info(f"Calling OpenAI with model: {model}, messages count: {len(openai_messages)}")

        # Define JSON schema for structured output
        response_schema = {
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The assistant's response message. This should be the natural language response to the user. Do NOT include market_references in this text."
                },
                "market_references": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "description": "Array of pair_ids (UUIDs) for markets explicitly mentioned or recommended in the response. Only include pair_ids that you directly reference. Leave empty array [] if no markets are mentioned.",
                    "default": []
                }
            },
            "required": ["message", "market_references"],
            "additionalProperties": False
        }

        try:
            response = client.chat.completions.create(
                model=model,
                messages=openai_messages,
                response_format={
                    "type": "json_schema",
                    "json_schema": {
                        "name": "chat_response",
                        "strict": True,
                        "schema": response_schema
                    }
                },
                temperature=0.7,
            )

            # Extract structured response
            message_obj = response.choices[0].message
            content = message_obj.content

            # Parse JSON response
            if content:
                logger.info(f"Received content from OpenAI (first 200 chars): {content[:200]}")
                try:
                    # Parse the JSON content
                    parsed_response = json.loads(content)
                    logger.info(f"Successfully parsed JSON, keys: {list(parsed_response.keys())}")
                    
                    # Extract message and market_references
                    assistant_message = parsed_response.get("message", "")
                    if not assistant_message:
                        # Fallback: if message is missing, try to use content as-is but log warning
                        logger.warning("'message' key not found in parsed response, using content")
                        assistant_message = content
                    
                    market_references_raw = parsed_response.get("market_references", [])
                    
                    # Clean and validate market_references
                    if isinstance(market_references_raw, list):
                        market_references = [ref for ref in market_references_raw if ref and isinstance(ref, str) and len(ref.strip()) > 0]
                        if not market_references:
                            market_references = None
                    else:
                        market_references = None
                    
                    # Clean message text - remove any accidental market_references mentions
                    import re
                    assistant_message = re.sub(r'\n?\s*market_references["\']?\s*:\s*\[.*?\]\s*\n?', '', assistant_message, flags=re.IGNORECASE | re.DOTALL)
                    assistant_message = assistant_message.strip()
                    
                    logger.info(f"Successfully parsed structured response - message length: {len(assistant_message)}, market_references count: {len(market_references) if market_references else 0}")
                    
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON response: {e}")
                    logger.error(f"Response content (first 500 chars): {content[:500]}")
                    # Try to extract from malformed JSON
                    assistant_message = content if content else "I apologize, but I couldn't generate a response. Please try again."
                    market_references = None
                    
                    # Try to extract market_references from text as fallback
                    import re
                    market_ref_match = re.search(r'market_references["\']?\s*:\s*\[(.*?)\]', content, re.IGNORECASE | re.DOTALL)
                    if market_ref_match:
                        refs_str = market_ref_match.group(1)
                        # Extract UUIDs or pair_ids
                        refs = re.findall(r'[\w-]{8,}', refs_str)
                        if refs:
                            market_references = refs
                            logger.info(f"Extracted market_references from text: {market_references}")
                        assistant_message = re.sub(r'\n?\s*market_references["\']?\s*:\s*\[.*?\]\s*\n?', '', assistant_message, flags=re.IGNORECASE | re.DOTALL).strip()
            else:
                logger.warning("Empty response content from OpenAI")
                assistant_message = "I apologize, but I couldn't generate a response. Please try again."
                market_references = None

        except Exception as api_error:
            # Fallback: try without structured output if the model doesn't support it
            logger.warning(f"Structured output failed, falling back to regular completion: {api_error}")
            try:
                response = client.chat.completions.create(
                    model=model,
                    messages=openai_messages,
                )
                message_obj = response.choices[0].message
                assistant_message = message_obj.content or "I apologize, but I couldn't generate a response. Please try again."
                market_references = None
            except Exception as fallback_error:
                logger.error(f"Fallback also failed: {fallback_error}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Failed to get response from AI: {str(fallback_error)}"
                )

        # Handle None or empty responses
        if not assistant_message:
            assistant_message = "I apologize, but I couldn't generate a response. Please try again."

        # Ensure we're returning the parsed message, not raw JSON
        # If assistant_message looks like JSON, try to parse it (shouldn't happen with structured output, but just in case)
        if assistant_message.strip().startswith('{') and assistant_message.strip().endswith('}'):
            try:
                # It might be a JSON string that wasn't parsed
                json_parsed = json.loads(assistant_message)
                if isinstance(json_parsed, dict) and "message" in json_parsed:
                    assistant_message = json_parsed.get("message", assistant_message)
                    if "market_references" in json_parsed and not market_references:
                        market_references_raw = json_parsed.get("market_references", [])
                        if isinstance(market_references_raw, list):
                            market_references = [ref for ref in market_references_raw if ref and isinstance(ref, str) and len(ref.strip()) > 0]
                            if not market_references:
                                market_references = None
            except (json.JSONDecodeError, AttributeError):
                # Not JSON, use as-is
                pass

        logger.info(f"Returning response - message length: {len(assistant_message)}, market_references: {market_references}")
        return ChatResponse(message=assistant_message, market_references=market_references)

    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get response from AI: {str(e)}"
        )
