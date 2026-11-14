# Báo cáo cá nhân — Day 6

## Dữ liệu và pipeline
- Chủ đề, nguồn/quyền, số trang và quy tắc tính trang: Luật An ninh mạng số 116/2025/QH15. Nguồn tài liệu lấy từ Cổng Thông tin điện tử Chính phủ: `https://datafiles.chinhphu.vn/cpp/files/vbpq/2026/01/luat116-2025.pdf` (file lưu cục bộ: `starter/data/luat_an_ninh_mang_116-2025.pdf`). Quyền sử dụng: Văn bản quy phạm pháp luật công khai của Nhà nước Việt Nam. PDF nguồn có 37 trang vật lý; pipeline OCR tạo 37 bản ghi trong `starter/data/pages.jsonl`, từ trang 1 đến trang 37. Cả 37/37 trang có văn bản sau trích xuất (`empty_pages_count = 0` theo manifest). Pipeline không có bước loại trang theo loại trang; số trang có văn bản được xác định bằng điều kiện `len(page.text.strip()) > 0`.
- Chuẩn hóa, lỗi và giới hạn: PDF được OCR bằng Tesseract với ngôn ngữ tiếng Việt (`vie`), độ phân giải 300 DPI và cấu hình PSM 6 theo `starter/scripts/ocr_pdf.py`. Hàm `normalize_text` trong `starter/src/ingestion.py` chuẩn hóa Unicode NFC, thay thế một số ký tự khoảng trắng đặc biệt (NBSP, zero-width space, tab), chuẩn hóa ký tự xuống dòng, gộp các dòng trống liên tiếp và loại bỏ khoảng trắng thừa ở đầu/cuối dòng. Hàm này **không sửa lỗi nhận dạng từ ngữ của OCR**. Vì vậy, văn bản vẫn còn lỗi như `Luật sô`, `hệ thông`, `ølan mạng`; đây là hạn chế của bước OCR, không phải lỗi đã được tự động hiệu đính. Khi evidence không khớp, cần đối chiếu với PDF gốc.
- Embedding model/provider/version/số chiều, vector store/version, metric, lệnh chạy và chi phí: Model `AITeamVN/Vietnamese_Embedding` qua Sentence Transformers 6.3.0, 1024 chiều, chạy local CPU trên Python 3.12.14. Vector store: PostgreSQL 16 + pgvector (`pgvector/pgvector:pg16` trên Docker port 55433, db `day6_lab`). Metric: Cosine Distance (`<=>`). Lệnh chạy: `cd starter && python -m src.run`. Chi phí: 0 VNĐ (dùng hoàn toàn open-source local).
- Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn: Metadata bắt buộc gồm `document_id` (`luat_an_ninh_mang_116-2025`), `source` (`luat_an_ninh_mang_116-2025`), `page` (1–37). Trường lọc bổ sung: `chapter` (Chương I đến Chương VIII). Nguồn giá trị: Trích xuất trực tiếp từ cấu trúc phân chương chính thức của Luật An ninh mạng 2025. Lý do chọn: Giúp cô lập phạm vi tìm kiếm theo từng chương, loại bỏ hoàn toàn hiện tượng nhiễu từ khóa chéo chương khi câu hỏi đề cập đến trách nhiệm hoặc điều kiện thuộc một chương cụ thể.

## Cấu hình và benchmark
- A / B / C (tham số cụ thể, khác biệt duy nhất B–C): Chiến lược A dùng chunking kích thước cố định 500 ký tự, overlap 50 ký tự, không lọc metadata. Chiến lược B dùng chunking theo đoạn văn (`\n\n`), trần tối đa 500 ký tự (tự ngắt câu nếu vượt quá), không lọc metadata. Chiến lược C dùng cùng cấu hình chunking theo đoạn như B (dùng chung vector index); khác biệt duy nhất giữa B và C là C áp dụng lọc metadata SQL JSONB (`metadata->>'chapter' = ...`) khi câu hỏi có chỉ định filter.
- ≥20 câu: phân chia ≥15 dev / ≥5 test, câu metadata filter và cách kiểm chứng evidence: Bộ benchmark gồm 20 câu hỏi tại `starter/data/benchmark.json` (và `benchmark/benchmark.json`), phân chia thành 15 câu Dev (`q01`–`q15`) và 5 câu Test (`q16`–`q20`). Có 4 câu hỏi kiểm tra bộ lọc `chapter` (`q07`, `q12` trong Dev; `q18`, `q19` trong Test). Evidence được trích từ trang nguồn; q16 có hai đoạn evidence ở trang 23–24 và core Hit yêu cầu cả hai cùng xuất hiện trong một chunk sau chuẩn hóa.
- Tiêu chí chọn chiến lược đã chốt trước khi xem test: (1) Evidence Hit@3 trên tập Dev $\ge 80\%$; (2) Điểm Coherence của chunk $\ge 1.8/2.0$ để tránh xé vụn ý nghĩa pháp lý; (3) Tối ưu tài nguyên tính toán và thời gian ingest.

