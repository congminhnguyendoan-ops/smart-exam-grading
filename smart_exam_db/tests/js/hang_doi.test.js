// Kiểm thử hàng đợi chụp liên tục (frontend/m_hang_doi.js) – node:test, không cần thư viện ngoài. Chạy: node --test tests/js  (pytest gọi qua test_dien_thoai_lien_tuc.py)
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { HangDoi } = require(path.join(__dirname, "..", "..", "frontend", "m_hang_doi.js"));

/** Máy chủ giả: mỗi lần gửi tạo một "lời hứa" do test tự quyết khi nào xong / lỗi. */
function mayChuGia() {
  const cho = [];
  let dongThoi = 0, maxDongThoi = 0;
  const gui = (to, bao) => new Promise((ok, loi) => {
    dongThoi++; maxDongThoi = Math.max(maxDongThoi, dongThoi);
    cho.push({ to, bao, ok: (v) => { dongThoi--; ok(v); }, loi: (e) => { dongThoi--; loi(e); } });
  });
  return { cho, gui, max: () => maxDongThoi };
}
const tep = (ten) => ({ name: ten, size: 1000 });
const nghi = () => new Promise((r) => setImmediate(r));
const loiMa = (ma, msg = "lỗi") => Object.assign(new Error(msg), { ma });

test("gửi theo đúng thứ tự chụp, tối đa 2 song song, không chặn việc thêm tờ", async () => {
  const m = mayChuGia();
  const hd = new HangDoi({ gui: m.gui, toiDa: 2 });
  hd.them([tep("1"), tep("2"), tep("3"), tep("4"), tep("5")]);
  assert.equal(m.cho.length, 2);                                   // chỉ 2 yêu cầu chạy
  assert.deepEqual(m.cho.map((c) => c.to.ten), ["1", "2"]);
  assert.deepEqual(hd.ds.map((t) => t.trangThai), ["gui", "gui", "cho", "cho", "cho"]);
  hd.them([tep("6")]);                                              // chụp tiếp trong lúc đang gửi: vẫn vào hàng
  assert.equal(hd.ds.length, 6);
  m.cho[1].ok({ sheet_id: 12, status: "needs_review" });            // tờ 2 xong trước tờ 1
  await nghi();
  assert.equal(m.cho[2].to.ten, "3");                               // tờ kế tiếp lấy theo thứ tự chụp
  for (let i = 0; i < 6; i++) { if (m.cho[i] && hd.tim(m.cho[i].to.stt).trangThai !== "xong") m.cho[i].ok({ sheet_id: 100 + i, status: "graded" }); await nghi(); }
  while (hd.dangBan()) { m.cho.filter((c) => hd.tim(c.to.stt).trangThai === "gui").forEach((c, i) => c.ok({ sheet_id: 200 + c.to.stt, status: "graded" })); await nghi(); }
  assert.equal(m.max(), 2);
  assert.deepEqual(hd.ds.map((t) => t.soTo), [1, 2, 3, 4, 5, 6]);
  assert.equal(hd.tong().chamDuoc, 6);
  assert.ok(hd.ds.every((t) => t.file === null));                   // xong: giải phóng ảnh
});

test("tiến trình 100% -> 'đang chấm'; ảnh bị từ chối tính riêng", async () => {
  const m = mayChuGia();
  const hd = new HangDoi({ gui: m.gui });
  hd.them([tep("a"), tep("b")]);
  m.cho[0].bao(0.5); assert.equal(hd.ds[0].trangThai, "gui");
  m.cho[0].bao(1); assert.equal(hd.ds[0].trangThai, "cham");
  m.cho[0].ok({ sheet_id: 1, status: "rejected", reject_code: "thieu_marker" });
  m.cho[1].ok({ sheet_id: 2, status: "needs_review" });
  await nghi();
  assert.deepEqual(hd.tong(), { daChup: 2, chamDuoc: 1, canXem: 1, tuChoi: 1, dangCho: 0, loi: 0, trung: 0 });
});

