"""Pipeline entry point for Day 06 Data Ingestion Engineering."""
import json
import os
import sys
import time
from pathlib import Path
from dotenv import load_dotenv

from .chunking import by_paragraph, fixed_size
from .embeddings import MyEmbedder
from .evaluation import evaluate_query, summarize
from .ingestion import load_jsonl, load_pdf
from .models import Chunk, DocumentPage
from .store import PgVectorStore


def load_corpus(data_dir: Path) -> list[DocumentPage]:
    """Discover and load documents from data directory (prioritizing pre-extracted JSONL or reading PDF)."""
    pages: list[DocumentPage] = []

    # Đọc default document_id từ manifest.json nếu có
    default_doc_id = "luat_an_ninh_mang_116-2025"
    manifest_path = data_dir / "manifest.json"
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest_data = json.load(f)
                default_doc_id = manifest_data.get("source_id", default_doc_id)
        except Exception:
            pass

    # 1. Ưu tiên tìm file JSONL đã trích xuất sẵn (ví dụ pages.jsonl từ OCR)
    jsonl_files = list(data_dir.glob("*.jsonl"))
    if jsonl_files:
        for jsonl_path in jsonl_files:
            pages.extend(load_jsonl(jsonl_path, document_id=default_doc_id, source=default_doc_id))
        return pages

    # 2. Nếu không có file JSONL, đọc từ các file PDF
    pdf_files = list(data_dir.glob("*.pdf"))
    for pdf_path in pdf_files:
        doc_id = pdf_path.stem
        pages.extend(load_pdf(pdf_path, document_id=doc_id, source=str(pdf_path.name)))

    return pages


def load_benchmark(data_dir: Path, base_dir: Path) -> list[dict]:
    """Load benchmark questions from benchmark.json or fallbacks."""
    candidate_paths = [
        data_dir / "benchmark.json",
        data_dir / "questions.json",
        base_dir / "data" / "benchmark.json",
        base_dir / "starter" / "data" / "benchmark.json",
    ]

    for p in candidate_paths:
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    return data
                elif isinstance(data, dict) and "questions" in data:
                    return data["questions"]

    # Thử tìm format-example làm mẫu nếu chưa có benchmark chính thức
    sample_path = base_dir / "data" / "format-example.json"
    if sample_path.exists():
        with open(sample_path, "r", encoding="utf-8") as f:
            sample = json.load(f)
            if "question" in sample:
                print(f"[Warning] benchmark.json not found. Loaded 1 sample question from {sample_path.name}")
                return [sample["question"]]

    return []