## Kết quả
| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| Strategy A | Dev | 10/15 (66.7%) | 14/15 (93.3%) | 209 | 66.85s | 0 VNĐ |
| Strategy A | Test | 1/5 (20.0%) | 2/5 (40.0%) | 209 | 66.85s | 0 VNĐ |
| Strategy B | Dev | 12/15 (80.0%) | 14/15 (93.3%) | 235 | 57.68s | 0 VNĐ |
| Strategy B | Test | 3/5 (60.0%) | 4/5 (80.0%) | 235 | 57.68s | 0 VNĐ |
| Strategy C | Dev | 12/15 (80.0%) | 14/15 (93.3%) | 235 | Dùng lại B | 0 VNĐ |
| Strategy C | Test | 3/5 (60.0%) | 4/5 (80.0%) | 235 | Dùng lại B | 0 VNĐ |

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N hoặc N/A) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| Strategy A | 1.3 / 2.0 (n=10) | 15/15 (100%) | Không lọc; 7/12 chunk đúng chương trên 4 truy vấn có filter | Mức 0: 0 câu, Mức 1: 1 câu, Mức 2: 4 câu → TB: 1.8 / 2.0 |
| Strategy B | 2.0 / 2.0 (n=10) | 15/15 (100%) | Không lọc; 3/12 chunk đúng chương trên 4 truy vấn có filter | Mức 0: 0 câu, Mức 1: 0 câu, Mức 2: 5 câu → TB: 2.0 / 2.0 |
| Strategy C | 2.0 / 2.0 (n=10) | 15/15 (100%) | 6/6 chunk Test đúng chương; 12/12 trên cả 4 truy vấn có filter | Mức 0: 0 câu, Mức 1: 0 câu, Mức 2: 5 câu → TB: 2.0 / 2.0 |

Core metric không tính q16 là Hit: hai đoạn evidence ở trang 23–24 không cùng xuất hiện trong một chunk. B/C có đủ hai đoạn rải trong Top-3, nhưng được ghi riêng như hỗ trợ đa chunk chứ không cộng vào Hit@3.

Đường dẫn trace, nhãn thủ công và cách chọn mẫu:
- Trace: Toàn bộ truy vết được ghi nhận tại `starter/results/traces.json`.
- Mẫu Coherence (10 vị trí): Lấy 10 vị trí ranh giới phân đoạn trải từ trang 1 đến trang 36 (Điều 1 trang 1, Điều 2 khoản 1 trang 1, Điều 2 khoản 17 trang 3, Điều 4 trang 4, Điều 10 trang 9, Điều 15 trang 15, Điều 23 trang 22, Điều 30 trang 27, Điều 38 trang 30, Điều 44 trang 36).
- Mẫu Metadata & Grounding: Toàn bộ 5 câu hỏi Test (`q16`–`q20`) $\times$ Top-3 retrieved chunks (tổng cộng 15 chunks).

## Phân tích và kết luận
- So sánh A–B và B–C; 2 ví dụ sai có ID câu và nguồn:
  - So sánh A–B: Chiến lược A cắt cố định 500 ký tự có thể làm vỡ câu giữa chừng (Coherence 1.3/2.0); B bảo toàn đoạn luật tốt hơn (2.0/2.0). B/C đạt Evidence Hit@3 4/5 trên Test, cao hơn A (2/5).
  - So sánh B–C: Hit@1 và Evidence Hit@3 bằng nhau; khác biệt là C áp dụng filter. Với 2 câu Test có filter (`q18`, `q19`), cả 6/6 chunk Top-3 của C thuộc đúng chương; trên cả 4 câu có filter, C đạt 12/12 chunk đúng chương.
  - 2 ví dụ sai cụ thể:
    1. Câu `q02` (Dev, gold trang 1): B/C xếp chunk trang 24 lên Top-1, còn chunk có đủ evidence ở trang 1 đứng Top-2; vì vậy B/C trượt Hit@1 nhưng vẫn đạt Evidence Hit@3.
    2. Câu `q16` (Test, gold trang 23–24): B/C truy xuất được hai đoạn evidence trong Top-3 nhưng chúng nằm ở các chunk khác nhau. Theo định nghĩa core Hit yêu cầu đủ evidence trong cùng chunk, cả hai vẫn là miss; đây là giới hạn của metric hiện tại, không phải bằng chứng rằng truy xuất không có nội dung liên quan.
- Chiến lược chọn, đánh đổi, điều kiện áp dụng: Chọn C (Paragraph-aware + Metadata filtering) làm cấu hình hoàn chỉnh vì có Coherence 2.0/2.0 và tuân thủ filter 12/12 chunk, trong khi Hit@1/Evidence Hit@3 giống B (75%/90% tổng). Đánh đổi: cần trích xuất và gán metadata chính xác; lọc sai chương có thể loại bỏ evidence đúng. Phù hợp với tài liệu phân cấp chương mục rõ ràng và chỉ bật filter khi phạm vi được xác định.
- Hạn chế của dữ liệu, nhãn, test nhỏ, đo thời gian/chi phí: Văn bản OCR còn lỗi nhận dạng ký tự/từ (ví dụ `Luật sô`, `hệ thông`, `ølan mạng`) dù đã chuẩn hóa Unicode và khoảng trắng; tập test 5 câu là mức đại diện tối thiểu theo lab, chưa bao quát toàn bộ câu hỏi phức tạp thực tế; thời gian đo chịu ảnh hưởng bởi tải CPU của máy local.
- Nếu làm lại hoặc mở rộng, cải tiến gì? (1) Kết hợp Hybrid Search (Dense Embedding `AITeamVN/Vietnamese_Embedding` + BM25/RRF) để cải thiện độ chính xác với các từ khóa số điều, ngày tháng; (2) Trích xuất metadata chi tiết đến cấp Điều (`article`) và Khoản (`clause`); (3) Tích hợp mô hình Cross-Encoder Re-ranker cho Top-10 kết quả trước khi đưa vào LLM.