test("lỗi mạng: GIỮ ảnh, không chặn tờ sau; Gửi lại thành công", async () => {
  const m = mayChuGia();
  const hd = new HangDoi({ gui: m.gui });
  const [t1] = hd.them([tep("1"), tep("2"), tep("3")]);
  m.cho[0].loi(loiMa(0, "Mất kết nối"));
  await nghi();
  assert.equal(t1.trangThai, "loi");
  assert.ok(t1.file && t1.file.name === "1");                       // còn File để gửi lại
  assert.equal(m.cho[2].to.ten, "3");                               // tờ 3 vẫn được gửi
  assert.equal(hd.tong().loi, 1);
  assert.equal(hd.guiLai(t1.stt), true);
  assert.equal(t1.trangThai === "gui" || t1.trangThai === "cho", true);
  m.cho[1].ok({ sheet_id: 2, status: "graded" }); m.cho[2].ok({ sheet_id: 3, status: "graded" }); await nghi();
  m.cho[3].ok({ sheet_id: 1, status: "needs_review" }); await nghi();
  assert.equal(t1.trangThai, "xong"); assert.equal(t1.lanGui, 2); assert.equal(t1.soTo, 1);
  assert.equal(hd.guiLai(t1.stt), false);                           // chỉ gửi lại tờ đang lỗi
  assert.deepEqual(hd.tong(), { daChup: 3, chamDuoc: 3, canXem: 1, tuChoi: 0, dangCho: 0, loi: 0, trung: 0 });
});

test("ảnh trùng: không tính chấm được, không lặp dòng phiếu đã có trong phiên", async () => {
  const m = mayChuGia();
  const hd = new HangDoi({ gui: m.gui });
  hd.them([tep("1")]);
  m.cho[0].ok({ sheet_id: 7, status: "needs_review", da_ton_tai: false }); await nghi();
  const [lai] = hd.them([tep("1")]);
  m.cho[1].ok({ sheet_id: 7, status: "needs_review", da_ton_tai: true }); await nghi();
  assert.equal(lai.trangThai, "trung"); assert.equal(lai.an, true);  // phiếu #7 đã có dòng -> ẩn dòng trùng
  const [cu] = hd.them([tep("x")]);
  m.cho[2].ok({ sheet_id: 99, status: "graded", da_ton_tai: true }); await nghi();
  assert.equal(cu.trangThai, "trung"); assert.equal(cu.an, false);  // phiếu tải từ phiên trước: hiện một dòng "đã tải trước đó"
  assert.deepEqual(hd.tong(), { daChup: 1, chamDuoc: 1, canXem: 1, tuChoi: 0, dangCho: 0, loi: 0, trung: 2 });
});

test("401: tạm dừng, tờ quay về hàng chờ, tiếp tục sau khi đăng nhập", async () => {
  const m = mayChuGia();
  const hd = new HangDoi({ gui: m.gui, toiDa: 1 });
  const [t1, t2] = hd.them([tep("1"), tep("2")]);
  m.cho[0].loi(loiMa(401, "hết phiên")); await nghi();
  assert.equal(hd.tamDung, true); assert.equal(t1.trangThai, "cho"); assert.equal(m.cho.length, 1);   // không gửi tiếp khi chưa đăng nhập
  hd.tiepTuc();
  assert.equal(m.cho.length, 2); assert.equal(m.cho[1].to, t1);       // gửi lại đúng tờ 1 trước
  m.cho[1].ok({ sheet_id: 1, status: "graded" }); await nghi();
  m.cho[2].ok({ sheet_id: 2, status: "graded" }); await nghi();
  assert.equal(t2.trangThai, "xong"); assert.equal(hd.tong().chamDuoc, 2);
});

