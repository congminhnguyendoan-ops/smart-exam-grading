// Kiểm thử logic khung "Chốt SBD / mã đề" (frontend/duyet_dinh_danh.js, lệnh AA) – node:test. pytest gọi qua test_ui_aa.py.
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { DuyetDinhDanh: D } = require(path.join(__dirname, "..", "..", "frontend", "duyet_dinh_danh.js"));

const DS = ["220006", "220007", "220008", "220009"];

test("lỗi tại ô SBD: chữ không phải số chặn lưu; ngoài danh sách -> cảnh báo + gợi ý gần giống; trong danh sách -> ok", () => {
  assert.equal(D.kiemSbd("", DS).muc, "trong");
  assert.equal(D.kiemSbd("22a010", DS).muc, "loi");
  const k = D.kiemSbd("220010", DS);
  assert.equal(k.muc, "canh_bao");
  assert.match(k.thong_bao, /220010 không có trong danh sách/);
  assert.deepEqual(k.goi_y, ["220006", "220007", "220008", "220009"]);    // cùng khoảng cách 2 -> theo số
  assert.deepEqual(D.kiemSbd("220018", DS).goi_y, ["220008", "220006", "220007", "220009"]);
  assert.deepEqual(D.kiemSbd("999999", DS).goi_y, []);                    // khác > 2 chữ số: không gợi ý bừa
  assert.equal(D.kiemSbd(" 220008 ", DS).muc, "ok");
  assert.equal(D.kiemSbd("220010", []).muc, "chua_kiem");                 // kỳ thi chưa có danh sách: không báo sai
  assert.match(D.kiemSbd("220010", null).thong_bao, /Không tải được/);    // tải danh sách lỗi: nói đúng nguyên nhân
});

test("lỗi tại ô mã đề: ngoài kỳ thi -> cảnh báo kèm toàn bộ mã đề hợp lệ", () => {
  assert.equal(D.kiemMaDe("103", ["103", "104"]).muc, "ok");
  const k = D.kiemMaDe("105", ["103", "104"]);
  assert.equal(k.muc, "canh_bao");
  assert.deepEqual(k.goi_y, ["103", "104"]);
  assert.match(k.thong_bao, /mã đề hợp lệ: 103, 104/);
  assert.equal(D.kiemMaDe("1o3", ["103"]).muc, "loi");
});

test("xác nhận trước khi lưu: ngoài danh sách / ngoài kỳ thi / SBD lấy từ gợi ý; chặn lưu khi lỗi hoặc cả hai trống", () => {
  const ok = { muc: "ok" }, trong = { muc: "trong" };
  assert.deepEqual(D.canXacNhan("220008", "103", ok, ok), []);
  assert.equal(D.canXacNhan("220010", "103", D.kiemSbd("220010", DS), ok).length, 1);
  assert.equal(D.canXacNhan("220008", "105", ok, D.kiemMaDe("105", ["103"])).length, 1);
  const g = D.canXacNhan("220008", "103", ok, ok, { sbd: "220008" });
  assert.equal(g.length, 1); assert.match(g[0], /GỢI Ý/);
  assert.equal(D.chanLuu(trong, trong), true);
  assert.equal(D.chanLuu({ muc: "loi" }, ok), true);
  assert.equal(D.chanLuu(ok, trong), false);
  assert.equal(D.chanLuu({ muc: "canh_bao" }, trong), false);            // cảnh báo không chặn – chỉ hỏi xác nhận
});

test("phiếu cần xem kế tiếp theo thứ tự hàng đợi", () => {
  assert.equal(D.keTiep([12, 15, 18], 15), 18);
  assert.equal(D.keTiep([12, 15, 18], 18), 12);                           // cuối hàng -> quay về đầu
  assert.equal(D.keTiep([12, 18], 15), 12);                               // phiếu hiện tại đã duyệt xong (ra khỏi hàng đợi)
  assert.equal(D.keTiep([15], 15), null);
  assert.equal(D.keTiep([], 15), null);
});

test("phím tắt: Enter lưu, Tab SBD -> mã đề, Shift+Tab mã đề -> SBD; ngoài hai ô không bắt phím", () => {
  assert.equal(D.phim("Enter", false, "in-sbd"), "luu");
  assert.equal(D.phim("Enter", false, "in-ma"), "luu");
  assert.equal(D.phim("Tab", false, "in-sbd"), "in-ma");
  assert.equal(D.phim("Tab", true, "in-ma"), "in-sbd");
  assert.equal(D.phim("Tab", false, "in-ma"), null);                      // Tab ở ô cuối: để trình duyệt sang nút Lưu
  assert.equal(D.phim("Enter", false, "tim"), null);
  assert.equal(D.phim("a", false, "in-sbd"), null);
});

test("cột cần nhìn kỹ: máy gắn cần xem hoặc ô tô không đọc được", () => {
  assert.equal(D.cotCanNhin({ can_xem: true, chu_so: "4", bubble: "4" }), true);
  assert.equal(D.cotCanNhin({ can_xem: false, chu_so: "?", bubble: "?" }), true);
  assert.equal(D.cotCanNhin({ can_xem: false, chu_so: "4", bubble: "4" }), false);
});
