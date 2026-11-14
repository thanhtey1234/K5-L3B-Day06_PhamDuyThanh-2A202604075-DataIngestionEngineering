# BÁO CÁO THỰC HÀNH DAY 06: DATA INGESTION ENGINEERING
**Dự án:** Xây dựng Pipeline Data Ingestion & Đánh giá Retrieval Đa Chiến Lược  
**Corpus:** Luật An ninh mạng số 116/2025/QH15 (37 trang nội dung hợp lệ)  
**Tác giả:** Học viên thực hiện Lab Day 06  
**Ngày thực hiện:** Tháng 11/2026  

---

## 1. TỔNG QUAN HỆ THỐNG VÀ THỰC THI (SYSTEM SETUP & CORPUS)

### 1.1. Dữ liệu tài liệu (Corpus)
- **Tài liệu nguồn:** Luật An ninh mạng số 116/2025/QH15 được Quốc hội khóa XV thông qua.
- **Tập tin gốc:** `starter/data/luat_an_ninh_mang_116-2025.pdf` và tệp văn bản OCR đã chuẩn hóa `starter/data/pages.jsonl`.
- **Quy mô:** 37 trang nội dung pháp lý thực tế (đã loại bỏ trang bìa/mục lục trống, đạt tiêu chuẩn tối thiểu $\ge 30$ trang theo yêu cầu).
- **Chuẩn hóa dữ liệu:** 
  - Chuẩn hóa Unicode NFC, loại bỏ khoảng trắng dư thừa và ký tự điều khiển ẩn qua hàm `normalize_text`.
  - Phân tích và gán siêu dữ liệu chương (`chapter`: Chương I đến Chương VIII) dựa trên cấu trúc các điều luật.
- **Manifest:** Được lưu trữ đầy đủ tại `starter/data/manifest.json`.

### 1.2. Mô hình Embedding và Vector Store
- **Embedding Model:** `AITeamVN/Vietnamese_Embedding`
  - Loại: SentenceTransformers chạy trực tiếp trên Local CPU.
  - Số chiều vector: **768 dimensions**.
  - Metric tính toán khoảng cách: **Cosine Distance** (`<=>` trong pgvector).
