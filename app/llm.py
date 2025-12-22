"""LLM integration layer with Claude API."""

import json
import logging
import asyncio
from typing import Dict, Any, Optional
from anthropic import AsyncAnthropic

from app.config import settings

logger = logging.getLogger(__name__)

# Initialize Anthropic client
client = AsyncAnthropic(api_key=settings.anthropic_api_key)

# Beta version for structured outputs
STRUCTURED_OUTPUTS_BETA = "structured-outputs-2025-11-13"


class LLMError(Exception):
    """Base exception for LLM-related errors."""
    pass


async def call_claude(
    prompt: str,
    system: str,
    temperature: float = 0.0,
    max_tokens: int = 2048,
    max_retries: int = 3
) -> str:
    """
    Call Claude API with retry logic.

    Args:
        prompt: User prompt
        system: System prompt
        temperature: Sampling temperature (0.0 for deterministic)
        max_tokens: Maximum tokens in response
        max_retries: Maximum number of retry attempts

    Returns:
        Response text from Claude

    Raises:
        LLMError: If all retries fail
    """
    for attempt in range(max_retries):
        try:
            response = await client.messages.create(
                model=settings.claude_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )

            # Extract text from response
            text_content = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    text_content += block.text

            # Log token usage
            logger.info(
                f"Claude API call successful - "
                f"Input: {response.usage.input_tokens}, "
                f"Output: {response.usage.output_tokens}"
            )

            return text_content

        except Exception as e:
            wait_time = 2 ** attempt  # Exponential backoff
            logger.warning(
                f"Claude API call failed (attempt {attempt + 1}/{max_retries}): {e}"
            )

            if attempt < max_retries - 1:
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                raise LLMError(f"Claude API failed after {max_retries} attempts: {e}")


async def call_claude_json(
    prompt: str,
    system: str,
    temperature: float = 0.0,
    max_tokens: int = 2048
) -> Dict[str, Any]:
    """
    Call Claude and parse JSON response.

    Args:
        prompt: User prompt
        system: System prompt (should instruct to return JSON)
        temperature: Sampling temperature
        max_tokens: Maximum tokens in response

    Returns:
        Parsed JSON response as dict

    Raises:
        LLMError: If API fails or response is not valid JSON
    """
    response_text = await call_claude(prompt, system, temperature, max_tokens)

    try:
        # Try to extract JSON from markdown code blocks if present
        if "```json" in response_text:
            start = response_text.find("```json") + 7
            end = response_text.find("```", start)
            json_text = response_text[start:end].strip()
        elif "```" in response_text:
            start = response_text.find("```") + 3
            end = response_text.find("```", start)
            json_text = response_text[start:end].strip()
        else:
            json_text = response_text.strip()

        return json.loads(json_text)

    except json.JSONDecodeError as e:
        logger.error(f"Failed to parse JSON from Claude response: {response_text}")
        raise LLMError(f"Invalid JSON response from Claude: {e}")


async def validate_json_structure(
    data: Dict[str, Any],
    required_fields: list[str]
) -> None:
    """
    Validate that JSON response has required fields.

    Args:
        data: JSON data to validate
        required_fields: List of required field names

    Raises:
        LLMError: If required fields are missing
    """
    missing = [field for field in required_fields if field not in data]
    if missing:
        raise LLMError(f"Missing required fields in LLM response: {missing}")


async def call_claude_structured(
    prompt: str,
    system: str,
    json_schema: Dict[str, Any],
    temperature: float = 0.0,
    max_tokens: int = 2048,
    max_retries: int = 3
) -> Dict[str, Any]:
    """
    Call Claude API with structured outputs (guaranteed schema compliance).

    This uses the new structured outputs beta feature to guarantee that Claude's
    response will always match the provided JSON schema, eliminating parsing errors
    and schema validation issues.

    Args:
        prompt: User prompt
        system: System prompt
        json_schema: JSON schema that response must follow
        temperature: Sampling temperature (0.0 for deterministic)
        max_tokens: Maximum tokens in response
        max_retries: Maximum number of retry attempts

    Returns:
        Parsed JSON response matching the schema

    Raises:
        LLMError: If all retries fail
    """
    for attempt in range(max_retries):
        try:
            response = await client.beta.messages.create(
                model=settings.claude_model,
                max_tokens=max_tokens,
                temperature=temperature,
                system=system,
                betas=[STRUCTURED_OUTPUTS_BETA],
                messages=[
                    {"role": "user", "content": prompt}
                ],
                output_format={
                    "type": "json_schema",
                    "schema": json_schema
                }
            )

            # Extract JSON from response (guaranteed to match schema)
            json_text = ""
            for block in response.content:
                if hasattr(block, 'text'):
                    json_text += block.text

            # Log token usage
            logger.info(
                f"Claude API call successful (structured) - "
                f"Input: {response.usage.input_tokens}, "
                f"Output: {response.usage.output_tokens}"
            )

            # Parse the JSON (will always be valid due to structured outputs)
            return json.loads(json_text)

        except Exception as e:
            wait_time = 2 ** attempt  # Exponential backoff
            logger.warning(
                f"Claude API call failed (attempt {attempt + 1}/{max_retries}): {e}"
            )

            if attempt < max_retries - 1:
                logger.info(f"Retrying in {wait_time} seconds...")
                await asyncio.sleep(wait_time)
            else:
                raise LLMError(f"Claude API failed after {max_retries} attempts: {e}")
