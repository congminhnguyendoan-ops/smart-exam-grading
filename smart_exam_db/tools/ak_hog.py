import numpy as np


class HogSVM:

    def __init__(self, C: float = 1.0):
        self.C = C

    @staticmethod
    def dac_trung(X: np.ndarray) -> np.ndarray:
        a = X.reshape(-1, 28, 28).astype(np.float32)
        gx, gy = np.zeros_like(a), np.zeros_like(a)
        gx[:, :, 1:-1] = a[:, :, 2:] - a[:, :, :-2]
        gy[:, 1:-1, :] = a[:, 2:, :] - a[:, :-2, :]
        mag = np.hypot(gx, gy)
        ang = (np.degrees(np.arctan2(gy, gx)) % 180.0) / 20.0
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
