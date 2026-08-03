"""
Smart cropping service — badge & seat-card photos.

Both output types share the same target:
  - Aspect ratio:  3:4  (portrait)
  - Resolution:    1080 × 1440 px
  - Background:    white (#FFFFFF)

The difference is the crop range:
  - Badge photo:  tight head-and-shoulders  (face ~40-50 % of frame height)
  - Seat card:    head to below-hands        (face ~20-25 % of frame height)
"""
import cv2
import numpy as np

from backend.utils.image_utils import pad_to_aspect_ratio

# Target output size
TARGET_W = 1080
TARGET_H = 1440
TARGET_ASPECT = TARGET_W / TARGET_H   # 0.75  (3:4)


class SmartCropper:
    """
    Crops a subject-on-white image to a standard badge or seat-card format.

    Expects a pre-detected face rectangle to be passed in (shared with the
    beautifier so Haar Cascade runs only once per image).
    """

    # Crop parameters (expressed in face-heights)
    BADGE_TOP_MARGIN = 0.40       # above face top
    BADGE_BOTTOM_MARGIN = 0.65    # below face bottom
    SEAT_TOP_MARGIN = 0.30        # above face top (slightly less headroom)
    SEAT_BOTTOM_MARGIN = 5.8      # below face top → covers head to waist

    # ---- public API ----

    def crop_badge_photo(self, img: np.ndarray,
                         face_rect: tuple | None = None) -> np.ndarray:
        """
        Crop to tight head-and-shoulders badge photo at 1080 × 1440.
        """
        return self._crop_to_target(
            img, face_rect,
            top_margin=self.BADGE_TOP_MARGIN,
            bottom_margin=self.BADGE_BOTTOM_MARGIN,
            bottom_from='bottom',
        )

    def crop_seat_card_photo(self, img: np.ndarray,
                              face_rect: tuple | None = None) -> np.ndarray:
        """
        Crop to seat-card photo (head to waist) at 1080 × 1440.
        """
        return self._crop_to_target(
            img, face_rect,
            top_margin=self.SEAT_TOP_MARGIN,
            bottom_margin=self.SEAT_BOTTOM_MARGIN,
            bottom_from='top',
        )

    # ---- internal ----

    def _crop_to_target(self, img: np.ndarray,
                         face_rect: tuple | None,
                         top_margin: float,
                         bottom_margin: float,
                         bottom_from: str) -> np.ndarray:
        """
        Core crop logic.

        Args:
            img: BGR uint8 (H, W, 3).
            face_rect: (x, y, w, h) or None.
            top_margin: face-heights above the face reference point.
            bottom_margin: face-heights below the face reference point.
            bottom_from: 'bottom' → measure from face bottom;
                         'top'    → measure from face top.

        Returns:
            BGR uint8 at exactly TARGET_W × TARGET_H.
        """
        h, w = img.shape[:2]

        if face_rect is not None:
            fx, fy, fw, fh = face_rect
            face_cx = fx + fw // 2
            face_cy = fy + fh // 2

            # Build crop rectangle in original image coordinates
            top = max(0, int(fy - top_margin * fh))
            if bottom_from == 'bottom':
                bot = min(h, int(fy + fh + bottom_margin * fh))
            else:
                bot = min(h, int(fy + bottom_margin * fh))

            crop_h = bot - top
            crop_w = int(crop_h * TARGET_ASPECT)

            left = face_cx - crop_w // 2
            right = left + crop_w

            # Clamp to image bounds
            if left < 0:
                left = 0
                right = min(w, crop_w)
            if right > w:
                right = w
                left = max(0, right - crop_w)

            # Recalculate height from actual width to keep exact ratio
            actual_w = right - left
            target_h_from_w = int(actual_w / TARGET_ASPECT)
            if top + target_h_from_w > h:
                bot = h
                top = max(0, h - target_h_from_w)
            else:
                bot = top + target_h_from_w

            cropped = img[top:bot, left:right]
        else:
            # No face detected — centre-crop to 3:4
            cropped = self._fallback_center_crop(img)

        # Pad to exact 3:4 with white
        cropped = pad_to_aspect_ratio(cropped, TARGET_ASPECT, (255, 255, 255))

        # Resize to exact target dimensions
        ch, cw = cropped.shape[:2]
        if (cw, ch) != (TARGET_W, TARGET_H):
            cropped = cv2.resize(cropped, (TARGET_W, TARGET_H),
                                  interpolation=cv2.INTER_LANCZOS4)

        return cropped

    @staticmethod
    def _fallback_center_crop(img: np.ndarray) -> np.ndarray:
        """
        Centre-crop to 3:4 when no face is detected.
        Assumes the subject is roughly centred.
        """
        h, w = img.shape[:2]
        current_ratio = w / h

        if current_ratio > TARGET_ASPECT:
            # Too wide — crop sides
            new_w = int(h * TARGET_ASPECT)
            left = (w - new_w) // 2
            return img[:, left:left + new_w]
        elif current_ratio < TARGET_ASPECT:
            # Too tall — crop from top (head is usually in the upper portion)
            new_h = int(w / TARGET_ASPECT)
            top = int(h * 0.05)
            top = min(top, h - new_h)
            return img[top:top + new_h, :]
        return img
