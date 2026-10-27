/* Hàng đợi tải ảnh của trang điện thoại /m (chụp LIÊN TỤC): mỗi tờ chụp xong vào hàng, gửi nền tối đa `toiDa` yêu cầu song song, KHÔNG chặn việc chụp tờ kế.
   Thuần logic (không DOM) – dùng được trong trình duyệt (window.HangDoi) và Node (module.exports) để kiểm thử: tests/js/hang_doi.test.js.

   Trạng thái một tờ: cho (chờ gửi) → gui (đang gửi ảnh) → cham (ảnh đã lên, máy chủ đang chấm) → xong | loi | trung.
     - xong : có kết quả (gồm cả ảnh bị từ chối – ketQua.status = "rejected"); giải phóng File (không còn cần).
     - loi  : lỗi mạng / máy chủ – GIỮ File để "Gửi lại" (không bắt chụp lại nếu chỉ rớt mạng).
     - trung: máy chủ báo ảnh đã tải trước đó (da_ton_tai) – không tính là chấm được; nếu phiếu đó đã có dòng trong phiên thì `an = true` (không lặp dòng).
     - Lỗi 401 (hết phiên): tờ quay về "cho", hàng đợi TẠM DỪNG cho tới khi tiepTuc() (sau khi đăng nhập lại).
   Chụp lại một tờ bị từ chối: chupLai(stt, file) – tờ cũ gắn `thayBang`, tờ mới mang `thayCho` và giữ số thứ tự tờ (soTo) của tờ cũ. */
"use strict";

(function (goc) {
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
        else if (t.ketQua && t.ketQua.status === "rejected") k.tuChoi++;
        else if (t.ketQua) { k.chamDuoc++; if (t.ketQua.status === "needs_review") k.canXem++; }
      }
      return k;
    }

    soToKeTiep() { return this._soTo + 1; }

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
        else { t.trangThai = "loi"; t.loi = (e && e.message) || String(e); t.maLoi = e && e.ma; }
      } finally {
        this.dangChay--; this.khiDoi(); this._bom();
      }
    }
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { HangDoi };
  else goc.HangDoi = HangDoi;
})(typeof window !== "undefined" ? window : globalThis);
