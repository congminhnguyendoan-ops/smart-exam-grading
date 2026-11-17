"""ak_hog.py - lớp HOG + SVM cho lệnh AK (đặt ở tệp riêng để pickle nạp lại được từ mọi nơi, không phụ thuộc __main__)."""
import numpy as np


class HogSVM:
    """HOG (cửa sổ 28, block 14, bước block 7, cell 7, 9 bin = 324 chiều; cài bằng NumPy) rồi SVC nhân RBF. Vào: vectơ 784 điểm ảnh /255."""

    def __init__(self, C: float = 1.0):
        self.C = C

    @staticmethod
    def dac_trung(X: np.ndarray) -> np.ndarray:
        """HOG Dalal–Triggs bằng NumPy (OpenCV 5.0 không còn HOGDescriptor): gradient trung tâm, 9 bin không dấu (0–180°) nội suy tuyến tính theo góc,
        cell 7×7 px (4×4 cell), block 2×2 cell bước 1 cell (3×3 block), chuẩn hoá L2-Hys (cắt 0,2) -> 3·3·4·9 = 324 chiều."""
        a = X.reshape(-1, 28, 28).astype(np.float32)
        gx, gy = np.zeros_like(a), np.zeros_like(a)
        gx[:, :, 1:-1] = a[:, :, 2:] - a[:, :, :-2]
        gy[:, 1:-1, :] = a[:, 2:, :] - a[:, :-2, :]
        mag = np.hypot(gx, gy)
        ang = (np.degrees(np.arctan2(gy, gx)) % 180.0) / 20.0               # [0, 9)
        b0 = np.floor(ang).astype(int) % 9
        b1 = (b0 + 1) % 9
        w1 = ang - np.floor(ang)
        n = len(a)
        cell = np.zeros((n, 4, 4, 9), np.float32)
        ci = (np.arange(28) // 7)
        ni = np.arange(n)[:, None, None]
        cy, cx = ci[None, :, None], ci[None, None, :]
        np.add.at(cell, (ni, cy, cx, b0), mag * (1 - w1))
        np.add.at(cell, (ni, cy, cx, b1), mag * w1)
        blocks = []
        for i in range(3):
            for j in range(3):
                v = cell[:, i:i + 2, j:j + 2, :].reshape(n, 36)
                v = v / np.sqrt((v ** 2).sum(1, keepdims=True) + 1e-6)
                v = np.minimum(v, 0.2)
                blocks.append(v / np.sqrt((v ** 2).sum(1, keepdims=True) + 1e-6))
        return np.concatenate(blocks, axis=1).astype(np.float32)

    def fit(self, X, y, sample_weight=None):
        from sklearn.svm import SVC
        self.svc = SVC(kernel="rbf", gamma="scale", C=self.C, decision_function_shape="ovr")
        self.svc.fit(self.dac_trung(X), y, sample_weight=sample_weight)
        return self

    def decision_function(self, X):
        return self.svc.decision_function(self.dac_trung(X))
