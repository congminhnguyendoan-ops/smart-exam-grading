// Kiểm thử phân loại lỗi khi tải ảnh (frontend/loi_tai.js, lệnh V1) – node:test. pytest gọi qua test_dien_thoai.py.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { LoiTai } = require(path.join(__dirname, "..", "..", "frontend", "loi_tai.js"));

test("lỗi mạng / quá giờ / quá tải / máy chủ -> gửi lại được", () => {
  for (const ma of [0, undefined, null, 408, 429, 500, 502, 503]) {
    assert.equal(LoiTai.phanLoai(ma), "mang", String(ma));
    assert.equal(LoiTai.guiLaiDuoc(ma), true);
  }
});

test("máy chủ trả lời rõ -> bị từ chối, không gửi lại", () => {
  for (const ma of [400, 403, 404, 409, 410, 422]) {
    assert.equal(LoiTai.phanLoai(ma), "tu_choi", String(ma));
    assert.equal(LoiTai.guiLaiDuoc(ma), false);
  }
  assert.equal(LoiTai.tieuDeTuChoi(409), "Kỳ thi không nhận ảnh");
  assert.equal(LoiTai.tieuDeTuChoi(418), "Máy chủ từ chối");
});

test("413 = ảnh lớn (chụp lại), 401 = hết phiên", () => {
  assert.equal(LoiTai.phanLoai(413), "anh_lon");
  assert.equal(LoiTai.phanLoai(401), "het_phien");
});
