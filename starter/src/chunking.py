"""Implement fixed-size and structure-aware chunking."""
import re
from .models import Chunk, DocumentPage


def fixed_size(page: DocumentPage, size: int = 500, overlap: int = 50) -> list[Chunk]:
    """Split text into overlapping windows and retain page metadata."""
    text = page.text
    if not text or not text.strip():
        return []

    if size <= 0:
        raise ValueError("size must be positive")
    if overlap < 0 or overlap >= size:
        raise ValueError("overlap must be non-negative and smaller than size")

    step = size - overlap
    chunks: list[Chunk] = []
    chunk_idx = 0

    start = 0
    total_len = len(text)

    while start < total_len:
        end = min(start + size, total_len)
        chunk_text = text[start:end].strip()

        if chunk_text:
            chunk_id = f"{page.document_id}_p{page.page}_fix_{chunk_idx:03d}"
            chunk_meta = dict(page.metadata)
            chunk_meta.update({
                "chunk_strategy": "fixed_size",
                "char_length": len(chunk_text),
                "start_char": start,
                "end_char": end,
            })

            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=chunk_text,
                    metadata=chunk_meta,
                )
            )
            chunk_idx += 1

        if end == total_len:
            break
        start += step

    return chunks


def _split_oversized_text(text: str, max_size: int) -> list[str]:
    """Helper to split a single oversized paragraph into sub-chunks."""
    # Thử tách theo câu (dấu chấm, chấm than, hỏi, xuống dòng)
    sentences = re.split(r"(?<=[.?!;\n])\s+", text)
    sub_chunks: list[str] = []
    curr_sub = ""

    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence:
            continue

        if len(curr_sub) + len(sentence) + 1 <= max_size:
            curr_sub = f"{curr_sub} {sentence}".strip() if curr_sub else sentence
        else:
            if curr_sub:
                sub_chunks.append(curr_sub)
            if len(sentence) > max_size:
                # Nếu một câu vẫn dài hơn max_size, cắt cứng theo ký tự
                for i in range(0, len(sentence), max_size):
                    part = sentence[i:i + max_size].strip()
                    if part:
                        sub_chunks.append(part)
                curr_sub = ""
            else:
                curr_sub = sentence

    if curr_sub:
        sub_chunks.append(curr_sub)

    return sub_chunks


def by_paragraph(page: DocumentPage, max_size: int = 500) -> list[Chunk]:
    """Group paragraphs, split oversized paragraphs and retain metadata."""
    text = page.text
    if not text or not text.strip():
        return []

    # Tách đoạn theo \n\n hoặc Điều/Khoản/Mục
    raw_paras = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not raw_paras:
        raw_paras = [p.strip() for p in text.split("\n") if p.strip()]

    chunks: list[Chunk] = []
    chunk_idx = 0
    current_group: list[str] = []
    current_length = 0

    def flush_group():
        nonlocal current_group, current_length, chunk_idx
        if not current_group:
            return
        combined_text = "\n\n".join(current_group).strip()
        if combined_text:
            chunk_id = f"{page.document_id}_p{page.page}_para_{chunk_idx:03d}"
            chunk_meta = dict(page.metadata)
            chunk_meta.update({
                "chunk_strategy": "by_paragraph",
                "char_length": len(combined_text),
                "paragraph_count": len(current_group),
            })
            chunks.append(
                Chunk(
                    chunk_id=chunk_id,
                    document_id=page.document_id,
                    source=page.source,
                    page=page.page,
                    text=combined_text,
                    metadata=chunk_meta,
                )
            )
            chunk_idx += 1
        current_group = []
        current_length = 0

    for para in raw_paras:
        para_len = len(para)

        # Nếu đoạn này tự thân nó đã vượt quá max_size
        if para_len > max_size:
            flush_group()
            sub_pieces = _split_oversized_text(para, max_size)
            for piece in sub_pieces:
                if piece:
                    chunk_id = f"{page.document_id}_p{page.page}_para_{chunk_idx:03d}"
                    chunk_meta = dict(page.metadata)
                    chunk_meta.update({
                        "chunk_strategy": "by_paragraph",
                        "char_length": len(piece),
                        "paragraph_count": 1,
                        "is_split_subpiece": True,
                    })
                    chunks.append(
                        Chunk(
                            chunk_id=chunk_id,
                            document_id=page.document_id,
                            source=page.source,
                            page=page.page,
                            text=piece,
                            metadata=chunk_meta,
                        )
                    )
                    chunk_idx += 1
            continue

        # Nếu thêm đoạn này vào nhóm hiện tại mà không vượt quá max_size
        if current_length + para_len + (2 if current_group else 0) <= max_size:
            current_group.append(para)
            current_length += para_len + (2 if len(current_group) > 1 else 0)
        else:
            flush_group()
            current_group.append(para)
            current_length = para_len

    flush_group()
    return chunks

