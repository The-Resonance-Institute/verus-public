"""
Test: packages/core/constants.py

Constants are the tunable parameters of the system.
Wrong constants cause subtle bugs that are expensive to find in production.
These tests verify that constants are internally consistent and within
sensible bounds — not just that they import.
"""

import pytest
from packages.core.constants import (
    PRIMARY_LLM, EMBEDDING_MODEL, EMBEDDING_DIMENSIONS, EMBEDDING_BATCH_SIZE,
    CHUNK_TARGET_TOKENS, CHUNK_MIN_TOKENS, CHUNK_OVERLAP_TOKENS,
    CHUNK_MAX_TABLE_TOKENS, TABLE_ROW_GROUP_SIZE,
    MAX_CLAIMS_PER_CHUNK, MIN_CLAIM_MATERIALITY,
    DOMAIN_CAP_COMMERCIAL, DOMAIN_CAP_OPERATIONAL,
    DOMAIN_CAP_FINANCIAL, DOMAIN_CAP_HUMAN_CAPITAL,
    DEDUP_SIMILARITY_THRESHOLD,
    CONFIDENCE_VERIFIED, CONFIDENCE_PROBABLE,
    MAX_THREAD_DEPTH, MAX_THREADS_PER_FINDING, REASONING_REVISION_LIMIT,
    CONNECTOR_TIMEOUT_SECONDS, CREDENTIAL_CACHE_TTL_SECS,
    MAX_RECORDS_PER_QUERY, CONNECTOR_MAX_QUERIES_PER_HR,
    DQ_MIN_COMPLETENESS, DQ_MIN_HISTORY_MONTHS, DQ_MIN_CONSISTENCY,
    ENGAGEMENT_RETENTION_DAYS, LEDGER_HASH_SEPARATOR,
    CHAT_MAX_HISTORY_TURNS, CHAT_CONTEXT_TOKEN_LIMIT,
    SPECULATIVE_PHRASES,
)


class TestLLMConstants:
    def test_model_strings_non_empty(self):
        assert len(PRIMARY_LLM) > 10, "PRIMARY_LLM looks wrong"
        assert len(EMBEDDING_MODEL) > 5, "EMBEDDING_MODEL looks wrong"

    def test_embedding_dimensions_correct(self):
        # text-embedding-3-large produces exactly 3072 dimensions
        # Wrong value here breaks Qdrant collection creation
        assert EMBEDDING_DIMENSIONS == 1536  # pgvector 0.6 HNSW limit; text-embedding-3-large supports truncation

    def test_embedding_batch_size_positive(self):
        assert 1 <= EMBEDDING_BATCH_SIZE <= 2048


class TestChunkingConstants:
    def test_token_hierarchy_is_consistent(self):
        """
        Overlap < Min < Target is the only valid ordering.
        If overlap >= min, chunks cannot be distinguished.
        If min >= target, every chunk triggers a merge.
        """
        assert CHUNK_OVERLAP_TOKENS < CHUNK_MIN_TOKENS, (
            f"Overlap ({CHUNK_OVERLAP_TOKENS}) must be < min ({CHUNK_MIN_TOKENS})"
        )
        assert CHUNK_MIN_TOKENS < CHUNK_TARGET_TOKENS, (
            f"Min ({CHUNK_MIN_TOKENS}) must be < target ({CHUNK_TARGET_TOKENS})"
        )

    def test_table_chunk_limit_larger_than_target(self):
        # Tables split only when they exceed this — must be larger than normal chunks
        assert CHUNK_MAX_TABLE_TOKENS > CHUNK_TARGET_TOKENS

    def test_row_group_size_reasonable(self):
        assert 5 <= TABLE_ROW_GROUP_SIZE <= 100


class TestClaimConstants:
    def test_max_claims_per_chunk_reasonable(self):
        # Too low: misses claims. Too high: noise dominates.
        assert 5 <= MAX_CLAIMS_PER_CHUNK <= 50

    def test_materiality_threshold_is_fraction(self):
        assert 0.0 < MIN_CLAIM_MATERIALITY < 1.0

    def test_domain_caps_are_positive(self):
        for cap in [DOMAIN_CAP_COMMERCIAL, DOMAIN_CAP_OPERATIONAL,
                    DOMAIN_CAP_FINANCIAL, DOMAIN_CAP_HUMAN_CAPITAL]:
            assert cap > 0

    def test_commercial_has_highest_cap(self):
        # Commercial claims (revenue, pipeline, customers) are highest-density
        assert DOMAIN_CAP_COMMERCIAL >= DOMAIN_CAP_OPERATIONAL
        assert DOMAIN_CAP_COMMERCIAL >= DOMAIN_CAP_FINANCIAL
        assert DOMAIN_CAP_COMMERCIAL >= DOMAIN_CAP_HUMAN_CAPITAL

    def test_dedup_threshold_is_high(self):
        # Below 0.85: too many false duplicates. Above 0.98: misses real duplicates.
        assert 0.85 <= DEDUP_SIMILARITY_THRESHOLD <= 0.98