test("chụp lại tờ bị từ chối: giữ số tờ, tờ cũ không còn tính", async () => {
  const m = mayChuGia();
  const hd = new HangDoi({ gui: m.gui });
  const [t1] = hd.them([tep("1")]);
  hd.them([tep("2")]);
  m.cho[0].ok({ sheet_id: 1, status: "rejected" }); m.cho[1].ok({ sheet_id: 2, status: "graded" }); await nghi();
  assert.equal(hd.tong().tuChoi, 1);
  const moi = hd.chupLai(t1.stt, tep("1b"));
  assert.equal(moi.soTo, 1); assert.equal(t1.thayBang, moi.stt); assert.equal(moi.thayCho, t1.stt);
  assert.equal(hd.soToKeTiep(), 3);                                    // không tăng số tờ
  m.cho[2].ok({ sheet_id: 3, status: "needs_review" }); await nghi();
  assert.deepEqual(hd.tong(), { daChup: 2, chamDuoc: 2, canXem: 1, tuChoi: 0, dangCho: 0, loi: 0, trung: 0 });
});

// ------------------------------------------------------------------------------------------------ F4: khôi phục danh sách sau khi tải lại trang
test("F4: xuất siêu dữ liệu (không ảnh) rồi khôi phục: tờ đã chấm hỏi lại API, tờ chưa gửi xong thành 'mat'", async () => {
  const m = mayChuGia();
  const hd = new HangDoi({ gui: m.gui, toiDa: 2 });
  hd.them([tep("1.jpg"), tep("2.jpg"), tep("3.jpg")], { examId: 7 });
  m.cho[0].ok({ sheet_id: 11, status: "graded", official_score: 8 });
  m.cho[1].ok({ sheet_id: 12, status: "needs_review", pending_questions: 3 });
  await nghi();                                                    // tờ 3 đang gửi (chưa xong)
  const meta = JSON.parse(JSON.stringify(hd.xuatSieuDuLieu()));    // đi qua JSON như sessionStorage
  assert.ok(meta.every((x) => !("file" in x)));                    // không có ảnh trong siêu dữ liệu
  assert.deepEqual(meta.map((x) => [x.soTo, x.trangThai, x.sheetId, x.examId]), [[1, "xong", 11, 7], [2, "xong", 12, 7], [3, "gui", null, 7]]);

  const moi = new HangDoi({ gui: m.gui });                         // trang tải lại: hàng đợi mới, rỗng
  const hoi = [];
  const kq = await moi.khoiPhuc(meta, async (id) => { hoi.push(id); return { sheet_id: id, status: id === 11 ? "graded" : "needs_review" }; });
  assert.deepEqual(hoi, [11, 12]);                                 // chỉ hỏi lại tờ đã có phiếu
  assert.deepEqual(kq, { phucHoi: 2, mat: 1 });
  assert.deepEqual(moi.ds.map((t) => [t.soTo, t.trangThai]), [[1, "xong"], [2, "xong"], [3, "mat"]]);
  assert.equal(moi.soMat(), 1);
  assert.equal(moi.tong().chamDuoc, 2);
  assert.equal(moi.soToKeTiep(), 4);                               // số tờ tiếp theo không trùng
  const t4 = moi.them([tep("4.jpg")], { examId: 7 })[0];
  assert.ok(t4.stt > Math.max(...meta.map((x) => x.stt)));         // stt mới không đè stt đã khôi phục
});

test("F4: tờ 'mat' chụp lại giữ số tờ, hết bị tính là mất; lỗi 401 khi hỏi lại thì ném ra; lỗi khác -> mat", async () => {
  const m = mayChuGia();
  const hd = new HangDoi({ gui: m.gui });
  await hd.khoiPhuc([{ stt: 1, soTo: 1, trangThai: "cham", sheetId: null, examId: 7 }, { stt: 2, soTo: 2, trangThai: "xong", sheetId: 5, examId: 7 }],
    async () => { throw loiMa(404, "không có"); });
  assert.deepEqual(hd.ds.map((t) => t.trangThai), ["mat", "mat"]);
  const moi = hd.chupLai(1, tep("chup_lai.jpg"), { examId: 7 });
  assert.equal(moi.soTo, 1); assert.equal(hd.soMat(), 1);          // tờ 1 đã chụp lại thay; còn tờ 2 mất
  const h2 = new HangDoi({ gui: m.gui });
  await assert.rejects(h2.khoiPhuc([{ stt: 1, soTo: 1, trangThai: "xong", sheetId: 9 }], async () => { throw loiMa(401, "hết phiên"); }), (e) => e.ma === 401);
});
