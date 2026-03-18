"""
Test: Row Level Security isolation and INSERT-ONLY enforcement.

ARCHITECTURE:
  verus     (superuser) — seeds test data via committed transactions
  verus_app (app role)  — queries with RLS enforced

RLS is enforced only for non-superuser roles. The application service
in production must use a non-superuser role. These tests verify that
the non-superuser app role cannot access data outside its engagement context.

Every test cleans up after itself in a finally block.
"""

import os
import pytest

pytestmark = pytest.mark.integration
import psycopg2
from uuid import uuid4

SUPER_URL = "postgresql://verus:verus@127.0.0.1:5432/verus_test"
APP_URL   = "postgresql://verus_app:verus_app@127.0.0.1:5432/verus_test"


def super_conn():
    c = psycopg2.connect(SUPER_URL)
    c.autocommit = True
    return c


def app_conn():
    c = psycopg2.connect(APP_URL)
    c.autocommit = True
    return c


def make_engagement_id():
    return str(uuid4())


def seed_engagement(sc, eng_id: str):
    """Insert engagement via superuser (committed immediately)."""
    with sc.cursor() as cur:
        cur.execute("""
            INSERT INTO engagements
                (engagement_id, deal_name, target_company,
                 window_start, window_end, created_by)
            VALUES (%s, 'RLS Test Deal', 'RLS Test Corp',
                    NOW(), NOW() + INTERVAL '28 days', %s)
            ON CONFLICT DO NOTHING
        """, (eng_id, str(uuid4())))


def seed_claim(sc, eng_id: str) -> str:
    """Insert one claim via superuser. Returns claim_id."""
    claim_id = str(uuid4())
    with sc.cursor() as cur:
        cur.execute("""
            INSERT INTO claims
                (claim_id, engagement_id, chunk_id, document_id,
                 claim_text, claim_type, domain, materiality, source_citation)
            VALUES
                (%s, %s, %s, %s,
                 'Revenue grew 23%% YoY in FY2024',
                 'explicit_numeric', 'commercial', 0.9, 'CIM.pdf, p.14')
        """, (claim_id, eng_id, str(uuid4()), str(uuid4())))
    return claim_id


def cleanup(sc, eng_id: str):
    """Delete all test data for an engagement.

    INSERT-ONLY tables (evidence_ledger, connector_audit_log, chat_messages)
    have DELETE rules that silently discard DELETEs. To clean them up in tests
    we disable session_replication_role to bypass rules (superuser only).
    This is safe because cleanup only runs in the test superuser connection.
    """
    with sc.cursor() as cur:
        # Bypass INSERT-ONLY rules for cleanup (test superuser only)
        cur.execute("SET session_replication_role = replica")
        for table in [
            "stress_test_assessments", "initiatives", "plan_documents",
            "chat_messages",          # before chat_sessions (FK)
            "chat_sessions",
            "evidence_ledger", "connector_audit_log",
            "findings", "hypotheses",
            "entities", "claims",
            "document_chunks", "documents",
            "engagement_connectors", "engagements",
        ]:
            cur.execute(
                f"DELETE FROM {table} WHERE engagement_id = %s",
                (eng_id,)
            )
        cur.execute("SET session_replication_role = DEFAULT")


def count_with_context(ac, table: str, eng_id: str) -> int:
    """Query table using app role with given engagement context."""
    with ac.cursor() as cur:
        cur.execute("SET app.engagement_id = %s", (eng_id,))
        cur.execute(f"SELECT count(*) FROM {table}")
        return cur.fetchone()[0]


