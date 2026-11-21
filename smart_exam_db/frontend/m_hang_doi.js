/* Hàng đợi tải ảnh của trang điện thoại /m (chụp LIÊN TỤC): mỗi tờ chụp xong vào hàng, gửi nền tối đa `toiDa` yêu cầu song song, KHÔNG chặn việc chụp tờ kế.
   Thuần logic (không DOM) – dùng được trong trình duyệt (window.HangDoi) và Node (module.exports) để kiểm thử: tests/js/hang_doi.test.js.

   Trạng thái một tờ: cho (chờ gửi) → gui (đang gửi ảnh) → cham (ảnh đã lên, máy chủ đang chấm) → xong | loi | tuchoi | trung.
     - xong : có kết quả (gồm cả ảnh bị từ chối – ketQua.status = "rejected"); giải phóng File (không còn cần).
     - loi  : lỗi mạng / máy chủ (LoiTai "mang", "anh_lon") – GIỮ File để "Gửi lại" (không bắt chụp lại nếu chỉ rớt mạng).
     - tuchoi (lệnh V1): máy chủ TRẢ LỜI RÕ là không nhận (409 kỳ thi đã đóng, 404 ngoài phạm vi …, frontend/loi_tai.js) – gửi lại chắc chắn hỏng nên
       KHÔNG có Gửi lại; giải phóng File; tính vào "từ chối".
     - trung: máy chủ báo ảnh đã tải trước đó (da_ton_tai) – không tính là chấm được; nếu phiếu đó đã có dòng trong phiên thì `an = true` (không lặp dòng).
     - Lỗi 401 (hết phiên): tờ quay về "cho", hàng đợi TẠM DỪNG cho tới khi tiepTuc() (sau khi đăng nhập lại).
   Chụp lại một tờ bị từ chối: chupLai(stt, file) – tờ cũ gắn `thayBang`, tờ mới mang `thayCho` và giữ số thứ tự tờ (soTo) của tờ cũ.
   Tải lại trang (F4): xuatSieuDuLieu() lưu danh sách tờ KHÔNG kèm ảnh; khoiPhuc() dựng lại danh sách và hỏi lại trạng thái từng phiếu qua API.
     - tờ đã có kết quả (xong / trung): khôi phục đủ từ máy chủ.
     - tờ chưa gửi xong (cho / gui / cham / loi): ảnh nằm trong bộ nhớ trang nên MẤT khi tải lại → trạng thái `mat`, bắt chụp lại (giới hạn đã biết). */
"use strict";

