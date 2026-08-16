"""Verify additive search schema and preserved lineage after migration."""

import asyncio

from sqlalchemy import text

from nevis.infrastructure.database import build_engine
from nevis.settings import get_settings


async def verify() -> None:
    engine = build_engine(get_settings().database_url)
    try:
        async with engine.connect() as connection:
            columns = set(
                await connection.scalars(
                    text(
                        "SELECT table_name || '.' || column_name FROM information_schema.columns "
                        "WHERE (table_name = 'documents' AND column_name = 'title_search_vector') "
                        "OR (table_name = 'document_chunks' "
                        "AND column_name = 'content_search_vector')"
                    )
                )
            )
            indexes = set(
                await connection.scalars(
                    text(
                        "SELECT indexname FROM pg_indexes WHERE indexname IN "
                        "('ix_documents_title_search', "
                        "'ix_document_chunks_content_search', "
                        "'ix_document_chunks_tenant_profile_version', "
                        "'uq_embedding_profiles_single_active')"
                    )
                )
            )
            missing_lineage = await connection.scalar(
                text(
                    "SELECT count(*) FROM document_chunks WHERE tenant_id IS NULL "
                    "OR source_id IS NULL OR document_version_id IS NULL "
                    "OR embedding_profile_id IS NULL OR authorization_decision_id IS NULL"
                )
            )
        assert columns == {
            "documents.title_search_vector",
            "document_chunks.content_search_vector",
        }
        assert indexes == {
            "ix_documents_title_search",
            "ix_document_chunks_content_search",
            "ix_document_chunks_tenant_profile_version",
            "uq_embedding_profiles_single_active",
        }
        assert missing_lineage == 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(verify())
