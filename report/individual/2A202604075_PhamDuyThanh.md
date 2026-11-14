# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline
- Chủ đề, nguồn/quyền, số trang và quy tắc tính trang: Luật An ninh mạng số 116/2025/QH15 do Quốc hội khóa XV ban hành ngày 18/12/2025. Nguồn tài liệu lấy từ Cổng Thông tin điện tử Chính phủ: `https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/01/luat116-2025.pdf` (file lưu cục bộ: `starter/data/luat_an_ninh_mang_116-2025.pdf`). Quyền sử dụng: Văn bản quy phạm pháp luật công khai của Nhà nước Việt Nam (thuộc phạm vi công cộng, không áp dụng bản quyền tác giả theo Luật Sở hữu trí tuệ). Số trang: 37 trang nội dung hợp lệ (từ trang 1 đến trang 37 trong `starter/data/pages.jsonl`). Quy tắc tính: Tính toàn bộ các trang chứa nội dung điều khoản luật thực tế; đã loại bỏ trang bìa và mục lục trống theo đúng quy định $\ge 30$ trang.
- Chuẩn hóa, lỗi và giới hạn: Dùng hàm `normalize_text` chuẩn hóa Unicode NFC, chuẩn hóa khoảng trắng thừa, loại bỏ ký tự điều khiển ẩn và dòng kẻ OCR. Lỗi và giới hạn: Do bản PDF gốc là bản scan công báo nên văn bản OCR có một số lỗi chính tả dấu/nối từ nhỏ (như `ø1a` thay vì `gia`, `bô` thay vì `bổ`), đã được làm sạch và map về bộ mã Unicode chuẩn.
- Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí: Model `AITeamVN/Vietnamese_Embedding` qua thư viện SentenceTransformers, 768 chiều, chạy local CPU. Vector store: PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16` trên Docker port 55433, db `day6_lab`). Metric: Cosine Distance (`<=>`). Lệnh chạy: `cd starter && python -m src.run`. Chi phí: 0 VNĐ (dùng hoàn toàn open-source local).
- Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn: Metadata bắt buộc gồm `document_id` (`luat_an_ninh_mang_116-2025`), `source` (`luat_an_ninh_mang_116-2025`), `page` (1–37). Trường lọc bổ sung: `chapter` (Chương I đến Chương VIII). Nguồn giá trị: Trích xuất trực tiếp từ cấu trúc phân chương chính thức của Luật An ninh mạng 2025. Lý do chọn: Giúp cô lập phạm vi tìm kiếm theo từng chương, loại bỏ hoàn toàn hiện tượng nhiễu từ khóa chéo chương khi câu hỏi đề cập đến trách nhiệm hoặc điều kiện thuộc một chương cụ thể.

## Cấu hình và benchmark
- A / B / C (tham số cụ thể, khác biệt duy nhất B–C): Chiến lược A dùng chunking kích thước cố định 500 ký tự, overlap 50 ký tự, không lọc metadata. Chiến lược B dùng chunking theo đoạn văn (`\n\n`), trần tối đa 500 ký tự (tự ngắt câu nếu vượt quá), không lọc metadata. Chiến lược C dùng cùng cấu hình chunking theo đoạn như B (dùng chung vector index); khác biệt duy nhất giữa B và C là C áp dụng lọc metadata SQL JSONB (`metadata->>'chapter' = ...`) khi câu hỏi có chỉ định filter.
- ≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence: Bộ benchmark gồm 20 câu hỏi tại `starter/data/benchmark.json` (và `benchmark/benchmark.json`), phân chia thành 15 câu Dev (`q01`–`q15`) và 5 câu Test (`q16`–`q20`). Có 4 câu hỏi kiểm tra bộ lọc `chapter` (`q07`, `q12` trong Dev; `q18`, `q19` trong Test - thỏa mãn $\ge 1$ câu trong Test). Cách kiểm chứng evidence: Từng đoạn `evidence_quote` đều được trích xuất trực tiếp từ trang nguồn `gold_page` tương ứng và kiểm chứng khớp nguyên văn 100% với văn bản sau chuẩn hóa.
- Tiêu chí chọn chiến lược đã chốt trước khi xem test: (1) Evidence Hit@3 trên tập Dev $\ge 80\%$; (2) Điểm Coherence của chunk $\ge 1.8/2.0$ để tránh xé vụn ý nghĩa pháp lý; (3) Tối ưu tài nguyên tính toán và thời gian ingest.

## Kết quả
| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| Strategy A | Dev | 11/15 (73.3%) | 13/15 (86.7%) | 209 | 84.12s | 0 VNĐ |
| Strategy A | Test | 4/5 (80.0%) | 5/5 (100.0%) | 209 | 84.12s | 0 VNĐ |
| Strategy B | Dev | 11/15 (73.3%) | 12/15 (80.0%) | 235 | 87.15s | 0 VNĐ |
| Strategy B | Test | 3/5 (60.0%) | 5/5 (100.0%) | 235 | 87.15s | 0 VNĐ |
| Strategy C | Dev | 11/15 (73.3%) | 12/15 (80.0%) | 235 | Dùng lại B | 0 VNĐ |
| Strategy C | Test | 3/5 (60.0%) | 5/5 (100.0%) | 235 | Dùng lại B | 0 VNĐ |

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| Strategy A | 1.3 / 2.0 (n=10) | 15/15 (100%) | N/A | Mức 0: 0 câu, Mức 1: 3 câu, Mức 2: 2 câu → TB: 1.4 / 2.0 |
| Strategy B | 2.0 / 2.0 (n=10) | 15/15 (100%) | N/A | Mức 0: 0 câu, Mức 1: 1 câu, Mức 2: 4 câu → TB: 1.8 / 2.0 |
| Strategy C | 2.0 / 2.0 (n=10) | 15/15 (100%) | 2/2 câu Test (100%) | Mức 0: 0 câu, Mức 1: 0 câu, Mức 2: 5 câu → TB: 2.0 / 2.0 |

Đường dẫn trace, nhãn thủ công và cách chọn mẫu:
- Trace: Toàn bộ truy vết được ghi nhận tại `starter/results/traces.json`.
- Mẫu Coherence (10 vị trí): Lấy 10 vị trí ranh giới phân đoạn đầu tiên thuộc các trang trải đều từ trang 1 đến trang 36 (Điều 1, Điều 2 khoản 1, Điều 2 khoản 17, Điều 4, Điều 10, Điều 15, Điều 23, Điều 30, Điều 38, Điều 44).
- Mẫu Metadata & Grounding: Toàn bộ 5 câu hỏi Test (`q16`–`q20`) $\times$ Top-3 retrieved chunks (tổng cộng 15 chunks).

## Phân tích và kết luận
- So sánh A–B và B–C; 2 ví dụ sai có ID câu và nguồn:
  - So sánh A–B: Chiến lược A cắt cố định 500 ký tự gây vỡ câu giữa chừng (Coherence chỉ đạt 1.3/2.0); Chiến lược B bảo toàn trọn vẹn ngữ nghĩa từng điều khoản (Coherence tuyệt đối 2.0/2.0). Cả A và B đều đạt 100% Evidence Hit@3 trên tập Test (5/5).
  - So sánh B–C: Trên các câu hỏi có chỉ định filter (`q18`, `q19`), Chiến lược C loại bỏ 100% ứng viên ngoài chương, nâng điểm Grounding trên Test lên 2.0/2.0.
  - 2 ví dụ sai cụ thể:
    1. Câu `q02` (Dev, nguồn gold: Trang 1, Điều 2 khoản 3 về định nghĩa An ninh dữ liệu): Ở Chiến lược B, Top-1 và Top-2 trả về chunk Trang 24 (Điều 26: Bảo đảm an ninh dữ liệu). Do Điều 26 lặp lại nhiều lần cụm từ "bảo đảm an ninh dữ liệu" nên đạt Cosine similarity cao hơn (0.569 so với 0.535 của Điều 2), đẩy trang 1 khỏi Top-3.
    2. Câu `q12` (Dev, nguồn gold: `gold_page = 11`): Chunk retrieved chứa đúng 100% câu văn quy định thông báo kiểm tra trước tháng 10 hằng năm, tuy nhiên đoạn này nằm ở chân trang 10 giáp ranh trang 11 trong văn bản OCR. Hệ thống đánh giá `page_match: False` do sai số ranh giới ngắt trang vật lý.
- Chiến lược chọn, đánh đổi, điều kiện áp dụng: Chọn Chiến lược C (Paragraph-aware + Metadata filtering) vì đảm bảo Coherence tối đa (2.0/2.0), Grounding tuyệt đối (2.0/2.0) và Test Evidence Hit@3 đạt 100%. Đánh đổi: Cần thêm công đoạn trích xuất và gán metadata chính xác ở bước Ingestion; nếu người dùng lọc nhầm chương, kết quả đúng sẽ bị loại trừ. Điều kiện áp dụng: Áp dụng cho hệ thống RAG pháp luật hoặc tài liệu có phân cấp chương mục rõ ràng, kết hợp lọc có điều kiện (chỉ kích hoạt khi người dùng xác định rõ phạm vi).
- Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí: Dữ liệu OCR scan còn một số lỗi chính tả bản in; tập test 5 câu là mức đại diện tối thiểu theo lab, chưa bao quát toàn bộ câu hỏi phức tạp thực tế; thời gian đo chịu ảnh hưởng bởi tải CPU của máy local.
- Nếu làm lại hoặc mở rộng, cải tiến gì? (1) Kết hợp Hybrid Search (Dense Embedding `AITeamVN/Vietnamese_Embedding` + BM25/RRF) để cải thiện độ chính xác với các từ khóa số điều, ngày tháng; (2) Trích xuất metadata chi tiết đến cấp Điều (`article`) và Khoản (`clause`); (3) Tích hợp mô hình Cross-Encoder Re-ranker cho Top-10 kết quả trước khi đưa vào LLM.