class TestConfidenceTiers:
    def test_tiers_are_ordered(self):
        """VERIFIED > PROBABLE > 0 — any other ordering breaks the tier logic."""
        assert CONFIDENCE_PROBABLE < CONFIDENCE_VERIFIED
        assert 0.0 < CONFIDENCE_PROBABLE
        assert CONFIDENCE_VERIFIED < 1.0

    def test_indicative_is_below_probable(self):
        # Anything below CONFIDENCE_PROBABLE is INDICATIVE
        # Verify the gap is meaningful (not e.g. 0.649 vs 0.650)
        assert CONFIDENCE_PROBABLE >= 0.5, "PROBABLE threshold too low"
        assert CONFIDENCE_VERIFIED >= 0.75, "VERIFIED threshold too low"


class TestReasoningConstants:
    def test_thread_depth_bounded(self):
        # Too low: misses corroborating evidence.
        # Too high: exponential query explosion (3^depth queries at worst).
        assert 2 <= MAX_THREAD_DEPTH <= 5

    def test_threads_per_finding_bounded(self):
        assert 1 <= MAX_THREADS_PER_FINDING <= 5

    def test_maximum_query_explosion(self):
        # Worst case: MAX_THREADS_PER_FINDING ^ MAX_THREAD_DEPTH additional queries
        # Must be manageable within the 6-hour reasoning window
        max_additional_queries = MAX_THREADS_PER_FINDING ** MAX_THREAD_DEPTH
        assert max_additional_queries <= 125, (
            f"Max query explosion ({max_additional_queries}) too high for "
            f"6-hour reasoning window"
        )

    def test_revision_limit_low(self):
        # Revision loop must terminate. Never more than 3 revisions.
        assert 1 <= REASONING_REVISION_LIMIT <= 3


class TestConnectorConstants:
    def test_timeout_reasonable(self):
        assert 10 <= CONNECTOR_TIMEOUT_SECONDS <= 120

    def test_credential_cache_shorter_than_one_hour(self):
        # Tokens typically expire at 3600s. Cache must expire first.
        assert CREDENTIAL_CACHE_TTL_SECS < 3600
        assert CREDENTIAL_CACHE_TTL_SECS > 0

    def test_max_records_reasonable(self):
        assert 1000 <= MAX_RECORDS_PER_QUERY <= 100_000

    def test_casa_rate_limit_threshold(self):
        # CASA triggers GOVERN above this many queries/hour
        assert 10 <= CONNECTOR_MAX_QUERIES_PER_HR <= 500


class TestDataQualityConstants:
    def test_completeness_is_fraction(self):
        assert 0.0 < DQ_MIN_COMPLETENESS < 1.0

    def test_history_months_reasonable(self):
        # Less than 6: data too sparse for trend claims.
        # More than 24: unreasonably strict for diligence window.
        assert 6 <= DQ_MIN_HISTORY_MONTHS <= 24

    def test_consistency_is_fraction(self):
        assert 0.0 < DQ_MIN_CONSISTENCY < 1.0


class TestRetentionConstants:
    def test_retention_at_least_30_days(self):
        # Must give deal teams time to download deliverables
        assert ENGAGEMENT_RETENTION_DAYS >= 30

    def test_retention_at_most_365_days(self):
        # Beyond 1 year: unnecessary data liability
        assert ENGAGEMENT_RETENTION_DAYS <= 365


class TestHashingConstants:
    def test_separator_is_single_char(self):
        assert len(LEDGER_HASH_SEPARATOR) == 1

    def test_separator_not_in_uuids(self):
        # UUID format: 550e8400-e29b-41d4-a716-446655440000
        # Separator must not appear in UUID strings
        import uuid
        sample_uuid = str(uuid.uuid4())
        assert LEDGER_HASH_SEPARATOR not in sample_uuid


class TestChatConstants:
    def test_history_turns_reasonable(self):
        assert 5 <= CHAT_MAX_HISTORY_TURNS <= 50

    def test_context_token_limit_large_enough(self):
        # Must fit: system prompt (~2K) + findings (~10K) + history (~20K) + chunks (~10K)
        assert CHAT_CONTEXT_TOKEN_LIMIT >= 50_000


class TestSpeculativePhrases:
    def test_list_non_empty(self):
        assert len(SPECULATIVE_PHRASES) > 0

    def test_all_lowercase(self):
        # Detection uses .lower() — phrases must be lowercase to match
        for phrase in SPECULATIVE_PHRASES:
            assert phrase == phrase.lower(), (
                f"Speculative phrase must be lowercase: '{phrase}'"
            )

    def test_critical_phrases_present(self):
        # These are the most common hallucination markers
        for required in ["might", "possibly", "seems to", "may indicate"]:
            assert required in SPECULATIVE_PHRASES, (
                f"Critical speculative phrase missing: '{required}'"
            )
