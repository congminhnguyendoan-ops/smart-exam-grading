-- =====================================================================
--  File 05: Kịch bản demo luồng chấm điểm end-to-end (chạy sau 04_seed.sql)
-- =====================================================================
\echo '===== BƯỚC 1: Xử lý (chấm + match SBD) toàn bộ phiếu ====='
SELECT s.sheet_id, s.detected_sbd, s.detected_exam_code, p.*
FROM answer_sheets s, LATERAL fn_process_sheet(s.sheet_id) p
ORDER BY s.sheet_id;

\echo '===== BƯỚC 2: Bảng điểm đã tự động ghi ====='
SELECT student_code, full_name, exam_code, num_correct, score, passed, status
FROM v_exam_results WHERE exam_id = 1 ORDER BY student_code;

\echo '===== BƯỚC 3: Hàng đợi review ====='
SELECT review_id, priority, reasons, detected_sbd, sbd_confidence, detected_exam_code, raw_score, details
FROM v_review_pending;

\echo '===== BƯỚC 4: Gợi ý SV cho phiếu 4 (OCR đọc 220099) ====='
SELECT * FROM fn_suggest_students(4);

\echo '===== BƯỚC 5: Giáo viên đối soát ====='
-- Phiếu 3: xác nhận đúng là SV 220003
SELECT fn_resolve_review((SELECT review_id FROM review_queue WHERE sheet_id = 3),
                         (SELECT student_id FROM students WHERE student_code = '220003'), 2, 'Đã xem ảnh, SBD đúng');
-- Phiếu 4: OCR đọc sai, thực ra là 220009
SELECT fn_resolve_review((SELECT review_id FROM review_queue WHERE sheet_id = 4),
                         (SELECT student_id FROM students WHERE student_code = '220009'), 2, 'OCR đọc 220099 -> sửa thành 220009');
-- Ghi nhận chữ số đúng để làm dữ liệu fine-tune
UPDATE ocr_digits SET corrected_digit = '0' WHERE sheet_id = 4 AND field = 'sbd' AND position = 4;
-- Phiếu 5: quét trùng -> loại
SELECT fn_reject_review((SELECT review_id FROM review_queue WHERE sheet_id = 5), 2, 'Ảnh quét trùng của phiếu 1');
-- Phiếu 6: xem ảnh thấy câu 3 đúng là tô C -> sửa tay rồi xác nhận
UPDATE sheet_answers SET state = 'filled', confidence = 1, manually_edited = TRUE WHERE sheet_id = 6 AND question_no = 3;
SELECT fn_resolve_review((SELECT review_id FROM review_queue WHERE sheet_id = 6),
                         (SELECT student_id FROM students WHERE student_code = '220004'), 2, 'Câu 3 tô mờ nhưng rõ là C');
-- Phiếu 7: mã đề đọc sai 999 -> thực tế là 101
UPDATE answer_sheets SET exam_code_id = (SELECT exam_code_id FROM exam_codes WHERE exam_id = 1 AND code = '101')
WHERE sheet_id = 7;
SELECT fn_resolve_review((SELECT review_id FROM review_queue WHERE sheet_id = 7),
                         (SELECT student_id FROM students WHERE student_code = '220005'), 2, 'Mã đề thật là 101');

\echo '===== BƯỚC 6: Sửa đáp án câu 7 (gốc) từ C -> D rồi chấm lại ====='
UPDATE questions SET correct_option = 'D' WHERE exam_id = 1 AND original_no = 7;
UPDATE answer_keys ak SET correct_option = 'D'
FROM questions q WHERE q.question_id = ak.question_id AND q.exam_id = 1 AND q.original_no = 7;
SELECT fn_regrade_exam(1, 2) AS so_ket_qua_thay_doi;

\echo '===== KẾT QUẢ CUỐI ====='
SELECT student_code, full_name, class_code, exam_code, num_correct, score, passed, status
FROM v_exam_results WHERE exam_id = 1 ORDER BY student_code;

SELECT exam_title, registered, sheets_uploaded, sheets_graded, sheets_need_review, results_count,
       auto_matched, avg_score, min_score, max_score, pass_rate_pct, auto_match_rate_pct
FROM v_exam_summary;

\echo '--- Phổ điểm ---'
SELECT * FROM v_score_distribution WHERE exam_id = 1 ORDER BY bucket_from;
\echo '--- Độ khó câu hỏi ---'
SELECT original_no, attempts, correct, p_value, difficulty FROM v_question_difficulty WHERE exam_id = 1 ORDER BY original_no;
\echo '--- SV chưa có điểm ---'
SELECT * FROM v_missing_results WHERE exam_id = 1;
\echo '--- Lịch sử thay đổi điểm ---'
SELECT a.result_id, s.student_code, a.action, a.old_score, a.new_score, a.old_status, a.new_status, a.changed_by, a.reason
FROM score_audit_logs a JOIN results r ON r.result_id = a.result_id JOIN students s ON s.student_id = r.student_id
ORDER BY a.audit_id;
\echo '--- Độ chính xác OCR thực tế ---'
SELECT * FROM v_ocr_correction_stats;
