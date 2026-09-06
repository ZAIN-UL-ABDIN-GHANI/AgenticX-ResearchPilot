"""
Text processing and cleaning utilities.
"""

import re
from typing import List


def clean_text(text: str) -> str:
    """Clean and normalize text."""
    # Remove extra whitespace
    text = re.sub(r'\s+', ' ', text)
    # Remove special characters
    text = re.sub(r'[^\w\s\.\,\!\?\-]', '', text)
    return text.strip()


def extract_sentences(text: str) -> List[str]:
    """Extract sentences from text."""
    sentences = re.split(r'[.!?]+', text)
    return [s.strip() for s in sentences if s.strip()]


def truncate_text(text: str, max_length: int = 100) -> str:
    """Truncate text to max length."""
    if len(text) <= max_length:
        return text
    return text[:max_length-3] + "..."


def extract_word_count(text: str) -> int:
    """Count words in text."""
    return len(text.split())


def highlight_text(text: str, phrase: str) -> str:
    """Highlight phrase in text."""
    pattern = re.compile(re.escape(phrase), re.IGNORECASE)
    return pattern.sub(f"**{phrase}**", text)
