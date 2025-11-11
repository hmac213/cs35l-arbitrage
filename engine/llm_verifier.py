"""LLM verification service for market matching using OpenAI GPT."""

import logging
from typing import Dict, Optional, Any
from openai import OpenAI

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
            api_key: OpenAI API key. If None, reads from config.
            model: OpenAI model name. If None, reads from config.
        """
        self.api_key = api_key or EngineConfig.OPENAI_API_KEY
        self.model = model or EngineConfig.OPENAI_MODEL
        
        if not self.api_key:
            raise LLMVerificationError("OpenAI API key is required. Set OPENAI_API_KEY environment variable.")
        
        self.client = OpenAI(api_key=self.api_key)
    
    def verify_markets_identical(
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
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are an expert at analyzing prediction markets. Always use the verify_market_match function to respond."},
                    {"role": "user", "content": prompt}
                ],
                tools=tools,
                tool_choice={"type": "function", "function": {"name": "verify_market_match"}},
                temperature=0.1  # Low temperature for more deterministic results
            )
            
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
                
                logger.debug(
                    f"LLM verification: markets {market1.market_id} and {market2.market_id} - "
                    f"identical: {result['is_identical']}, confidence: {result['confidence']}"
                )
                
                return result
            else:
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