def main() -> None:
    print("=" * 60)
    print(" DAY 06: DATA INGESTION ENGINEERING PIPELINE ")
    print("=" * 60)

    # 1. Setup paths & Environment
    base_dir = Path(__file__).resolve().parents[2]
    starter_dir = Path(__file__).resolve().parents[1]
    data_dir = starter_dir / "data"
    results_dir = starter_dir / "results"
    results_dir.mkdir(parents=True, exist_ok=True)

    env_path = starter_dir / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    database_url = os.getenv(
        "DATABASE_URL",
        "postgresql://day6:day6_local_only@127.0.0.1:55433/day6_lab"
    )

    # 2. Load corpus
    print("\n[1/5] Loading Corpus...")
    pages = load_corpus(data_dir)

    if not pages:
        print(f"\n[!] Không tìm thấy file dữ liệu nào (*.pdf hoặc *.jsonl) trong thư mục {data_dir}.")
        print("Hãy copy tài liệu corpus của bạn vào starter/data/ và chạy lại.")
        return

    content_pages = [p for p in pages if len(p.text.strip()) > 0]
    print(f"Tổng số trang: {len(pages)} | Số trang nội dung: {len(content_pages)}")
    if len(content_pages) < 30:
        print(f"[CẢNH BÁO] Corpus hiện có {len(content_pages)} trang nội dung. Rubric yêu cầu tối thiểu 30 trang!")

    # 3. Chunking theo các chiến lược
    print("\n[2/5] Chunking...")
    # Chiến lược A: Fixed-size 500 ký tự, overlap 50 ký tự
    chunks_a: list[Chunk] = []
    for page in content_pages:
        chunks_a.extend(fixed_size(page, size=500, overlap=50))
    print(f"Strategy A (Fixed size 500/50): {len(chunks_a)} chunks")

    # Chiến lược B: Paragraph-based tối đa 500 ký tự
    chunks_b: list[Chunk] = []
    for page in content_pages:
        chunks_b.extend(by_paragraph(page, max_size=500))
    print(f"Strategy B (Paragraph <= 500): {len(chunks_b)} chunks")

    # Chiến lược C dùng chung chunk và embeddings với B, chỉ khác về metadata filtering khi truy xuất

    # 4. Embeddings & Ingestion to Vector Store
    print("\n[3/5] Embedding & Indexing into Vector Store...")
    embedder = MyEmbedder()
    store = PgVectorStore(database_url=database_url, dimensions=embedder.dimensions)
    store.create_schema()

    # Ingest Strategy A
    store.clear_strategy("strategy_a")
    t0 = time.time()
    texts_a = [c.text for c in chunks_a]
    print(f"Embedding Strategy A ({len(texts_a)} texts)...")
    vectors_a = embedder.embed_documents(texts_a)
    store.upsert("strategy_a", chunks_a, vectors_a)
    time_a = time.time() - t0
    print(f"Strategy A indexing completed in {time_a:.2f}s")

    # Ingest Strategy B
    store.clear_strategy("strategy_b")
    t0 = time.time()
    texts_b = [c.text for c in chunks_b]
    print(f"Embedding Strategy B ({len(texts_b)} texts)...")
    vectors_b = embedder.embed_documents(texts_b)
    store.upsert("strategy_b", chunks_b, vectors_b)
    time_b = time.time() - t0
    print(f"Strategy B indexing completed in {time_b:.2f}s")

    # 5. Benchmark Retrieval & Evaluation
    print("\n[4/5] Running Benchmark Retrieval...")
    benchmark = load_benchmark(data_dir, base_dir)
    if not benchmark:
        print("[!] Không tìm thấy bộ benchmark (starter/data/benchmark.json).")
        print("Hãy tạo file benchmark với ít nhất 20 câu hỏi dev/test theo BENCHMARK.md!")
        return

    print(f"Loaded {len(benchmark)} benchmark questions.")

    traces_a = []
    traces_b = []
    traces_c = []

    for q in benchmark:
        q_text = q.get("question", "")
        q_filter = q.get("filter")
        q_vec = embedder.embed_query(q_text)

        # Strategy A: Fixed-size, no filter
        hits_a = store.search("strategy_a", q_vec, top_k=3, filters=None)
        traces_a.append(evaluate_query(q, hits_a))

        # Strategy B: Paragraph-based, no filter
        hits_b = store.search("strategy_b", q_vec, top_k=3, filters=None)
        traces_b.append(evaluate_query(q, hits_b))

        # Strategy C: Paragraph-based + Metadata Filter (nếu câu hỏi có filter)
        hits_c = store.search("strategy_b", q_vec, top_k=3, filters=q_filter)
        traces_c.append(evaluate_query(q, hits_c))

    # 6. Tổng hợp kết quả & Lưu trace
    print("\n[5/5] Summarizing Results...")
    summary_a = summarize(traces_a)
    summary_b = summarize(traces_b)
    summary_c = summarize(traces_c)

    final_results = {
        "dataset_stats": {
            "total_pages": len(pages),
            "content_pages": len(content_pages),
            "strategy_a_chunks": len(chunks_a),
            "strategy_b_chunks": len(chunks_b),
            "ingest_time_seconds": {"strategy_a": round(time_a, 2), "strategy_b": round(time_b, 2)},
        },
        "benchmark_summary": {
            "strategy_a": summary_a,
            "strategy_b": summary_b,
            "strategy_c": summary_c,
        },
        "traces": {
            "strategy_a": traces_a,
            "strategy_b": traces_b,
            "strategy_c": traces_c,
        },
    }

    traces_out_file = results_dir / "traces.json"
    with open(traces_out_file, "w", encoding="utf-8") as f:
        json.dump(final_results, f, ensure_ascii=False, indent=2)

    print(f"\nSaved full traces and summary to: {traces_out_file}")

    # In bảng tóm tắt kết quả
    print("\n" + "=" * 65)
    print(" RETRIEVAL BENCHMARK RESULTS ")
    print("=" * 65)
    print(f"{'Metric':<25} | {'Strategy A':<11} | {'Strategy B':<11} | {'Strategy C':<11}")
    print("-" * 65)

    for split in ["dev", "test", "all"]:
        h1_a = summary_a.get(split, {}).get("hit_at_1_display", "N/A")
        h1_b = summary_b.get(split, {}).get("hit_at_1_display", "N/A")
        h1_c = summary_c.get(split, {}).get("hit_at_1_display", "N/A")
        print(f"Hit@1 ({split.upper()}): {h1_a:<15} | {h1_b:<15} | {h1_c:<15}")

        h3_a = summary_a.get(split, {}).get("evidence_hit_at_3_display", "N/A")
        h3_b = summary_b.get(split, {}).get("evidence_hit_at_3_display", "N/A")
        h3_c = summary_c.get(split, {}).get("evidence_hit_at_3_display", "N/A")
        print(f"Hit@3 ({split.upper()}): {h3_a:<15} | {h3_b:<15} | {h3_c:<15}")
        print("-" * 65)


if __name__ == "__main__":
    main()

