"""
All shared constants for Verus.
Change here — it changes everywhere.
Every numeric threshold, every model name, every limit.
"""

# ── LLM ───────────────────────────────────────────────────────────────────────
PRIMARY_LLM           = "claude-sonnet-4-20250514"
EMBEDDING_MODEL       = "text-embedding-3-large"
EMBEDDING_DIMENSIONS  = 1536        # text-embedding-3-large with truncation (pgvector 0.6 max for indexed search)
EMBEDDING_BATCH_SIZE  = 100         # OpenAI max batch per request
RERANK_MODEL          = "rerank-v3.5"  # Cohere rerank

# ── CHUNKING ──────────────────────────────────────────────────────────────────
CHUNK_TARGET_TOKENS   = 512
CHUNK_MIN_TOKENS      = 80     # Minimum viable chunk — below this merge with previous
CHUNK_OVERLAP_TOKENS  = 64     # Overlap between adjacent chunks — MUST be < CHUNK_MIN_TOKENS
CHUNK_MAX_TABLE_TOKENS = 2048       # Tables > this split into row groups
TABLE_ROW_GROUP_SIZE  = 20          # Rows per row-group chunk

# ── CLAIM EXTRACTION ──────────────────────────────────────────────────────────
MAX_CLAIMS_PER_CHUNK      = 20
MIN_CLAIM_MATERIALITY     = 0.5     # Claims below excluded from reasoning
DOMAIN_CAP_COMMERCIAL     = 50
DOMAIN_CAP_OPERATIONAL    = 40
DOMAIN_CAP_FINANCIAL      = 40
DOMAIN_CAP_HUMAN_CAPITAL  = 20
DEDUP_SIMILARITY_THRESHOLD = 0.92   # Cosine similarity for deduplication

# ── CONFIDENCE TIERS ──────────────────────────────────────────────────────────
CONFIDENCE_VERIFIED  = 0.85         # >= VERIFIED
CONFIDENCE_PROBABLE  = 0.65         # >= PROBABLE, < VERIFIED
                                    # < PROBABLE = INDICATIVE

# ── REASONING ─────────────────────────────────────────────────────────────────
MAX_THREAD_DEPTH         = 3
MAX_THREADS_PER_FINDING  = 3
REASONING_REVISION_LIMIT = 2        # Max evidence enforcer revision cycles

# ── CONNECTOR ─────────────────────────────────────────────────────────────────
CONNECTOR_TIMEOUT_SECONDS    = 30
CONNECTOR_HEALTH_CHECK_SECS  = 10
CREDENTIAL_CACHE_TTL_SECS    = 3300  # 55 min (tokens expire at 60)
MAX_RECORDS_PER_QUERY        = 10000
CONNECTOR_MAX_QUERIES_PER_HR = 50    # CASA rate limit trigger

# ── DATA QUALITY ──────────────────────────────────────────────────────────────
DQ_MIN_COMPLETENESS    = 0.70
DQ_MIN_HISTORY_MONTHS  = 12
DQ_MIN_CONSISTENCY     = 0.85

# ── STORAGE — S3 key templates (format with .format(**kwargs)) ─────────────
S3_RAW_KEY          = "{engagement_id}/raw/{document_id}/{filename}"
S3_NORMALIZED_KEY   = "{engagement_id}/normalized/{document_id}/output.json"
S3_CHUNKS_KEY       = "{engagement_id}/chunks/{document_id}/chunks.json"
S3_DELIVERABLES_DIR = "{engagement_id}/deliverables/"
S3_PLAN_KEY         = "{engagement_id}/plan/{plan_id}/{filename}"

# ── VAULT ─────────────────────────────────────────────────────────────────────
VAULT_CONNECTOR_PATH = "secret/engagements/{engagement_id}/connectors/{connector_type}"

# ── TIMEOUTS ──────────────────────────────────────────────────────────────────
INGESTION_TASK_TIMEOUT_SECS  = 1800    # 30 min per document
REASONING_TASK_TIMEOUT_SECS  = 21600   # 6 hours
CHAT_RESPONSE_TIMEOUT_SECS   = 60

# ── RETENTION ─────────────────────────────────────────────────────────────────
ENGAGEMENT_RETENTION_DAYS = 90          # Delete all data 90 days after close

# ── EVIDENCE LEDGER ───────────────────────────────────────────────────────────
LEDGER_HASH_SEPARATOR = "|"             # Separator in hash payloads

# ── CHAT ──────────────────────────────────────────────────────────────────────
CHAT_MAX_HISTORY_TURNS     = 20
CHAT_MAX_RETRIEVED_CHUNKS  = 10
CHAT_CONTEXT_TOKEN_LIMIT   = 100_000    # Truncate context above this
CHAT_SUGGESTED_FOLLOWUPS   = 3

# ── SPECULATIVE LANGUAGE — phrases that fail evidence integrity check ─────────
SPECULATIVE_PHRASES = [
    "might", "could suggest", "possibly", "it appears",
    "may indicate", "seems to", "presumably", "arguably",
    "one might think", "it's possible that",
]