(function (goc) {
  const LoiTai = goc.LoiTai || (typeof require !== "undefined" ? require("./loi_tai.js").LoiTai : null);

  class HangDoi {
    /** gui(to, baoTienTrinh) -> Promise<ketQua>; lỗi ném ra có thuộc tính `ma` (mã HTTP, 0 = mạng). */
    constructor({ gui, toiDa = 2, khiDoi = () => {}, bayGio = () => Date.now() }) {
      this.gui = gui; this.toiDa = toiDa; this.khiDoi = khiDoi; this.bayGio = bayGio;
      this.ds = []; this.dangChay = 0; this.tamDung = false; this._stt = 0; this._soTo = 0;
    }

    them(files, thongTin = {}) {
      const moi = [...files].map((f) => this._tao(f, thongTin));
      this.ds.push(...moi); this.khiDoi(); this._bom();
      return moi;
    }

    chupLai(stt, file, thongTin = {}) {
      const cu = this.tim(stt);
      if (!cu) return null;
      const moi = this._tao(file, { ...thongTin, soTo: cu.soTo, thayCho: stt });
      cu.thayBang = moi.stt;
      this.ds.push(moi); this.khiDoi(); this._bom();
      return moi;
    }

    guiLai(stt) {
      const t = this.tim(stt);
      if (!t || t.trangThai !== "loi" || !t.file) return false;
      Object.assign(t, { trangThai: "cho", loi: null, tienTrinh: 0 });
      this.khiDoi(); this._bom();
      return true;
    }

    tiepTuc() { this.tamDung = false; this._bom(); }

    tim(stt) { return this.ds.find((t) => t.stt === stt) || null; }

    /** Tổng kết phiên: tờ đã chụp (không tính tờ đã được chụp lại thay, không tính ảnh trùng). */
    tong() {
      const k = { daChup: 0, chamDuoc: 0, canXem: 0, tuChoi: 0, dangCho: 0, loi: 0, trung: 0 };
      for (const t of this.ds) {
        if (t.trangThai === "trung") { k.trung++; continue; }
        if (t.thayBang) continue;
        k.daChup++;
        if (["cho", "gui", "cham"].includes(t.trangThai)) k.dangCho++;
        else if (t.trangThai === "loi") k.loi++;
        else if (t.trangThai === "tuchoi") k.tuChoi++;
        else if (t.ketQua && t.ketQua.status === "rejected") k.tuChoi++;
        else if (t.ketQua) { k.chamDuoc++; if (t.ketQua.status === "needs_review") k.canXem++; }
      }
      return k;
    }

    /** Lệnh BA: tờ đã có điểm chính thức nhưng còn câu tô nhiều ô đã chấm sai chờ xem lại (giáo viên xem trên máy tính). */
    demTuCham() {
      const r = { soTo: 0, soCau: 0 };
      for (const t of this.ds) {
        if (t.thayBang || t.trangThai !== "xong" || !t.ketQua || t.ketQua.status !== "graded") continue;
        const sc = (t.ketQua.chiTiet && t.ketQua.chiTiet.score) || {};
        const n = t.ketQua.auto_graded_pending ?? sc.auto_graded_pending ?? 0;
        if (n > 0) { r.soTo++; r.soCau += n; }
      }
      return r;
    }

    soToKeTiep() { return this._soTo + 1; }

    /** Số tờ MẤT sau khi tải lại trang (chưa gửi xong, ảnh không còn) và chưa được chụp lại thay. */
    soMat() { return this.ds.filter((t) => t.trangThai === "mat" && !t.thayBang).length; }

    /** Siêu dữ liệu để lưu (sessionStorage): số thứ tự, tên tệp, mã phiếu nếu đã có – KHÔNG có ảnh, KHÔNG có token. */
    xuatSieuDuLieu() {
      return this.ds.map((t) => ({ stt: t.stt, soTo: t.soTo, ten: t.ten || null, kichThuoc: t.kichThuoc || null, examId: t.examId || null,
        trangThai: t.trangThai, sheetId: t.ketQua ? t.ketQua.sheet_id : null, daTonTai: !!(t.ketQua && t.ketQua.da_ton_tai),
        thayCho: t.thayCho, thayBang: t.thayBang, an: t.an, ...(t.trangThai === "tuchoi" ? { loi: t.loi, maLoi: t.maLoi } : {}) }));
    }

    /** Dựng lại danh sách từ siêu dữ liệu. `traCuu(sheetId, meta)` -> Promise<ketQua> (hỏi API); lỗi 401 ném ra để đăng nhập lại; lỗi khác -> tờ `mat`. */
    async khoiPhuc(meta, traCuu) {
      let phucHoi = 0, mat = 0;
      for (const m of meta) {
        const t = { stt: m.stt, soTo: m.soTo, file: null, ten: m.ten, kichThuoc: m.kichThuoc, examId: m.examId, trangThai: "cho", tienTrinh: 1, ketQua: null,
          loi: null, lanGui: 1, tChup: this.bayGio(), tBatDau: null, tXong: this.bayGio(), an: !!m.an, thayCho: m.thayCho ?? null, thayBang: m.thayBang ?? null,
          khoiPhuc: true };
        if (m.sheetId && (m.trangThai === "xong" || m.trangThai === "trung")) {
          try { t.ketQua = await traCuu(m.sheetId, m); t.trangThai = m.trangThai; phucHoi++; }
          catch (e) {
            if (e && e.ma === 401) throw e;
            t.trangThai = "mat"; t.loi = (e && e.message) || "Không hỏi lại được trạng thái phiếu."; mat++;
          }
        } else if (m.trangThai === "tuchoi") { t.trangThai = "tuchoi"; t.loi = m.loi || "Máy chủ đã từ chối tờ này."; t.maLoi = m.maLoi; phucHoi++; }
        else { t.trangThai = "mat"; t.loi = "Tờ này chưa gửi xong khi trang được tải lại, ảnh không còn trên máy."; mat++; }
        this.ds.push(t);
        this._stt = Math.max(this._stt, t.stt); this._soTo = Math.max(this._soTo, t.soTo);
      }
      this.khiDoi();
      return { phucHoi, mat };
    }

    dangBan() { return this.ds.some((t) => ["cho", "gui", "cham"].includes(t.trangThai)); }

    _tao(file, { soTo, ...them } = {}) {
      const s = ++this._stt;
      if (soTo === undefined) soTo = ++this._soTo;
      return { stt: s, soTo, file, ten: file && file.name, kichThuoc: file && file.size, trangThai: "cho", tienTrinh: 0, ketQua: null, loi: null,
        lanGui: 0, tChup: this.bayGio(), tBatDau: null, tXong: null, an: false, thayCho: null, thayBang: null, ...them };
    }

    _bom() {
      while (!this.tamDung && this.dangChay < this.toiDa) {
        const t = this.ds.find((x) => x.trangThai === "cho");
        if (!t) return;
        this._chay(t);
      }
    }

    async _chay(t) {
      this.dangChay++; t.trangThai = "gui"; t.lanGui++; t.tBatDau = this.bayGio(); t.tienTrinh = 0; this.khiDoi();
      try {
        const kq = await this.gui(t, (p) => { t.tienTrinh = p; if (p >= 1 && t.trangThai === "gui") t.trangThai = "cham"; this.khiDoi(); });
        t.ketQua = kq; t.tXong = this.bayGio();
        if (kq && kq.da_ton_tai) {
          t.trangThai = "trung";
          t.an = this.ds.some((x) => x !== t && x.ketQua && x.ketQua.sheet_id === kq.sheet_id && x.trangThai !== "trung");
        } else t.trangThai = "xong";
        t.file = null;                                                   // đã có kết quả: không giữ ảnh trong bộ nhớ điện thoại
      } catch (e) {
        if (e && e.ma === 401) { t.trangThai = "cho"; this.tamDung = true; t.loi = e.message; }
        else if (LoiTai && LoiTai.phanLoai(e && e.ma) === "tu_choi") {   // máy chủ trả lời rõ: gửi lại cũng hỏng -> không giữ ảnh
          t.trangThai = "tuchoi"; t.loi = (e && e.message) || String(e); t.maLoi = e.ma; t.tXong = this.bayGio(); t.file = null;
        }
        else { t.trangThai = "loi"; t.loi = (e && e.message) || String(e); t.maLoi = e && e.ma; }
      } finally {
        this.dangChay--; this.khiDoi(); this._bom();
      }
    }
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { HangDoi };
  else goc.HangDoi = HangDoi;
})(typeof window !== "undefined" ? window : globalThis);
