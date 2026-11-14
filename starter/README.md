# Starter · PostgreSQL + pgvector

Bộ triển khai cá nhân cho pipeline ingestion và benchmark. Docker Compose tạo PostgreSQL + pgvector local; `src/` đọc corpus, tạo chunk, embedding, lưu vector, áp dụng filter và ghi trace kết quả. Có thể thay PostgreSQL bằng Qdrant, Chroma hoặc vector store tương đương theo [GUIDE.md](../GUIDE.md), nhưng cần điều chỉnh mã tương ứng.

## Cấu trúc

```text
starter/
├── docker-compose.yml     # PostgreSQL 16 + pgvector, chỉ mở cổng local
├── init.sql               # bật extension khi tạo database mới
├── requirements.txt       # psycopg, pypdf, python-dotenv và Sentence Transformers
├── .env.example           # cấu hình mẫu; copy thành .env
├── scripts/check_setup.py # kiểm tra kết nối và extension (đã chạy được)
├── src/
│   ├── models.py          # cấu trúc dữ liệu mẫu
│   ├── ingestion.py       # đọc, chuẩn hóa và gắn metadata cho trang nguồn
│   ├── chunking.py        # fixed-size và paragraph-aware chunking
│   ├── embeddings.py      # Sentence Transformers chạy local
│   ├── store.py           # PostgreSQL/pgvector, metadata filter và vector search
│   ├── evaluation.py      # exact evidence matching, Hit@1 / Hit@3
│   └── run.py             # chạy ingestion, ba chiến lược và benchmark
├── data/                  # corpus, manifest và benchmark
└── results/               # summary và traces.json
```

## 1. Cài và kiểm tra database

Cần Docker Desktop hoặc Docker Engine + Compose, Python **3.11–3.14** (đã kiểm tra với Python 3.12.14), và mạng để tải image/dependencies/model lần đầu. Các lệnh sau chạy từ thư mục `starter/`:

```bash
cd starter
python3 -m venv .venv
```

Kích hoạt `.venv`: macOS/Linux dùng `source .venv/bin/activate`; Windows PowerShell dùng `.venv\Scripts\Activate.ps1`. Sau đó:

```bash
python -m pip install -r requirements.txt
# macOS/Linux: cp .env.example .env
# Windows PowerShell: Copy-Item .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py
```

Kỳ vọng: hiện tên database, phiên bản PostgreSQL và pgvector, sau đó `Setup OK`. Đây **chỉ là kiểm tra hạ tầng**, không phải kết quả benchmark. Docker dùng cổng `127.0.0.1:55433` và mật khẩu cố định **chỉ dùng local cho lab**; nếu cổng bận, sửa đồng thời port trong `docker-compose.yml` và `DATABASE_URL` trong `.env`. `init.sql` chỉ chạy khi volume mới được tạo; nếu database sẵn có chưa bật extension, xem log Docker và kiểm tra cấu hình thay vì xóa volume chứa dữ liệu.

Dừng container nhưng giữ dữ liệu:

```bash
docker compose -p day6_student_starter stop
```

## 2. Chọn embedding model

Model Sentence Transformers local được cài từ `requirements.txt` và không cần API key. Nếu thay bằng provider API, điền key tương ứng trong `.env`, cài SDK của provider và **không commit `.env`**. Ghi tên/version model và số chiều; dùng cùng model cho toàn bộ chiến lược và vector query tương thích vector document.

## 3. Hoàn thiện pipeline

1. Đặt corpus vào `data/` hoặc cung cấp manifest/hướng dẫn truy cập. Đọc [GUIDE.md](../GUIDE.md) về **30 trang nội dung**, quyền dữ liệu và metadata.
2. Kiểm tra hoặc điều chỉnh các bước trong `src/` cho corpus của bạn. Lưu ID tài liệu, nguồn, trang/vị trí và ít nhất một trường filter có ích.
3. Xây ít nhất ba cấu hình; ví dụ A fixed-size, B theo đoạn, C như B nhưng có filter. Cần cùng corpus, model và benchmark; nạp lại không nhân đôi và xử lý chunk cũ khi dữ liệu đổi.
4. Tự viết ít nhất 20 câu hỏi kèm evidence, tách dev/test trước khi thử theo [BENCHMARK.md](../BENCHMARK.md). Lưu trace top-3 và báo cáo đủ năm tiêu chí.
5. Chạy `python -m src.run` từ thư mục `starter/`. Pipeline hiện dùng dữ liệu trong `data/`, chạy ba cấu hình retrieval và lưu kết quả đầy đủ trong `results/traces.json`.

Lưu code, cấu hình, kết quả và lệnh chạy để người chấm tái lập; không commit key, dữ liệu mật hoặc dữ liệu không có quyền chia sẻ.
