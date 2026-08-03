"""
Photo processing orchestrator — ties together the entire pipeline:
Pre-scale → Bg Remove → Beautify → Crop (Badge + Seat Card)

Output: both badge and seat card at 1080 × 1440 (3:4), white background, JPG.
"""
import gc
import time
import traceback
from typing import Callable

import cv2
import numpy as np

from backend.utils.image_utils import (
    load_image, safe_rgb, encode_jpg, get_dimensions,
)
from backend.services.background_remover import BackgroundRemover
from backend.services.face_beautifier import FaceBeautifier
from backend.services.smart_cropper import SmartCropper, TARGET_W, TARGET_H

# Working size for heavy operations (bg removal, beautify)
WORK_MAX_PX = 1440


class PhotoProcessor:
    """
    Orchestrates the full photo processing pipeline for a single photo.
    Lazy-loads heavy models on first use.
    """

    def __init__(self):
        self._bg_remover: BackgroundRemover | None = None
        self._beautifier: FaceBeautifier | None = None
        self._cropper: SmartCropper | None = None
        self._face_cascade: cv2.CascadeClassifier | None = None

    @property
    def bg_remover(self) -> BackgroundRemover:
        if self._bg_remover is None:
            self._bg_remover = BackgroundRemover()
        return self._bg_remover

    @property
    def beautifier(self) -> FaceBeautifier:
        if self._beautifier is None:
            self._beautifier = FaceBeautifier()
        return self._beautifier

    @property
    def cropper(self) -> SmartCropper:
        if self._cropper is None:
            self._cropper = SmartCropper()
        return self._cropper

    @property
    def face_cascade(self) -> cv2.CascadeClassifier:
        """Shared Haar Cascade — loaded once, used for detection in pipeline."""
        if self._face_cascade is None:
            import os
            cascade_path = os.path.join(
                os.path.dirname(__file__),
                'haarcascade_frontalface_default.xml'
            )
            self._face_cascade = cv2.CascadeClassifier(cascade_path)
        return self._face_cascade

    # ---- face detection (shared across pipeline) ----

    def _detect_face(self, img: np.ndarray) -> tuple | None:
        """
        Detect the primary face once — used by beautifier AND cropper.
        Returns (x, y, w, h) or None.
        """
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        faces = self.face_cascade.detectMultiScale(
            gray, scaleFactor=1.1, minNeighbors=5, minSize=(60, 60)
        )
        if len(faces) == 0:
            faces = self.face_cascade.detectMultiScale(
                gray, scaleFactor=1.05, minNeighbors=3, minSize=(40, 40)
            )

        if len(faces) == 0:
            return None
        if len(faces) > 1:
            areas = [fw * fh for (fx, fy, fw, fh) in faces]
            return tuple(faces[np.argmax(areas)])
        return tuple(faces[0])

    # ---- main pipeline ----

    def process_single(
        self,
        file_bytes: bytes,
        filename: str,
        options: dict[str, bool],
        progress_callback: Callable | None = None
    ) -> dict:
        """
        Process a single photo through the full pipeline.

        Args:
            file_bytes: Raw bytes of the photo file (JPG/PNG).
            filename: Original filename (for logging).
            options: Dict with boolean flags:
                - "badge_photo": bool
                - "seat_card": bool
            progress_callback: Optional callable(stage: str, detail: str).

        Returns:
            Dict with keys:
                - "badge_bytes": bytes | None
                - "seat_bytes": bytes | None
                - "badge_dimensions": (w, h) | None
                - "seat_dimensions": (w, h) | None
                - "filename": str
                - "error": str | None
        """
        t_start = time.time()

        result = {
            "filename": filename,
            "badge_bytes": None,
            "seat_bytes": None,
            "badge_dimensions": None,
            "seat_dimensions": None,
            "error": None,
        }

        img = None
        work_img = None
        face_rect = None

        try:
            # ----------------------------------------------------------------
            # Stage 1: Load & validate
            # ----------------------------------------------------------------
            self._emit(progress_callback, "loading", f"正在加载 {filename}...")
            img = load_image(file_bytes)
            img = safe_rgb(img)
            original_h, original_w = img.shape[:2]

            # ----------------------------------------------------------------
            # Stage 2: Pre-scale to working resolution
            # ----------------------------------------------------------------
            max_dim = max(original_h, original_w)
            if max_dim > WORK_MAX_PX:
                scale = WORK_MAX_PX / max_dim
                work_img = cv2.resize(img, None, fx=scale, fy=scale,
                                       interpolation=cv2.INTER_AREA)
            else:
                work_img = img

            # ----------------------------------------------------------------
            # Stage 3: Face detection (once, shared)
            # ----------------------------------------------------------------
            self._emit(progress_callback, "detect", f"正在检测人脸: {filename}")
            face_rect = self._detect_face(work_img)
            # Map face_rect back to original image coordinates
            if face_rect is not None and work_img is not img:
                inv_scale = max_dim / WORK_MAX_PX
                fx, fy, fw, fh = face_rect
                face_rect_full = (int(fx * inv_scale), int(fy * inv_scale),
                                   int(fw * inv_scale), int(fh * inv_scale))
            else:
                face_rect_full = face_rect

            # ----------------------------------------------------------------
            # Stage 4: Background removal
            # ----------------------------------------------------------------
            self._emit(progress_callback, "background", f"正在抠图换白底: {filename}")
            try:
                work_img = self.bg_remover.remove_background(work_img, face_rect)
            except Exception:
                work_img = self.bg_remover.remove_background_fallback(work_img, face_rect)

            # Scale back up if we downscaled
            if work_img is not img and original_h > WORK_MAX_PX:
                work_img = cv2.resize(work_img, (original_w, original_h),
                                       interpolation=cv2.INTER_LANCZOS4)

            # ----------------------------------------------------------------
            # Stage 5: Face beautification
            # ----------------------------------------------------------------
            self._emit(progress_callback, "beautify", f"正在美颜: {filename}")
            try:
                img = self.beautifier.beautify(work_img, face_rect_full)
            except Exception:
                img = work_img  # beautify failure is non-fatal

            # ----------------------------------------------------------------
            # Stage 6a: Badge photo crop
            # ----------------------------------------------------------------
            if options.get("badge_photo", True):
                self._emit(progress_callback, "badge_crop", f"正在裁剪工牌照: {filename}")
                badge_img = self.cropper.crop_badge_photo(img, face_rect_full)
                bh, bw = badge_img.shape[:2]
                result["badge_dimensions"] = (bw, bh)
                result["badge_bytes"] = encode_jpg(badge_img, quality=95)

            # ----------------------------------------------------------------
            # Stage 6b: Seat card photo crop
            # ----------------------------------------------------------------
            if options.get("seat_card", True):
                self._emit(progress_callback, "seat_crop", f"正在裁剪座位牌: {filename}")
                seat_img = self.cropper.crop_seat_card_photo(img, face_rect_full)
                sh, sw = seat_img.shape[:2]
                result["seat_dimensions"] = (sw, sh)
                result["seat_bytes"] = encode_jpg(seat_img, quality=95)

            elapsed = time.time() - t_start
            self._emit(progress_callback, "done",
                       f"完成: {filename} ({elapsed:.1f}s)")

        except Exception as e:
            result["error"] = str(e)
            self._emit(progress_callback, "error", f"处理失败: {filename} - {e}")
            traceback.print_exc()

        finally:
            # Let Python's GC handle cleanup — explicit del causes
            # scoping issues with Python 3.14's finally-block semantics.
            gc.collect()

        return result

    def _emit(self, callback: Callable | None, stage: str, detail: str):
        """Emit progress event if callback is provided."""
        if callback:
            try:
                callback(stage, detail)
            except Exception:
                pass
