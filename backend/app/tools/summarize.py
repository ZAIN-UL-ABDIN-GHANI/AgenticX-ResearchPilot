"""
Content summarization tool using Google Gemini.
"""

import json
from typing import Optional, Dict, Any
import google.generativeai as genai

from app.schemas.tools import SummarizeRequest, SummarizeResponse, KeyClaim
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

_summarization_tool = None


class SummarizationTool:
    """Tool for summarizing content using Gemini."""
    
    def __init__(self, api_key: str, model: str = "gemini-2.0-flash", timeout: int = 30):
        """Initialize the summarization tool."""
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        genai.configure(api_key=api_key)
    
    async def execute(
        self,
        source_id: str,
        content: str,
        context: Optional[str] = None,
    ) -> SummarizeResponse:
        """
        Summarize content and extract key claims.
        
        Args:
            source_id: Source identifier
            content: Content to summarize
            context: Optional context/question
        
        Returns:
            SummarizeResponse with summary and claims
        """
        try:
            # Validate input
            request = SummarizeRequest(
                source_id=source_id,
                content=content,
                context=context,
            )
            
            # Build prompt
            prompt = await self._build_prompt(request.content, request.context)
            
            # Call Gemini
            response_text = await self._call_gemini(prompt)
            
            # Parse response
            data = await self._parse_response(response_text)
            
            logger.info(
                f"Content summarized",
                extra={
                    "source_id": request.source_id,
                    "claims_count": len(data.get("key_claims", [])),
                },
            )
            
            return SummarizeResponse(
                success=True,
                source_id=request.source_id,
                summary=data.get("summary", ""),
                key_claims=[
                    KeyClaim(**claim) for claim in data.get("key_claims", [])
                ],
            )
        
        except json.JSONDecodeError as e:
            logger.error(f"JSON parse error: {str(e)}")
            return SummarizeResponse(
                success=False,
                source_id=source_id,
                error="Failed to parse response",
            )
        except Exception as e:
            logger.error(f"Summarization error: {str(e)}", exc_info=True)
            return SummarizeResponse(
                success=False,
                source_id=source_id,
                error="Summarization failed",
            )
    
    async def _build_prompt(self, content: str, context: Optional[str] = None) -> str:
        """Build the summarization prompt."""
        # Limit content to prevent token overflow
        content = content[:50000]
        
        prompt = f"""Summarize the following content and extract key claims.

Content:
{content}

"""
        if context:
            prompt += f"Context/Question: {context}\n\n"
        
        prompt += """Respond ONLY with a valid JSON object in this format (no markdown, no code blocks):
{
  "summary": "Brief 2-3 sentence summary",
  "key_claims": [
    {
      "claim": "Specific factual claim",
      "evidence": "Supporting evidence from the text",
      "confidence": 0.85
    }
  ]
}"""
        
        return prompt
    
    async def _call_gemini(self, prompt: str) -> str:
        """Call Gemini API."""
        model = genai.GenerativeModel(self.model)
        response = model.generate_content(
            prompt,
            generation_config={
                "temperature": 0.3,
                "max_output_tokens": 2000,
            },
        )
        return response.text
    
    async def _parse_response(self, response_text: str) -> Dict[str, Any]:
        """Parse Gemini response."""
        # Remove markdown code blocks if present
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.startswith("```"):
            response_text = response_text[3:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        
        data = json.loads(response_text.strip())
        
        # Validate structure
        if "summary" not in data:
            raise ValueError("Missing 'summary' in response")
        
        if "key_claims" not in data:
            data["key_claims"] = []
        
        # Validate and fix confidence values
        for claim in data["key_claims"]:
            if "confidence" in claim:
                confidence = claim["confidence"]
                if not isinstance(confidence, (int, float)):
                    try:
                        confidence = float(confidence)
                    except (ValueError, TypeError):
                        confidence = 0.5
                confidence = max(0.0, min(1.0, confidence))
                claim["confidence"] = confidence
            else:
                claim["confidence"] = 0.5
        
        return data


def get_summarization_tool() -> SummarizationTool:
    """Get or create summarization tool singleton."""
    global _summarization_tool
    if _summarization_tool is None:
        _summarization_tool = SummarizationTool(
            api_key=settings.gemini_api_key,
            model=settings.gemini_model,
            timeout=settings.gemini_timeout,
        )
    return _summarization_tool