# ═════════════════════════════════════════════════════════════════════════════
# CORE ISOLATION TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestRLSClaimsIsolation:
    def test_claims_invisible_to_wrong_engagement(self):
        """
        CRITICAL: Claims for engagement A must be completely invisible
        when querying with engagement B's context.
        """
        eng_a = make_engagement_id()
        eng_b = make_engagement_id()
        sc = super_conn()
        ac = app_conn()
        try:
            seed_engagement(sc, eng_a)
            seed_claim(sc, eng_a)

            count = count_with_context(ac, "claims", eng_b)
            assert count == 0, (
                f"RLS FAILURE: engagement B context sees {count} claim(s) "
                f"from engagement A. Deal data isolation is broken."
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()
            ac.close()

    def test_claims_visible_in_correct_engagement(self):
        """Claims are visible when querying with the correct engagement context."""
        eng_a = make_engagement_id()
        sc = super_conn()
        ac = app_conn()
        try:
            seed_engagement(sc, eng_a)
            seed_claim(sc, eng_a)
            seed_claim(sc, eng_a)  # two claims

            count = count_with_context(ac, "claims", eng_a)
            assert count == 2, (
                f"Expected 2 claims visible to correct engagement, got {count}"
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()
            ac.close()

    def test_no_context_sees_nothing(self):
        """With no engagement context, no data is visible."""
        eng_a = make_engagement_id()
        sc = super_conn()
        ac = app_conn()
        try:
            seed_engagement(sc, eng_a)
            seed_claim(sc, eng_a)

            # Query with null UUID context (no engagement set)
            with ac.cursor() as cur:
                cur.execute("SET app.engagement_id = %s",
                            ("00000000-0000-0000-0000-000000000000",))
                cur.execute("SELECT count(*) FROM claims")
                count = cur.fetchone()[0]

            assert count == 0, (
                f"Null engagement context should see 0 claims, got {count}"
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()
            ac.close()


class TestRLSFindingsIsolation:
    def test_findings_invisible_to_wrong_engagement(self):
        eng_a = make_engagement_id()
        eng_b = make_engagement_id()
        sc = super_conn()
        ac = app_conn()
        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO findings
                        (engagement_id, finding_code, domain, verdict,
                         materiality, confidence, management_claim, claim_citation)
                    VALUES
                        (%s, 'COM-001', 'commercial', 'DIVERGENT',
                         'HIGH', 0.88,
                         'Revenue grew 23%% YoY', 'CIM.pdf, p.14')
                """, (eng_a,))

            count = count_with_context(ac, "findings", eng_b)
            assert count == 0, (
                f"RLS FAILURE: findings from A visible to B ({count} rows)"
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()
            ac.close()


class TestRLSEvidenceLedgerIsolation:
    def test_ledger_invisible_to_wrong_engagement(self):
        eng_a = make_engagement_id()
        eng_b = make_engagement_id()
        sc = super_conn()
        ac = app_conn()
        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO evidence_ledger
                        (engagement_id, entry_type, object_id,
                         object_hash, recorded_by)
                    VALUES
                        (%s, 'chunk', %s, %s, 'ingestion-worker')
                """, (eng_a, str(uuid4()), "a" * 64))

            count = count_with_context(ac, "evidence_ledger", eng_b)
            assert count == 0, (
                f"RLS FAILURE: evidence_ledger from A visible to B ({count} rows)"
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()
            ac.close()

    def test_ledger_visible_in_correct_engagement(self):
        eng_a = make_engagement_id()
        sc = super_conn()
        ac = app_conn()
        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO evidence_ledger
                        (engagement_id, entry_type, object_id,
                         object_hash, recorded_by)
                    VALUES (%s, 'chunk', %s, %s, 'test')
                """, (eng_a, str(uuid4()), "b" * 64))

            count = count_with_context(ac, "evidence_ledger", eng_a)
            assert count == 1
        finally:
            cleanup(sc, eng_a)
            sc.close()
            ac.close()


class TestRLSAuditLogIsolation:
    def test_audit_log_invisible_to_wrong_engagement(self):
        eng_a = make_engagement_id()
        eng_b = make_engagement_id()
        sc = super_conn()
        ac = app_conn()
        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO connector_audit_log
                        (engagement_id, query_id, connector_type, query_intent,
                         domain, parameters_hash, executed_at,
                         duration_ms, record_count, success)
                    VALUES
                        (%s, %s, 'salesforce', 'pipeline_summary',
                         'commercial', %s, NOW(), 250, 47, TRUE)
                """, (eng_a, str(uuid4()), "a" * 64))

            count = count_with_context(ac, "connector_audit_log", eng_b)
            assert count == 0, (
                f"RLS FAILURE: audit_log from A visible to B ({count} rows)"
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()
            ac.close()


class TestRLSDocumentsIsolation:
    def test_documents_invisible_to_wrong_engagement(self):
        eng_a = make_engagement_id()
        eng_b = make_engagement_id()
        sc = super_conn()
        ac = app_conn()
        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO documents
                        (engagement_id, source, original_filename,
                         file_extension, file_size_bytes, s3_key)
                    VALUES
                        (%s, 'direct_upload', 'CIM.pdf',
                         'pdf', 4200000, %s)
                """, (eng_a, f"{eng_a}/raw/abc/CIM.pdf"))

            count = count_with_context(ac, "documents", eng_b)
            assert count == 0, (
                f"RLS FAILURE: documents from A visible to B ({count} rows)"
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()
            ac.close()


class TestRLSHypothesesIsolation:
    def test_hypotheses_invisible_to_wrong_engagement(self):
        eng_a = make_engagement_id()
        eng_b = make_engagement_id()
        sc = super_conn()
        ac = app_conn()
        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO hypotheses
                        (engagement_id, source_claim_id, hypothesis_text,
                         domain, materiality)
                    VALUES
                        (%s, %s,
                         'Salesforce will show 20-25%% YoY pipeline growth',
                         'commercial', 0.9)
                """, (eng_a, str(uuid4())))

            count = count_with_context(ac, "hypotheses", eng_b)
            assert count == 0
        finally:
            cleanup(sc, eng_a)
            sc.close()
            ac.close()


class TestRLSChatIsolation:
    def test_chat_sessions_invisible_to_wrong_engagement(self):
        eng_a = make_engagement_id()
        eng_b = make_engagement_id()
        sc = super_conn()
        ac = app_conn()
        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO chat_sessions (engagement_id, user_id)
                    VALUES (%s, %s)
                """, (eng_a, str(uuid4())))

            count = count_with_context(ac, "chat_sessions", eng_b)
            assert count == 0
        finally:
            cleanup(sc, eng_a)
            sc.close()
            ac.close()


class TestMultiEngagementCrossContamination:
    def test_ten_engagements_fully_isolated(self):
        """
        Stress test: insert data into 10 engagements simultaneously.
        Each engagement's context must see only its own data.
        """
        N = 10
        sc = super_conn()
        ac = app_conn()
        eng_ids = [make_engagement_id() for _ in range(N)]

        try:
            # Seed all engagements
            for eng_id in eng_ids:
                seed_engagement(sc, eng_id)
                # Insert a unique number of claims per engagement
                for _ in range(eng_ids.index(eng_id) + 1):
                    seed_claim(sc, eng_id)

            # Verify each engagement only sees its own claims
            for i, eng_id in enumerate(eng_ids):
                expected = i + 1
                count = count_with_context(ac, "claims", eng_id)
                assert count == expected, (
                    f"Engagement {i}: expected {expected} claims, got {count}. "
                    f"Cross-engagement contamination detected."
                )
        finally:
            for eng_id in eng_ids:
                cleanup(sc, eng_id)
            sc.close()
            ac.close()


# ═════════════════════════════════════════════════════════════════════════════
# INSERT-ONLY ENFORCEMENT TESTS
# ═════════════════════════════════════════════════════════════════════════════

class TestEvidenceLedgerInsertOnly:
    def test_update_silently_does_nothing(self):
        """
        CRITICAL: The evidence ledger is immutable.
        An UPDATE must silently do nothing — the rule discards it.
        The hash must remain exactly as originally inserted.
        """
        eng_a = make_engagement_id()
        sc = super_conn()
        original_hash = "a" * 64
        tampered_hash = "b" * 64

        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO evidence_ledger
                        (engagement_id, entry_type, object_id,
                         object_hash, recorded_by)
                    VALUES (%s, 'chunk', %s, %s, 'test')
                """, (eng_a, str(uuid4()), original_hash))

                # Attempt UPDATE as superuser (superuser has no RLS bypass for rules)
                cur.execute("""
                    UPDATE evidence_ledger
                    SET object_hash = %s
                    WHERE engagement_id = %s
                """, (tampered_hash, eng_a))

                # Verify hash is unchanged
                cur.execute("""
                    SELECT object_hash FROM evidence_ledger
                    WHERE engagement_id = %s
                """, (eng_a,))
                rows = cur.fetchall()

            assert len(rows) == 1, "Ledger entry should still exist after UPDATE attempt"
            assert rows[0][0] == original_hash, (
                f"INSERT-ONLY FAILURE: UPDATE changed the evidence ledger hash.\n"
                f"Expected: {original_hash}\n"
                f"Got:      {rows[0][0]}\n"
                f"The evidence ledger has been tampered with."
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()

    def test_delete_silently_does_nothing(self):
        """DELETE on evidence_ledger must silently do nothing."""
        eng_a = make_engagement_id()
        sc = super_conn()

        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO evidence_ledger
                        (engagement_id, entry_type, object_id,
                         object_hash, recorded_by)
                    VALUES (%s, 'chunk', %s, %s, 'test')
                """, (eng_a, str(uuid4()), "c" * 64))

                # Attempt DELETE
                cur.execute(
                    "DELETE FROM evidence_ledger WHERE engagement_id = %s",
                    (eng_a,)
                )

                # Count — must still be 1
                cur.execute(
                    "SELECT count(*) FROM evidence_ledger WHERE engagement_id = %s",
                    (eng_a,)
                )
                count = cur.fetchone()[0]

            assert count == 1, (
                f"INSERT-ONLY FAILURE: DELETE removed row from evidence_ledger. "
                f"Expected 1 row, found {count}."
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()

    def test_multiple_inserts_all_persist(self):
        """All inserts succeed. Only UPDATE/DELETE are blocked."""
        eng_a = make_engagement_id()
        sc = super_conn()

        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                for i in range(5):
                    cur.execute("""
                        INSERT INTO evidence_ledger
                            (engagement_id, entry_type, object_id,
                             object_hash, recorded_by)
                        VALUES (%s, 'chunk', %s, %s, 'test')
                    """, (eng_a, str(uuid4()), str(i) * 64))

                cur.execute(
                    "SELECT count(*) FROM evidence_ledger WHERE engagement_id = %s",
                    (eng_a,)
                )
                count = cur.fetchone()[0]

            assert count == 5, (
                f"Expected 5 ledger entries, got {count}. Inserts should all succeed."
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()


class TestAuditLogInsertOnly:
    def test_update_silently_does_nothing(self):
        eng_a = make_engagement_id()
        sc = super_conn()
        original_hash = "original_" + "x" * 55

        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO connector_audit_log
                        (engagement_id, query_id, connector_type, query_intent,
                         domain, parameters_hash, executed_at,
                         duration_ms, record_count, success)
                    VALUES
                        (%s, %s, 'salesforce', 'pipeline_summary',
                         'commercial', %s, NOW(), 250, 47, TRUE)
                """, (eng_a, str(uuid4()), original_hash))

                cur.execute("""
                    UPDATE connector_audit_log
                    SET parameters_hash = %s
                    WHERE engagement_id = %s
                """, ("tampered_" + "y" * 55, eng_a))

                cur.execute("""
                    SELECT parameters_hash FROM connector_audit_log
                    WHERE engagement_id = %s
                """, (eng_a,))
                rows = cur.fetchall()

            assert rows[0][0] == original_hash, (
                "INSERT-ONLY FAILURE: connector_audit_log parameters_hash was modified"
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()

    def test_delete_silently_does_nothing(self):
        eng_a = make_engagement_id()
        sc = super_conn()

        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO connector_audit_log
                        (engagement_id, query_id, connector_type, query_intent,
                         domain, parameters_hash, executed_at,
                         duration_ms, record_count, success)
                    VALUES
                        (%s, %s, 'hubspot', 'pipeline_summary',
                         'commercial', %s, NOW(), 180, 23, TRUE)
                """, (eng_a, str(uuid4()), "d" * 64))

                cur.execute(
                    "DELETE FROM connector_audit_log WHERE engagement_id = %s",
                    (eng_a,)
                )
                cur.execute(
                    "SELECT count(*) FROM connector_audit_log WHERE engagement_id = %s",
                    (eng_a,)
                )
                count = cur.fetchone()[0]

            assert count == 1, (
                "INSERT-ONLY FAILURE: DELETE removed row from connector_audit_log"
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()


class TestChatMessagesInsertOnly:
    def test_update_silently_does_nothing(self):
        eng_a = make_engagement_id()
        sc = super_conn()
        original_content = "What is the pipeline conversion rate?"

        try:
            seed_engagement(sc, eng_a)
            with sc.cursor() as cur:
                cur.execute("""
                    INSERT INTO chat_sessions (session_id, engagement_id, user_id)
                    VALUES (%s, %s, %s)
                    RETURNING session_id
                """, (str(uuid4()), eng_a, str(uuid4())))
                session_id = cur.fetchone()[0]

                cur.execute("""
                    INSERT INTO chat_messages
                        (session_id, engagement_id, role, content)
                    VALUES (%s, %s, 'user', %s)
                """, (session_id, eng_a, original_content))

                cur.execute("""
                    UPDATE chat_messages
                    SET content = 'Tampered content'
                    WHERE engagement_id = %s
                """, (eng_a,))

                cur.execute(
                    "SELECT content FROM chat_messages WHERE engagement_id = %s",
                    (eng_a,)
                )
                rows = cur.fetchall()

            assert rows[0][0] == original_content, (
                "INSERT-ONLY FAILURE: chat_messages content was modified"
            )
        finally:
            cleanup(sc, eng_a)
            sc.close()
