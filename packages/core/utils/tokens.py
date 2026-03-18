"""
Token counting utilities.
Uses tiktoken cl100k_base — matches OpenAI embedding model tokenization.
Falls back to word-count approximation when tiktoken vocab is unavailable
(e.g. in network-sandboxed test environments).
"""
from __future__ import annotations
import functools
import math
from typing import Optional

try:
    import tiktoken

    @functools.lru_cache(maxsize=1)
    def _get_encoding():
        """Cache the encoding object — initialisation is expensive."""
        return tiktoken.get_encoding("cl100k_base")

    def count_tokens(text: str) -> int:
        """Count tokens using cl100k_base encoding."""
        if not text:
            return 0
        try:
            return len(_get_encoding().encode(text))
        except Exception:
            return _approx_token_count(text)

    def truncate_to_tokens(text: str, max_tokens: int) -> str:
        """Truncate text to at most max_tokens tokens."""
        try:
            enc = _get_encoding()
            tokens = enc.encode(text)
            if len(tokens) <= max_tokens:
                return text
            return enc.decode(tokens[:max_tokens])
        except Exception:
            return _approx_truncate(text, max_tokens)

except Exception:
    # tiktoken import failed entirely
    def count_tokens(text: str) -> int:  # type: ignore[misc]
        if not text:
            return 0
        return _approx_token_count(text)

    def truncate_to_tokens(text: str, max_tokens: int) -> str:  # type: ignore[misc]
        return _approx_truncate(text, max_tokens)


def _approx_token_count(text: str) -> int:
    """Approximate token count: ~0.75 words per token (GPT convention)."""
    if not text:
        return 0
    word_count = len(text.split())
    return math.ceil(word_count / 0.75)


def _approx_truncate(text: str, max_tokens: int) -> str:
    """Approximate truncation by word count."""
    words = text.split()
    max_words = math.floor(max_tokens * 0.75)
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def fits_in_tokens(text: str, max_tokens: int) -> bool:
    """Return True if text fits within max_tokens."""
    return count_tokens(text) <= max_tokens
