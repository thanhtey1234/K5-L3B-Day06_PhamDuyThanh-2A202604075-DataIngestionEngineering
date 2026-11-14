
import json
import sys
from pathlib import Path

# Nhận đường dẫn file từ Terminal
file_path = Path(sys.argv[1])

if not file_path.exists():
    raise FileNotFoundError(file_path)

total_pages = 0
empty_pages = 0

with open(file_path, "r", encoding="utf-8") as f:
    for line_number, line in enumerate(f, start=1):
        if not line.strip():
            continue

        page = json.loads(line)
        total_pages += 1

        print(f"\n========== PAGE {total_pages} ==========")

        # Hiển thị các trường dữ liệu
        print("Fields:", list(page.keys()))

        for key, value in page.items():
            if isinstance(value, str):
                print(f"{key}: {value[:300]}")
            else:
                print(f"{key}: {value}")

        # Kiểm tra trang rỗng
        if not any(
            isinstance(value, str) and value.strip()
            for key, value in page.items()
            if "text" in key.lower()
        ):
            empty_pages += 1

        # Chỉ xem 3 trang đầu
        if total_pages >= 3:
            break

print("\n========== SUMMARY ==========")
print("Pages inspected:", total_pages)
print("Empty pages in inspected sample:", empty_pages)
