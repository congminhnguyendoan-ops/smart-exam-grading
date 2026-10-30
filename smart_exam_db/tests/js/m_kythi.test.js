// node --test tests/js/m_kythi.test.js  – tham số ?kythi của trang /m (frontend/m_kythi.js)
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { docThamSo, chonTuDanhSach } = require("../../frontend/m_kythi.js");

test("đọc id hợp lệ", () => {
  assert.equal(docThamSo("?kythi=1632"), 1632);
  assert.equal(docThamSo("?a=1&kythi=7"), 7);
});

test("bỏ qua giá trị lạ / thiếu", () => {
  for (const s of ["", "?", "?kythi=", "?kythi=0", "?kythi=-3", "?kythi=12a", "?kythi=<script>", "?kythi=1e3", "?kythi=1.5", "?kythi=1234567890123", null, undefined]) {
    assert.equal(docThamSo(s), null, String(s));
  }
});

test("chọn kỳ thi có quyền", () => {
  const ds = [{ exam_id: 5, exam_title: "A" }, { exam_id: 9, exam_title: "B" }];
  assert.deepEqual(chonTuDanhSach(ds, 9), { exam: ds[1], loi: null });
});

test("không có trong danh sách (không tồn tại HOẶC không có quyền): cùng một lỗi, không trả tên", () => {
  const kq = chonTuDanhSach([{ exam_id: 5, exam_title: "A" }], 6);
  assert.deepEqual(kq, { exam: null, loi: "khong_thay" });
  assert.deepEqual(chonTuDanhSach([], 6), kq);
});

test("không có tham số: không chọn, không lỗi", () => {
  assert.deepEqual(chonTuDanhSach([{ exam_id: 5 }], null), { exam: null, loi: null });
});
