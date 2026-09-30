"""
Kiểm tra kết nối Python -> PostgreSQL và gọi thử fn_process_sheet.
Cài đặt:  pip install "psycopg[binary]" python-dotenv
Chạy:     python tools/db_check.py
"""
import os
import psycopg

DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://smart_exam_app:smartexam123@localhost:5432/smart_exam",
)


def main():
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            print("Kết nối OK:", cur.fetchone()[0].split(",")[0])

            cur.execute("SELECT exam_title, results_count, avg_score, auto_match_rate_pct FROM v_exam_summary")
            for row in cur.fetchall():
                print("Kỳ thi:", row)

            # Ví dụ: đây là cách backend gọi sau khi pipeline OCR/OMR xử lý xong 1 phiếu
            #   1) INSERT answer_sheets (detected_sbd, sbd_confidence, ...)
            #   2) INSERT sheet_answers (question_no, state, selected_options, confidence)
            #   3) SELECT * FROM fn_process_sheet(sheet_id)
            cur.execute("SET LOCAL app.current_user_id = '2'")   # user đang đăng nhập -> audit log
            cur.execute("SELECT * FROM v_review_pending LIMIT 5")
            print("Review đang chờ:", cur.fetchall())


if __name__ == "__main__":
    main()
