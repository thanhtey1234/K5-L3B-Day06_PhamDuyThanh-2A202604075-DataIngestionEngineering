"""
ocr_pdf.py - Đọc PDF scan (không có lớp chữ) bằng OCR tiếng Việt.

Mỗi trang PDF -> 1 dòng JSON trong file .jsonl gồm:
  source_id, page (số trang vật lý, bắt đầu từ 1), text, n_chars

Cách chạy:
  python ocr_pdf.py data/luat_an_ninh_mang_116-2025.pdf results/pages.jsonl

Cần cài:
  pip install pypdfium2 pytesseract pillow
  + chương trình Tesseract OCR và gói ngôn ngữ 'vie' (xem hướng dẫn kèm theo)
"""
import json
import sys
import time
import unicodedata
from pathlib import Path

import pypdfium2 as pdfium
import pytesseract

DPI = 300            # độ phân giải khi chuyển trang PDF thành ảnh
LANG = "vie"         # ngôn ngữ OCR: tiếng Việt
PSM = "6"            # coi mỗi trang là một khối chữ đồng nhất


def normalize(text: str) -> str:
    """Chuẩn hóa Unicode về dạng NFC để chữ có dấu luôn cùng một kiểu mã."""
    text = unicodedata.normalize("NFC", text)
    # bỏ khoảng trắng thừa ở cuối dòng và dòng trống liên tiếp
    lines = [ln.rstrip() for ln in text.splitlines()]
    out, blank = [], False
    for ln in lines:
        if ln.strip() == "":
            if not blank:
                out.append("")
            blank = True
        else:
            out.append(ln)
            blank = False
    return "\n".join(out).strip()


def main(pdf_path: str, out_path: str) -> None:
    pdf_path = Path(pdf_path)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    pdf = pdfium.PdfDocument(str(pdf_path))
    n_pages = len(pdf)
    print(f"Đọc {pdf_path.name}: {n_pages} trang")

    # Nếu file kết quả đã có (chạy dở lần trước), bỏ qua các trang đã OCR xong
    done = set()
    if out_path.exists():
        with out_path.open(encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    done.add(json.loads(line)["page"])
    if done:
        print(f"  đã có {len(done)} trang, chạy tiếp phần còn lại")

    t0 = time.time()
    with out_path.open("a", encoding="utf-8") as f:
        for i in range(n_pages):
            if (i + 1) in done:
                continue
            # render trang thành ảnh
            image = pdf[i].render(scale=DPI / 72).to_pil().convert("L")
            # OCR
            raw = pytesseract.image_to_string(
                image, lang=LANG, config=f"--psm {PSM}"
            )
            text = normalize(raw)
            record = {
                "source_id": pdf_path.stem,
                "page": i + 1,
                "text": text,
                "n_chars": len(text),
            }
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
            f.flush()
            print(f"  trang {i + 1:>2}/{n_pages}: {len(text):>5} ký tự")

    print(f"Xong sau {time.time() - t0:.0f} giây -> {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(1)
    main(sys.argv[1], sys.argv[2])
