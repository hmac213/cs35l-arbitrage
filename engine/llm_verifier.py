"""LLM verification service for market matching using OpenAI GPT."""

import os
import logging
from typing import Dict, Optional, Any
from openai import AsyncOpenAI

from db.models import DatabaseMarket
from .config import EngineConfig
from .errors import LLMVerificationError

logger = logging.getLogger(__name__)


class LLMVerifier:
    """LLM verification service using OpenAI GPT."""
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """Initialize LLM verifier.
        
        Args:
            api_key: OpenAI API key. If None, reads from config or environment.
            model: OpenAI model name. If None, reads from config.
        """
        # Try parameter first, then config, then direct env var (in case .env wasn't loaded when config was imported)
        self.api_key = api_key or EngineConfig.OPENAI_API_KEY or os.getenv('OPENAI_API_KEY')
        self.model = model or EngineConfig.OPENAI_MODEL
        
        if not self.api_key:
            raise LLMVerificationError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.client = AsyncOpenAI(api_key=self.api_key)
        logger.info(f"[LLM] Initialized LLM verifier with model: {self.model} (async)")
    
    async def verify_markets_identical(
        self,
        market1: DatabaseMarket,
        market2: DatabaseMarket
    ) -> Dict[str, Any]:
        """Verify if two markets are identical using LLM.
        
        Uses structured tool calls (function calling) to return a boolean result.
        
        Args:
            market1: First market to compare.
            market2: Second market to compare.
            
        Returns:
            Dictionary with keys:
            - is_identical: bool
            - confidence: float (0.0-1.0)
            - reasoning: str (optional explanation)
        """
        # Prepare market information for prompt
        market1_info = self._format_market_info(market1)
        market2_info = self._format_market_info(market2)
        
        # Prompt engineering: structured to guide LLM toward accurate matching
        # Key considerations:
        # 1. Emphasize "same question AND same outcome" - markets can ask similar questions
        #    but resolve differently (e.g., "Will X happen?" vs "Will X NOT happen?")
        # 2. Resolution criteria matter - markets with different rules aren't identical even
        #    if they seem similar (e.g., "Will X win?" vs "Will X win by >5 points?")
        # 3. Outcome space must match - binary markets can't match multi-outcome markets
        # 4. Wording differences are acceptable if meaning is preserved (semantic equivalence)
        # The low temperature (0.1) ensures consistent, deterministic results across runs
        prompt = f"""You are an expert at analyzing prediction markets. Your task is to determine if two prediction markets are asking the same question and will resolve to the same outcome.

Market 1 ({market1.exchange}):
{market1_info}

Market 2 ({market2.exchange}):
{market2_info}

Are these two prediction markets asking the same question and resolving to the same outcome? Consider:
- The core question being asked
- The resolution criteria
- The outcome space (binary vs multi-outcome)
- Any differences in wording that don't change the meaning

Respond with a clear yes or no answer using the provided function."""
        
        # Define the function/tool for structured output
        tools = [
            {
                "type": "function",
                "function": {
                    "name": "verify_market_match",
                    "description": "Verify if two prediction markets are identical",
                    "parameters": {
                        "type": "object",
                        "properties": {
                            "is_identical": {
                                "type": "boolean",
                                "description": "True if the markets are asking the same question and resolve to the same outcome, False otherwise"
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence level from 0.0 to 1.0",
                                "minimum": 0.0,
                                "maximum": 1.0
                            },
                            "reasoning": {
                                "type": "string",
                                "description": "Brief explanation of the decision (optional)"
                            }
                        },
                        "required": ["is_identical", "confidence"]
                    }
                }
            }
        ]
        
        try:
            logger.info(f"[LLM] Calling OpenAI API (model: {self.model}) to verify markets...")
            logger.debug(f"[LLM] Market 1: {market1.market_id} ({market1.exchange}) - {market1.name}")
            logger.debug(f"[LLM] Market 2: {market2.market_id} ({market2.exchange}) - {market2.name}")
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing prediction markets. Always use the verify_market_match function to respond."},
                    {"role": "user", "content": prompt}
                ],
                tools=tools,
                # Force function calling to ensure structured output - prevents LLM from
                # returning free-form text that would require parsing. This guarantees
                # we receive a boolean is_identical and float confidence in a parseable format.
                tool_choice={"type": "function", "function": {"name": "verify_market_match"}},
                # Low temperature (0.1) for deterministic, consistent results
                # Higher temperature would introduce variability that could cause the same
                # market pair to be verified differently on repeated runs
                temperature=0.1
            )
            
            logger.debug(f"[LLM] Received response from OpenAI API")
            
            # Extract function call result
            message = response.choices[0].message
            
            if message.tool_calls and len(message.tool_calls) > 0:
                tool_call = message.tool_calls[0]
                import json
                arguments = json.loads(tool_call.function.arguments)
                
                result = {
                    "is_identical": bool(arguments.get("is_identical", False)),
                    "confidence": float(arguments.get("confidence", 0.0)),
                    "reasoning": arguments.get("reasoning", "")
                }
                
                logger.info(
                    f"[LLM] ✓ Verification complete: markets {market1.market_id} and {market2.market_id} - "
                    f"identical: {result['is_identical']}, confidence: {result['confidence']:.4f}"
                )
                
                if result.get('reasoning'):
                    logger.debug(f"[LLM] Reasoning: {result['reasoning']}")
                
                return result
            else:
                logger.error(f"[LLM] ✗ LLM did not return a function call response")
                raise LLMVerificationError("LLM did not return a function call response")
                
        except Exception as e:
            if isinstance(e, LLMVerificationError):
                raise
            raise LLMVerificationError(f"Failed to verify markets with LLM: {str(e)}") from e
    
    def _format_market_info(self, market: DatabaseMarket) -> str:
        """Format market information for LLM prompt.
        
        Args:
            market: DatabaseMarket instance.
            
        Returns:
            Formatted string with market information.
        """
        parts = []
        
        parts.append(f"Market ID: {market.market_id}")
        parts.append(f"Name: {market.name or 'N/A'}")
        
        if market.rules:
            parts.append(f"Rules: {market.rules}")
        
        if market.description:
            parts.append(f"Description: {market.description}")
        
        if market.resolve_date:
            parts.append(f"Resolve Date: {market.resolve_date}")
            if market.resolve_time:
                parts.append(f"Resolve Time: {market.resolve_time}")
        
        if market.category:
            parts.append(f"Category: {market.category}")
        
        if market.subcategory:
            parts.append(f"Subcategory: {market.subcategory}")
        
        return "\n".join(parts)

