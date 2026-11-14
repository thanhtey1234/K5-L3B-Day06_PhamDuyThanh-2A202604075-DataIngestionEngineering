"""Read and normalize source data."""
import json
import re
import unicodedata
from pathlib import Path
from pypdf import PdfReader
from .models import DocumentPage


def normalize_text(text: str) -> str:
    """Normalize Unicode and whitespace without discarding useful paragraph structure."""
    if not text:
        return ""

    # Chuẩn hóa Unicode sang dạng NFC
    normalized = unicodedata.normalize("NFC", text)

    # Thay thế các ký tự khoảng trắng đặc biệt (non-breaking space, zero-width space, tabs)
    normalized = normalized.replace("\xa0", " ").replace("\u200b", "").replace("\t", " ")

    # Chuẩn hóa xuống dòng: thay thế \r\n hoặc \r thành \n
    normalized = re.sub(r"\r\n|\r", "\n", normalized)

    # Gộp nhiều dòng trống liên tiếp (>2 dòng trống) thành 2 dòng trống (\n\n) để giữ cấu trúc đoạn văn
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    # Chuẩn hóa các khoảng trắng ngang liên tiếp trong cùng một dòng
    lines = []
    for line in normalized.split("\n"):
        clean_line = re.sub(r"[ ]{2,}", " ", line).strip()
        lines.append(clean_line)

    cleaned_text = "\n".join(lines).strip()
    return cleaned_text


def get_chapter_for_page(page: int) -> str:
    """Map page number to legal chapter for metadata filtering."""
    if page <= 7:
        return "Chương I"
    elif page <= 12:
        return "Chương II"
    elif page <= 22:
        return "Chương III"
    elif page <= 25:
        return "Chương IV"
    elif page <= 26:
        return "Chương V"
    elif page <= 30:
        return "Chương VI"
    elif page <= 33:
        return "Chương VII"
    else:
        return "Chương VIII"


def load_pdf(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Extract each physical page; keep its page number and source.

    Detect and record pages with no text.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"PDF file not found at: {path}")

    reader = PdfReader(str(path))
    pages: list[DocumentPage] = []
    empty_pages_count = 0

    for idx, pdf_page in enumerate(reader.pages, start=1):
        raw_text = pdf_page.extract_text() or ""
        clean_text = normalize_text(raw_text)

        is_empty = len(clean_text) == 0
        if is_empty:
            empty_pages_count += 1

        page_obj = DocumentPage(
            document_id=document_id,
            source=source,
            page=idx,
            text=clean_text,
            metadata={
                "char_count": len(clean_text),
                "is_empty": is_empty,
                "raw_char_count": len(raw_text),
                "chapter": get_chapter_for_page(idx),
            }
        )
        pages.append(page_obj)

    print(f"Loaded {len(pages)} pages from {path.name} (Empty/No-text pages: {empty_pages_count})")
    return pages


def load_jsonl(path: Path, document_id: str, source: str) -> list[DocumentPage]:
    """Helper to load pre-extracted pages from JSONL format if provided."""
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"JSONL file not found at: {path}")

    pages: list[DocumentPage] = []
    with open(path, "r", encoding="utf-8") as f:
        for idx, line in enumerate(f, start=1):
            if not line.strip():
                continue
            data = json.loads(line)

            # Tìm trường chứa text
            text_val = ""
            for k, v in data.items():
                if isinstance(v, str) and ("text" in k.lower() or "content" in k.lower()):
                    text_val = v
                    break

            clean_text = normalize_text(text_val)
            page_num = int(data.get("page", data.get("page_number", idx)))
            doc_id = data.get("document_id") or data.get("source_id") or document_id
            src = data.get("source") or data.get("source_id") or source
            custom_metadata = {k: v for k, v in data.items() if k not in ["text", "content"]}
            custom_metadata["char_count"] = len(clean_text)
            custom_metadata["document_id"] = doc_id
            custom_metadata["source_id"] = doc_id
            if "chapter" not in custom_metadata:
                custom_metadata["chapter"] = get_chapter_for_page(page_num)

            pages.append(DocumentPage(
                document_id=doc_id,
                source=src,
                page=page_num,
                text=clean_text,
                metadata=custom_metadata
            ))

    print(f"Loaded {len(pages)} pages from JSONL: {path.name}")
    return pages