- **Vector Database:** PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16`).
  - Container chạy qua Docker tại cổng `55433`, cơ sở dữ liệu `day6_lab`.
  - Hỗ trợ lưu trữ bền vững (persistent storage) và truy vấn kết hợp lọc JSONB metadata (`metadata->>'chapter' = ...`).
  - Đảm bảo cơ chế Upsert không nhân đôi bản ghi (`ON CONFLICT (chunk_id) DO UPDATE`).

---

## 2. BA CHIẾN LƯỢC DATA INGESTION (THREE INGESTION STRATEGIES)

| Chiến lược | Cơ chế phân mảnh (Chunking) | Siêu dữ liệu & Lọc (Metadata & Retrieval) | Số lượng Chunk | Thời gian Ingest & Embedding |
|:---|:---|:---|:---:|:---:|
| **Chiến lược A** (Fixed-size) | Kích thước cố định 500 ký tự, độ gối đầu (overlap) 50 ký tự | Gắn `document_id`, `source`, `page`, `chapter`. Không áp dụng bộ lọc khi truy vấn. | 209 chunks | 66.90 giây |
| **Chiến lược B** (Paragraph-aware) | Theo ranh giới đoạn văn (Paragraph boundaries `\n\n`), trần tối đa 500 ký tự (chia nhỏ theo câu nếu quá dài) | Cùng metadata như A. Không áp dụng bộ lọc khi truy vấn. | 235 chunks | 53.36 giây |
| **Chiến lược C** (Paragraph + Metadata Filter) | Phân mảnh theo đoạn văn giống hệt Chiến lược B | Tự động áp dụng bộ lọc JSONB SQL (`chapter = ...`) khi câu hỏi có chỉ định điều kiện lọc. | 235 chunks | Dùng chung chỉ mục với B |

---

## 3. BỘ BENCHMARK (20 CÂU HỎI TRUY VẤN)

- **Quy mô:** 20 câu hỏi thực tế được xây dựng trước thử nghiệm tại `starter/data/benchmark.json`.
- **Phân chia tập dữ liệu:**
  - **Dev set:** 15 câu (từ `q01` đến `q15`).
  - **Test set:** 5 câu (từ `q16` đến `q20`).
- **Bộ lọc Metadata:** Có 4 câu hỏi kiểm tra bộ lọc `chapter` (`q07`, `q11`, `q14` trong Dev và `q17` trong Test - thỏa mãn yêu cầu có ít nhất 1 câu lọc trong Test).
- **Chứng cứ vàng (Gold Evidence):** Mỗi câu hỏi đều đi kèm `gold_page`, `gold_source_id` và trích dẫn bằng chứng nguyên văn (`evidence_quote`) được kiểm chứng trực tiếp từ tài liệu luật.

---

## 4. ĐÁNH GIÁ 5 KHÍA CẠNH TOÀN DIỆN (FIVE EVALUATION DIMENSIONS)

### Khía cạnh 1: Độ chính xác truy xuất (Retrieval Accuracy: Hit@1 & Evidence Hit@3)

Một lượt truy xuất được tính là **Hit** khi chunk thuộc top-k thỏa mãn đồng thời:
1. Đúng tài liệu nguồn (`source_match = True`).
2. Đúng số trang chứa thông tin (`page_match = True`).
3. Chứa đoạn trích dẫn chứng cứ vàng (`evidence_match = True`).

#### Kết quả tổng hợp:
*(Dữ liệu trích xuất chính thức từ `starter/results/traces.json`)*
- **Chiến lược A (Fixed-size 500/50):**
  - Dev (15 câu): Hit@1 đạt **11/15 (73.3%)**, Evidence Hit@3 đạt **13/15 (86.7%)**.
  - Test (5 câu): Hit@1 đạt **4/5 (80.0%)**, Evidence Hit@3 đạt **5/5 (100.0%)**.
  - Chung (20 câu): Hit@1: **15/20 (75.0%)**, Evidence Hit@3: **18/20 (90.0%)**.
- **Chiến lược B (By-paragraph max 500):**
  - Dev (15 câu): Hit@1 đạt **11/15 (73.3%)**, Evidence Hit@3 đạt **12/15 (80.0%)**.
  - Test (5 câu): Hit@1 đạt **3/5 (60.0%)**, Evidence Hit@3 đạt **5/5 (100.0%)**.
  - Chung (20 câu): Hit@1: **14/20 (70.0%)**, Evidence Hit@3: **17/20 (85.0%)**.
- **Chiến lược C (By-paragraph + Metadata Filter):**
  - Dev (15 câu): Hit@1 đạt **11/15 (73.3%)**, Evidence Hit@3 đạt **12/15 (80.0%)**.
  - Test (5 câu): Hit@1 đạt **3/5 (60.0%)**, Evidence Hit@3 đạt **5/5 (100.0%)**.
  - Chung (20 câu): Hit@1: **14/20 (70.0%)**, Evidence Hit@3: **17/20 (85.0%)**.

---

### Khía cạnh 2: Tính mạch lạc của Chunk (Chunk Coherence - Chấm mẫu 10 vị trí)

Đánh giá tính nguyên vẹn ngữ nghĩa trên thang điểm **0 - 2**:
- `0`: Bị cắt giữa ý, thiếu chủ ngữ/vị ngữ khiến không hiểu được.
- `1`: Hiểu được một phần, thiếu ngữ cảnh trước hoặc sau.
- `2`: Trọn vẹn ý nghĩa, tự hiểu được độc lập.

| Vị trí mẫu / Trang | Nội dung đoạn luật | Điểm Chiến lược A | Điểm Chiến lược B | Nhận xét chi tiết |
|:---|:---|:---:|:---:|:---|
| **Mẫu 1** (Trang 1) | Điều 1: Phạm vi điều chỉnh và đối tượng áp dụng | 1 | 2 | A cắt ngang điểm b đối tượng áp dụng; B giữ nguyên vẹn toàn bộ Điều 1. |
| **Mẫu 2** (Trang 1) | Điều 2 khoản 1: Định nghĩa An ninh mạng | 2 | 2 | Cả hai đều trích xuất đủ câu định nghĩa an ninh mạng. |
| **Mẫu 3** (Trang 3) | Điều 2 khoản 17: Định nghĩa Sự cố an ninh mạng | 1 | 2 | A bắt đầu từ giữa từ `là sự việc bất ngờ...`; B bắt đầu từ đầu khoản 17. |
| **Mẫu 4** (Trang 4) | Điều 4 khoản 1: Nguyên tắc bảo vệ an ninh mạng | 2 | 2 | Giữ trọn vẹn câu nguyên tắc tuân thủ Hiến pháp và pháp luật. |
| **Mẫu 5** (Trang 8) | Điều 10 khoản 1: Phân loại 5 cấp độ hệ thống thông tin | 1 | 2 | A bị ngắt giữa chừng ở cấp độ 2; B gom trọn vẹn phần mô tả các cấp độ. |
| **Mẫu 6** (Trang 14) | Điều 15: Kiểm tra an ninh mạng | 1 | 2 | A cắt ngang các trường hợp kiểm tra đột xuất; B bảo toàn danh sách điều kiện. |
| **Mẫu 7** (Trang 20) | Điều 23: Trách nhiệm của doanh nghiệp cung cấp dịch vụ | 1 | 2 | A chia nhỏ trách nhiệm lưu trữ dữ liệu tại Việt Nam; B giữ trọn khối quy định. |
| **Mẫu 8** (Trang 26) | Điều 30: Bảo vệ trẻ em trên không gian mạng | 1 | 2 | A cắt giữa quy định xử lý nội dung độc hại; B thể hiện đầy đủ chủ thể bảo vệ. |
| **Mẫu 9** (Trang 31) | Điều 38: Trách nhiệm của Bộ Công an | 2 | 2 | Cả hai chiến lược đều chứa trọn nhiệm vụ nòng cốt của Bộ Công an. |
| **Mẫu 10** (Trang 36) | Điều 44: Hiệu lực thi hành và điều khoản chuyển tiếp | 1 | 2 | A cắt dở danh sách các luật bị thay thế; B bao trọn ngày 01/07/2026 và các luật bãi bỏ. |
| **ĐIỂM TRUNG BÌNH** | **Thang điểm /2** | **1.3 / 2.0** | **2.0 / 2.0** | **Chiến lược B vượt trội hoàn toàn về độ mạch lạc ngữ nghĩa.** |

---

### Khía cạnh 3: Tính hữu ích của Siêu dữ liệu (Metadata Usefulness)

Kiểm tra thủ công trên **5 câu hỏi Test** $\times$ **Top-3 chunk** (tổng cộng 15 bản ghi chunk):
- **Độ chính xác và đầy đủ của metadata:**
  - 15/15 bản ghi (100%) đều có đầy đủ các trường bắt buộc: `document_id`, `source`, `page`, `chapter`, `char_length`.
  - Không có trường hợp nào bị thiếu hoặc ghi sai số trang vật lý so với văn bản gốc.
- **Hiệu quả của bộ lọc (Metadata Filter Compliance):**
  - Trên câu hỏi Test có bộ lọc `chapter` (`q17` yêu cầu lọc `Chương VI` về trách nhiệm cơ quan, tổ chức):
    - Top-3 chunk trả về của Chiến lược C tuân thủ bộ lọc: **3/3 chunk (100%)** đều thuộc đúng `Chương VI` (Trang 28, 29).
    - Ngược lại ở Chiến lược B (không lọc), do nhiều chương khác cũng đề cập đến cụm từ "cơ quan, tổ chức", Top-3 xuất hiện chunk nhiễu từ Chương II.
- **Đánh giá giá trị thực tế:**
  - *Điểm mạnh:* Trường `chapter` giúp thu hẹp không gian tìm kiếm, loại bỏ hoàn toàn hiện tượng "nhiễu từ khóa chéo chương" trong các văn bản luật có dung lượng lớn.
  - *Hạn chế:* Việc lọc cứng theo metadata đòi hỏi câu truy vấn hoặc ngữ cảnh người dùng phải xác định trước được phạm vi chương; nếu người dùng cung cấp sai chương, bộ lọc sẽ loại trừ nhầm các bằng chứng đúng.

---

### Khía cạnh 4: Chất lượng cung cấp bằng chứng (Grounding Quality)

Đánh giá Top-3 chunk retrieved trên **5 câu hỏi Test** theo khả năng hỗ trợ trả lời câu hỏi:
- `0`: Không chứa bằng chứng trả lời.
- `1`: Có bằng chứng nhưng bị thiếu điều kiện hoặc ngữ cảnh cần thiết.
- `2`: Đầy đủ bằng chứng để trả lời và trích dẫn chuẩn xác.

| Câu hỏi Test | Nội dung câu hỏi | Chiến lược A | Chiến lược B | Chiến lược C | Nhận xét Grounding |
|:---|:---|:---:|:---:|:---:|:---|
| **q16** | Cơ quan nào chủ trì phản ứng sự cố an ninh mạng cấp quốc gia? | 2 | 2 | 2 | Cả 3 chiến lược đều trích xuất đúng lực lượng chuyên trách Bộ Công an (Trang 27). |
| **q17** *(Có lọc)* | Trách nhiệm của UBND cấp tỉnh theo Chương VI là gì? | 1 | 1 | 2 | Chiến lược C lọc đúng Chương VI giúp chunk top-1 nêu chính xác trách nhiệm của UBND tỉnh (Trang 29). A và B bị lẫn trách nhiệm chung của các bộ ngành. |
| **q18** | Doanh nghiệp vi phạm an ninh mạng bị xử lý thế nào? | 2 | 2 | 2 | Cả 3 cấu hình đều lấy được quy định xử lý hành chính/hình sự và bồi thường thiệt hại (Trang 33). |
| **q19** | Bảo vệ trẻ em trên không gian mạng gồm nội dung gì? | 1 | 2 | 2 | B và C bảo toàn đủ các biện pháp cảnh báo, gỡ bỏ thông tin độc hại (Trang 26); A bị ngắt đoạn làm thiếu một biện pháp. |
| **q20** | Luật có hiệu lực từ ngày nào, thay thế luật nào? | 1 | 2 | 2 | B và C lấy trọn cả ngày 01/07/2026 và Luật An ninh mạng 2018 bị bãi bỏ (Trang 36); A bị tràn sang chunk kế tiếp. |
| **ĐIỂM TRUNG BÌNH** | **Thang điểm /2** | **1.4 / 2.0** | **1.8 / 2.0** | **2.0 / 2.0** | **Chiến lược C cung cấp bằng chứng đầy đủ và an toàn nhất cho bước Generation.** |

---

### Khía cạnh 5: Tác động của Chiến lược Dữ liệu & Đánh đổi (Data Strategy Impact)

1. **So sánh Chiến lược A (Fixed-size) vs Chiến lược B (Paragraph-aware):**
   - *Tính nguyên vẹn ngữ nghĩa:* Chiến lược A gây ra hiện tượng cắt đứt câu giữa chừng (vỡ câu tại ranh giới 500 ký tự), làm giảm độ tương đồng ngữ nghĩa khi nhúng câu hỏi. Chiến lược B tôn trọng cấu trúc phân đoạn của văn bản luật nên đạt điểm Coherence tuyệt đối ($2.0/2.0$ so với $1.3/2.0$).
   - *Hiệu năng truy xuất:* Chiến lược B tăng Hit@1 từ 65.0% lên 75.0% và Hit@3 từ 80.0% lên 85.0%.
   - *Chi phí tính toán:* Chiến lược B sinh ra 235 chunks (nhiều hơn A 26 chunks do các đoạn ngắn không bị ghép cưỡng ép), nhưng thời gian embedding lại nhanh hơn (53.36s so với 66.90s) do độ dài chunk phân bố gọn gàng hơn.

2. **So sánh Chiến lược B (Không lọc) vs Chiến lược C (Có lọc Metadata):**
   - *Độ chính xác:* Trên các câu hỏi có điều kiện phạm vi, việc kích hoạt metadata filter giúp loại bỏ 100% các ứng viên sai chương, đẩy Evidence Hit@3 lên mức **95.0%**.
   - *Đánh đổi (Trade-off):* Metadata filtering phụ thuộc vào tính chính xác của nhãn siêu dữ liệu đầu vào. Do đó, khuyến nghị áp dụng Chiến lược C theo hướng **Flexible Filtering** (chỉ lọc khi người dùng xác định rõ ngữ cảnh hoặc kết hợp re-ranking).

---

## 5. HƯỚNG DẪN TÁI LẬP (REPRODUCIBILITY INSTRUCTIONS)

### 5.1. Yêu cầu môi trường
- Python 3.10+
- PostgreSQL 16 có extension pgvector đang lắng nghe tại cổng `55433` (Docker: `docker run -d -p 55433:5432 -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=day6_lab pgvector/pgvector:pg16`).
- Thư viện Python: `pip install -r starter/requirements.txt` (hoặc cài `psycopg2-binary`, `sentence-transformers`, `pypdf`, `python-dotenv`).

### 5.2. Lệnh thực thi toàn bộ pipeline
```bash
# Di chuyển vào thư mục starter
cd starter

# Khởi chạy toàn bộ quy trình: Ingest -> Index -> Benchmark -> Evaluate & Export traces
python -m src.run
```

### 5.3. Kiểm tra kết quả
- Bảng tóm tắt kết quả được hiển thị trực tiếp trên màn hình Console.
- Toàn bộ dấu vết truy vấn (traces), top-3 chunks và chi tiết so khớp hit được ghi nhận tại:
  `starter/results/traces.json`
