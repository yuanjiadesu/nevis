EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
WITH latest_versions AS (
    SELECT document_id, max(version_number) AS version_number
    FROM document_versions
    WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'nevis-global')
    GROUP BY document_id
),
authorized_chunks AS MATERIALIZED (
    SELECT c.*, d.title_search_vector
    FROM document_chunks c
    JOIN document_versions v ON v.id = c.document_version_id
    JOIN latest_versions lv
      ON lv.document_id = v.document_id AND lv.version_number = v.version_number
    JOIN documents d ON d.id = c.document_id
    JOIN indexing_jobs j
      ON j.document_version_id = c.document_version_id
     AND j.embedding_profile_id = c.embedding_profile_id
    WHERE c.tenant_id = (SELECT id FROM tenants WHERE slug = 'nevis-global')
      AND j.status = 'completed'
      AND c.authorization_result = 'allow'
      AND c.embedding_profile_id = (SELECT id FROM embedding_profiles WHERE is_active LIMIT 1)
)
SELECT document_id,
       greatest(
           ts_rank_cd(title_search_vector, websearch_to_tsquery('english', 'Nevis indexing')),
           ts_rank_cd(content_search_vector, websearch_to_tsquery('english', 'Nevis indexing'))
       ) AS score
FROM authorized_chunks
WHERE title_search_vector @@ websearch_to_tsquery('english', 'Nevis indexing')
   OR content_search_vector @@ websearch_to_tsquery('english', 'Nevis indexing')
ORDER BY score DESC, id ASC
LIMIT 100;

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id
FROM clients
WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'nevis-global')
  AND normalized_email = 'benchmark-42@example.test';

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id
FROM clients
WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'nevis-global')
  AND lower(first_name || ' ' || last_name) = 'benchmark 42'
ORDER BY id
LIMIT 100;

EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT id
FROM clients
WHERE tenant_id = (SELECT id FROM tenants WHERE slug = 'nevis-global')
  AND search_vector @@ websearch_to_tsquery('english', 'retirement specialist')
ORDER BY ts_rank_cd(
    search_vector,
    websearch_to_tsquery('english', 'retirement specialist')
) DESC, id
LIMIT 100;
