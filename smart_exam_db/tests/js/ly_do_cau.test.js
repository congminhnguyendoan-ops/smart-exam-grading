"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { LyDoCau } = require("../../frontend/ly_do_cau.js");
const { DuyetNhanh } = require("../../frontend/duyet_nhanh.js");

test("o_mo không còn là 'ô tô mờ'", () => {
  assert.match(LyDoCau.chuoi(["o_mo"]), /tô đặc.*gạch chéo.*bóng đổ.*nhìn ảnh rồi xác nhận/);
  assert.doesNotMatch(LyDoCau.chuoi(["o_mo"]) + LyDoCau.chuoi(["o_mo"], LyDoCau.NGAN), /tô mờ/);
  assert.equal(LyDoCau.chuoi(["o_mo"], LyDoCau.NGAN), "ô chưa chắc đã tô đặc");
});

test("mã khác giữ nguyên chữ, mã lạ trả nguyên mã", () => {
  assert.equal(LyDoCau.chuoi(["nhieu_o", "vi_tri"]), "tô nhiều ô, chưa chắc vị trí hàng");
  assert.equal(LyDoCau.chuoi(["la_hoac"]), "la_hoac");
  assert.equal(LyDoCau.chuoi(undefined), "");
});

test("độ tin cậy chỉ hiện khi API đã trả", () => {
  assert.equal(LyDoCau.doTinCay({ confidence: 0.874 }), "độ tin cậy của máy 87%");
  assert.equal(LyDoCau.doTinCay({ confidence: null }), "");
  assert.equal(LyDoCau.doTinCay({}), "");
});

test("nhãn duyệt nhanh dùng cùng lời", () => {
  const n = DuyetNhanh.nhanCau({ reasons: ["o_mo"], omr_selected_options: "B" });
  assert.equal(n.dau_hieu, "ô chưa chắc đã tô đặc");
  assert.equal(n.goi_y, LyDoCau.GOI_Y_O_MO);
});
