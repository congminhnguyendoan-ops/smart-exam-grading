import sys
from pathlib import Path

import psycopg

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from backend.config import lay_cau_hinh  # noqa: E402  (đọc DATABASE_URL từ biến môi trường / .env – không còn mật khẩu trong code)

DSN = lay_cau_hinh().database_url


def main():
    with psycopg.connect(DSN) as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT version()")
            print("Kết nối OK:", cur.fetchone()[0].split(",")[0])

            cur.execute("SELECT exam_title, results_count, avg_score, auto_match_rate_pct FROM v_exam_summary")
            for row in cur.fetchall():
                print("Kỳ thi:", row)

            cur.execute("SET LOCAL app.current_user_id = '2'")
            cur.execute("SELECT * FROM v_review_pending LIMIT 5")
            print("Review đang chờ:", cur.fetchall())


if __name__ == "__main__":
    main()
