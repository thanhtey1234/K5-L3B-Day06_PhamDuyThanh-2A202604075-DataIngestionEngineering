"""Store and search vectors using PostgreSQL + pgvector."""
import json
from typing import Any
import psycopg
from .models import Chunk


class PgVectorStore:
    def __init__(self, database_url: str, dimensions: int) -> None:
        """Retain connection settings; validate model dimensions."""
        if not database_url:
            raise ValueError("database_url cannot be empty")
        if dimensions <= 0:
            raise ValueError("dimensions must be positive")

        self.database_url = database_url
        self.dimensions = dimensions

    def create_schema(self) -> None:
        """Create table with vector column and source/page/filter metadata."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # Bật extension vector
                cur.execute("CREATE EXTENSION IF NOT EXISTS vector;")

                # Tạo bảng lưu chunks
                cur.execute(f"""
                    CREATE TABLE IF NOT EXISTS chunks (
                        chunk_id VARCHAR(255) PRIMARY KEY,
                        strategy VARCHAR(64) NOT NULL,
                        document_id VARCHAR(128) NOT NULL,
                        source TEXT NOT NULL,
                        page INTEGER NOT NULL,
                        text TEXT NOT NULL,
                        metadata JSONB NOT NULL DEFAULT '{{}}'::jsonb,
                        embedding vector({self.dimensions}) NOT NULL
                    );
                """)

                # Tạo index hỗ trợ truy vấn nhanh
                cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_strategy ON chunks(strategy);")
                cur.execute("CREATE INDEX IF NOT EXISTS idx_chunks_metadata ON chunks USING gin (metadata);")
                conn.commit()
        print(f"Schema initialized for vector dimensions: {self.dimensions}")

    def clear_strategy(self, strategy: str) -> None:
        """Delete all chunks for a specific strategy before re-ingesting."""
        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM chunks WHERE strategy = %s;", (strategy,))
                conn.commit()
        print(f"Cleared existing chunks for strategy '{strategy}'")

    def upsert(self, strategy: str, chunks: list[Chunk], vectors: list[list[float]]) -> None:
        """Validate lengths/dimensions and write stable IDs without duplicates.

        Removes all existing chunks for this strategy to avoid stale or duplicate chunks across runs.
        """
        if len(chunks) != len(vectors):
            raise ValueError(f"Mismatched count: {len(chunks)} chunks vs {len(vectors)} vectors")

        if not chunks:
            return

        for idx, vec in enumerate(vectors):
            if len(vec) != self.dimensions:
                raise ValueError(
                    f"Vector dimension mismatch at index {idx}: expected {self.dimensions}, got {len(vec)}"
                )

        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                # Xóa toàn bộ chunk cũ của chiến lược này trước khi nạp mới để triệt để tránh duplicate chunks
                cur.execute("DELETE FROM chunks WHERE strategy = %s;", (strategy,))

                # Batch insert với ON CONFLICT
                query = """
                    INSERT INTO chunks (
                        chunk_id, strategy, document_id, source, page, text, metadata, embedding
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s::vector
                    )
                    ON CONFLICT (chunk_id) DO UPDATE SET
                        strategy = EXCLUDED.strategy,
                        document_id = EXCLUDED.document_id,
                        source = EXCLUDED.source,
                        page = EXCLUDED.page,
                        text = EXCLUDED.text,
                        metadata = EXCLUDED.metadata,
                        embedding = EXCLUDED.embedding;
                """

                rows = [
                    (
                        chunk.chunk_id,
                        strategy,
                        chunk.document_id,
                        chunk.source,
                        chunk.page,
                        chunk.text,
                        json.dumps(chunk.metadata, ensure_ascii=False),
                        str(vec),
                    )
                    for chunk, vec in zip(chunks, vectors)
                ]

                cur.executemany(query, rows)
                conn.commit()

        print(f"Upserted {len(chunks)} chunks for strategy '{strategy}'")

    def search(
        self,
        strategy: str,
        query_vector: list[float],
        top_k: int = 3,
        filters: dict[str, Any] | None = None
    ) -> list[dict[str, Any]]:
        """Filter permitted metadata in SQL, rank by cosine distance, return top-k.

        Return chunk ID, text, score and metadata. Parameterize user-supplied values.
        """
        if len(query_vector) != self.dimensions:
            raise ValueError(f"Query vector dimension mismatch: expected {self.dimensions}, got {len(query_vector)}")

        query_vec_str = str(query_vector)

        sql_conditions = ["strategy = %s"]
        params: list[Any] = [strategy]

        if filters:
            for k, v in filters.items():
                if v is None:
                    continue
                # Kiểm tra xem có phải cột trực tiếp hay nằm trong jsonb metadata
                if k in ["document_id", "source", "page"]:
                    sql_conditions.append(f"{k} = %s")
                    params.append(v)
                else:
                    # Lọc trong trường JSONB metadata
                    if isinstance(v, (int, float, bool)):
                        sql_conditions.append(f"(metadata->>%s)::text = %s")
                        params.extend([k, str(v)])
                    else:
                        sql_conditions.append(f"metadata->>%s = %s")
                        params.extend([k, str(v)])

        where_clause = " AND ".join(sql_conditions)

        # Cosine distance: <=>
        # Cosine similarity: 1 - (embedding <=> query_vector)
        sql = f"""
            SELECT
                chunk_id,
                strategy,
                document_id,
                source,
                page,
                text,
                metadata,
                1 - (embedding <=> %s::vector) AS score
            FROM chunks
            WHERE {where_clause}
            ORDER BY embedding <=> %s::vector ASC
            LIMIT %s;
        """

        full_params = [query_vec_str] + params + [query_vec_str, top_k]

        with psycopg.connect(self.database_url) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, full_params)
                rows = cur.fetchall()

        results: list[dict[str, Any]] = []
        for r in rows:
            meta = r[6]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    pass

            results.append({
                "chunk_id": r[0],
                "strategy": r[1],
                "document_id": r[2],
                "source": r[3],
                "page": r[4],
                "text": r[5],
                "metadata": meta,
                "score": float(r[7]),
            })

        return results

