// Kiểm thử ẩn kỳ thi đã đóng ở ô chọn (frontend/ky_thi_dong.js, lệnh V2) – node:test. pytest gọi qua test_dien_thoai.py.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { KyThiDong } = require(path.join(__dirname, "..", "..", "frontend", "ky_thi_dong.js"));

const DS = [{ exam_id: 1, status: "draft" }, { exam_id: 2, status: "closed" }, { exam_id: 3, status: "published" }, { exam_id: 4, status: "closed" }];

function khoGia() {
  const m = new Map();
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), removeItem: (k) => m.delete(k), m };
}

test("mặc định ẩn kỳ thi đã đóng; bật thì hiện đủ; đếm số kỳ thi đóng", () => {
  assert.deepEqual(KyThiDong.loc(DS, false).map((e) => e.exam_id), [1, 3]);
  assert.deepEqual(KyThiDong.loc(DS, true).map((e) => e.exam_id), [1, 2, 3, 4]);
  assert.equal(KyThiDong.soDong(DS), 2);
  assert.deepEqual(KyThiDong.loc([], false), []);
  assert.deepEqual(KyThiDong.loc(null, false), []);
});

test("kỳ thi đang chọn luôn giữ dù đã đóng (không tự đổi kỳ thi đang xem)", () => {
  assert.deepEqual(KyThiDong.loc(DS, false, 4).map((e) => e.exam_id), [1, 3, 4]);
  assert.deepEqual(KyThiDong.loc(DS, false, 1).map((e) => e.exam_id), [1, 3]);
});

test("nhớ lựa chọn ở đúng MỘT khoá localStorage; xoá khi đăng xuất; không có localStorage vẫn chạy", () => {
  const kho = khoGia();
  globalThis.localStorage = kho;
  try {
    assert.equal(KyThiDong.doc(), false);
    KyThiDong.luu(true);
    assert.deepEqual([...kho.m.entries()], [["hienKyThiDong", "1"]]);
    assert.equal(KyThiDong.doc(), true);
    KyThiDong.xoa();
    assert.equal(kho.m.size, 0); assert.equal(KyThiDong.doc(), false);
    globalThis.localStorage = { getItem: () => { throw new Error("chặn"); }, setItem: () => { throw new Error("chặn"); }, removeItem: () => { throw new Error("chặn"); } };
    assert.equal(KyThiDong.doc(), false); KyThiDong.luu(true);                  // trình duyệt chặn lưu trữ: không ném lỗi
  } finally { delete globalThis.localStorage; }
  assert.equal(KyThiDong.doc(), false);
});
