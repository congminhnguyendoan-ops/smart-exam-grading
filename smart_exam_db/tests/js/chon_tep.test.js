// Kiểm thử dòng trạng thái ô chọn tệp tiếng Việt (frontend/chon_tep.js, lệnh AB) – node:test. pytest gọi qua test_ui_aa.py.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { rutGonTen } = require(path.join(__dirname, "..", "..", "frontend", "ten_tep.js"));
const { moTaTepChon } = require(path.join(__dirname, "..", "..", "frontend", "chon_tep.js"));

test("chưa chọn / một ảnh / vài ảnh: tiếng Việt, có tên tệp", () => {
  assert.equal(moTaTepChon([]), "Chưa chọn ảnh.");
  assert.equal(moTaTepChon(null), "Chưa chọn ảnh.");
  assert.equal(moTaTepChon(["0001_C1.jpg"]), "Đã chọn 1 ảnh: 0001_C1.jpg");
  assert.equal(moTaTepChon(["a.jpg", "b.jpg", "c.jpg"]), "Đã chọn 3 ảnh: a.jpg, b.jpg, c.jpg");
});

test("nhiều ảnh: chỉ hiện 3 tên đầu + số còn lại; tên dài rút gọn như ten_tep.js", () => {
  assert.equal(moTaTepChon(["a.jpg", "b.jpg", "c.jpg", "d.jpg", "e.jpg"]), "Đã chọn 5 ảnh: a.jpg, b.jpg, c.jpg và 2 ảnh khác");
  const dai = "att.pc5ziEXaMpLe-Very-Long-Name.jpeg";
  assert.equal(moTaTepChon([dai], rutGonTen), `Đã chọn 1 ảnh: ${rutGonTen(dai)}`);
  assert.ok(!/Choose|No file/i.test(moTaTepChon([])));
});
