"""Migration coverage runs against PostgreSQL/pgvector in CI or Compose smoke environments."""

from pathlib import Path


def test_initial_migration_creates_global_foundation() -> None:
    migration = Path("migrations/versions/20260815_0001_platform_foundation.py").read_text()

    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "nevis-global" in migration
    assert "audit_events" in migration
    assert "embedding_profiles" in migration


def test_ingestion_migration_creates_immutable_lineage_tables() -> None:
    migration = Path("migrations/versions/20260816_0002_document_ingestion.py").read_text()

    for table in (
        "document_sources",
        "documents",
        "document_versions",
        "ingestion_requests",
        "indexing_jobs",
        "document_chunks",
    ):
        assert table in migration
    assert "Vector(384)" in migration
    assert 'UniqueConstraint("organization_id", "idempotency_key")' in migration


def test_authorization_migration_converts_global_owner_to_tenant() -> None:
    migration = Path(
        "migrations/versions/20260816_0003_tenant_advisor_authorization.py"
    ).read_text()

    for table in ("tenants", "advisors", "advisor_tenant_memberships", "authorization_decisions"):
        assert table in migration
    assert "authorization_decision_id" in migration


def test_search_migration_adds_retrieval_vectors_and_indexes() -> None:
    migration = Path("migrations/versions/20260816_0004_document_search.py").read_text()

    assert 'down_revision = "20260816_0003"' in migration
    assert "title_search_vector" in migration
    assert "content_search_vector" in migration
    assert 'postgresql_using="gin"' in migration
    assert "ix_document_chunks_tenant_profile_version" in migration
    assert "def downgrade()" in migration


def test_active_profile_migration_enforces_single_runtime_identity() -> None:
    migration = Path(
        "migrations/versions/20260816_0005_single_active_embedding_profile.py"
    ).read_text()

    assert 'down_revision = "20260816_0004"' in migration
    assert "uq_embedding_profiles_single_active" in migration
    assert "is_active = false" in migration


def test_client_migration_preserves_legacy_documents_with_nullable_association() -> None:
    migration = Path("migrations/versions/20260816_0006_client_records.py").read_text()

    assert 'down_revision = "20260816_0005"' in migration
    assert '"clients"' in migration
    assert '"client_creation_requests"' in migration
    assert "uq_clients_tenant_normalized_email" in migration
    assert (
        'op.add_column("documents", sa.Column("client_id", sa.Uuid(), nullable=True))' in migration
    )
    assert "ix_documents_tenant_client" in migration
    assert "def downgrade()" in migration


def test_mixed_search_migration_adds_client_search_indexes() -> None:
    migration = Path("migrations/versions/20260816_0007_mixed_search.py").read_text()
    assert 'down_revision = "20260816_0006"' in migration
    assert "search_vector" in migration
    assert "ix_clients_search_vector" in migration
    assert "ix_clients_tenant_normalized_full_name" in migration
    assert "def downgrade()" in migration
