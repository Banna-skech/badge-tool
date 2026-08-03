"""
Background removal service — fast, reliable, no heavy ML dependencies.

Strategy (tried in order):
1. White-background check — if the photo already has a near-white background,
   just clean it up (fastest, ~0.05s).
2. Edge-based subject isolation — works well for badge photos with a distinct
   subject against a plain backdrop (~0.2s).
3. GrabCut with auto-initialised rectangle — fallback for complex backgrounds
   (~1-2s on a downscaled working image).
"""
import cv2
import numpy as np

from backend.utils.image_utils import safe_rgb


class BackgroundRemover:
    """
    Removes image background and composites the subject onto pure white.

    Optimised for badge / seat-card photos: the subject is usually a single
    person centred in the frame against a plain or lightly textured backdrop.
    """

    # ---- public API ----

    def remove_background(self, img: np.ndarray,
                          face_rect: tuple | None = None) -> np.ndarray:
        """
        Remove background and return subject on white.

        Args:
            img: BGR (H, W, 3) uint8 array.
            face_rect: Optional (x, y, w, h) of the detected face — used to
                       seed the GrabCut rectangle when needed.

        Returns:
            BGR uint8 array, same dimensions as input, white background.
        """
        bgr = safe_rgb(img)

        # 1 – White-background fast path
        if self._is_mostly_white_bg(bgr):
            return self._clean_white_bg(bgr)

        # 2 – Edge-based isolation
        mask = self._edge_subject_mask(bgr)
        if mask is not None and self._mask_quality_ok(mask):
            return self._composite_on_white(bgr, mask)

        # 3 – GrabCut fallback
        return self._grabcut_white(bgr, face_rect)

    def remove_background_fallback(self, img: np.ndarray,
                                   face_rect: tuple | None = None) -> np.ndarray:
        """Alias — always goes through the GrabCut path."""
        return self._grabcut_white(safe_rgb(img), face_rect)

    # ---- internal helpers ----

    @staticmethod
    def _is_mostly_white_bg(bgr: np.ndarray) -> bool:
        """
        Return True when the four corner regions are near-white (≥ 220
        in all channels), indicating a photo that already has a white or
        very light background.
        """
        h, w = bgr.shape[:2]
        margin = max(8, min(h, w) // 30)
        corners = [
            bgr[0:margin, 0:margin],                 # top-left
            bgr[0:margin, w - margin:w],             # top-right
            bgr[h - margin:h, 0:margin],             # bottom-left
            bgr[h - margin:h, w - margin:w],         # bottom-right
        ]
        white_ratio = 0.0
        for corner in corners:
            white_ratio += np.mean(corner >= 220)
        white_ratio /= 4.0
        return white_ratio > 0.75

    @staticmethod
    def _clean_white_bg(bgr: np.ndarray) -> np.ndarray:
        """
        Light clean-up: threshold near-white pixels to pure white, apply a
        tiny morphological close to fill small dark specks.
        """
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        _, mask = cv2.threshold(gray, 235, 255, cv2.THRESH_BINARY)
        mask_inv = cv2.bitwise_not(mask)

        # Morph close to remove tiny non-white specks on background
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask_inv = cv2.morphologyEx(mask_inv, cv2.MORPH_CLOSE, kernel)
        # Small dilate to capture edge fringes
        mask_inv = cv2.dilate(mask_inv, kernel, iterations=1)

        mask_3 = cv2.merge([mask_inv] * 3)
        white = np.full_like(bgr, 255)
        return np.where(mask_3 > 0, bgr, white).astype(np.uint8)

    @staticmethod
    def _edge_subject_mask(bgr: np.ndarray) -> np.ndarray | None:
        """
        Attempt to isolate the subject using Canny edges + contour fill.

        Returns a single-channel uint8 mask (255 = subject, 0 = background),
        or None when the method doesn't produce a usable result.
        """
        h, w = bgr.shape[:2]
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

        # Light blur to suppress texture noise
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)

        # Canny edge detection
        edges = cv2.Canny(blurred, 30, 100)

        # Dilate edges to close small gaps
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        edges = cv2.dilate(edges, kernel, iterations=2)

        # Find contours and fill the largest one (presumed subject)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL,
                                        cv2.CHAIN_APPROX_SIMPLE)
        if not contours:
            return None

        mask = np.zeros((h, w), dtype=np.uint8)
        # Fill all reasonably large contours
        min_area = (h * w) * 0.02  # at least 2% of image
        for cnt in contours:
            if cv2.contourArea(cnt) > min_area:
                cv2.drawContours(mask, [cnt], -1, 255, cv2.FILLED)

        if np.count_nonzero(mask) < min_area:
            return None

        # Morph close + open to clean up the mask
        kernel5 = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (5, 5))
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel5)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel5)

        # Feather edges slightly
        mask = cv2.GaussianBlur(mask, (7, 7), 0)

        return mask

    @staticmethod
    def _mask_quality_ok(mask: np.ndarray) -> bool:
        """Heuristic: reject obviously broken masks."""
        h, w = mask.shape[:2]
        coverage = np.count_nonzero(mask > 128) / (h * w)
        return 0.15 < coverage < 0.95

    @staticmethod
    def _composite_on_white(bgr: np.ndarray,
                             mask: np.ndarray) -> np.ndarray:
        """Blend BGR image onto white using a float mask (0-1)."""
        mask_f = mask.astype(np.float32) / 255.0
        mask_3 = np.stack([mask_f] * 3, axis=2)
        white = np.ones_like(bgr, dtype=np.float32) * 255.0
        bgr_f = bgr.astype(np.float32)
        blended = bgr_f * mask_3 + white * (1.0 - mask_3)
        return blended.astype(np.uint8)

    @staticmethod
    def _grabcut_white(bgr: np.ndarray,
                       face_rect: tuple | None = None) -> np.ndarray:
        """
        OpenCV GrabCut with an auto-initialised rectangle, composited
        onto white.  Uses only 2 iterations on a downscaled working copy
        for speed.
        """
        h, w = bgr.shape[:2]

        # Downscale for speed (keep max side ≤ 600 px)
        max_side = max(h, w)
        scale = 1.0
        work = bgr
        if max_side > 600:
            scale = 600.0 / max_side
            work = cv2.resize(bgr, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_AREA)

        wh, ww = work.shape[:2]

        # Build initialisation rectangle
        if face_rect is not None:
            fx, fy, fw, fh = face_rect
            fx = int(fx * scale)
            fy = int(fy * scale)
            fw = int(fw * scale)
            fh = int(fh * scale)
            margin_x = max(10, fw // 2)
            margin_y = max(10, fh // 2)
            rect = (max(0, fx - margin_x),
                    max(0, fy - margin_y),
                    min(ww, fw + 2 * margin_x),
                    min(wh, fh + 2 * margin_y))
        else:
            margin_x = int(ww * 0.08)
            margin_y = int(wh * 0.04)
            rect = (margin_x, margin_y,
                    ww - 2 * margin_x,
                    wh - 2 * margin_y)

        mask = np.zeros((wh, ww), np.uint8)
        bgd = np.zeros((1, 65), np.float64)
        fgd = np.zeros((1, 65), np.float64)

        cv2.grabCut(work, mask, rect, bgd, fgd, 2,
                     cv2.GC_INIT_WITH_RECT)

        # Binary mask: GC_FGD (1) and GC_PR_FGD (3) → subject
        mask2 = np.where((mask == 1) | (mask == 3), 255, 0).astype('uint8')

        # Clean mask edges
        kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        mask2 = cv2.erode(mask2, kernel, iterations=1)

        # Scale mask back to original size
        if scale != 1.0:
            mask2 = cv2.resize(mask2, (w, h),
                                interpolation=cv2.INTER_LINEAR)
            mask2 = (mask2 > 128).astype(np.uint8) * 255

        # Composite
        mask3 = mask2.astype(np.float32) / 255.0
        mask3 = np.stack([mask3] * 3, axis=2)
        white = np.ones_like(bgr, dtype=np.float32) * 255.0
        result = bgr.astype(np.float32) * mask3 + white * (1.0 - mask3)
        return result.astype(np.uint8)
