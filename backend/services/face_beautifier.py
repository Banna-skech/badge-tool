"""
Face beautification service — light skin smoothing & brightening.
Uses OpenCV Haar Cascade for face detection + skin-color masking.
"""
import cv2
import numpy as np


class FaceBeautifier:
    """
    Light, natural face beautification suitable for official badge photos.

    - Skin smoothing via bilateral filter (preserves edges)
    - Subtle brightness increase in HSV space
    - Mask feathering for invisible transitions

    Can accept a pre-detected face rectangle to avoid duplicate detection.
    """

    # Skin colour range in YCrCb (covers East Asian + most skin tones)
    SKIN_YCRCB_MIN = np.array([0, 133, 77], dtype=np.uint8)
    SKIN_YCRCB_MAX = np.array([255, 173, 127], dtype=np.uint8)

    def __init__(self):
        import os
        cascade_path = os.path.join(
            os.path.dirname(__file__),
            'haarcascade_frontalface_default.xml'
        )
        self._face_cascade = cv2.CascadeClassifier(cascade_path)

    @property
    def face_cascade(self):
        return self._face_cascade

    def _detect_face(self, img: np.ndarray) -> tuple | None:
        """
        Detect the primary face.  Returns (x, y, w, h) or None.
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
            return faces[np.argmax(areas)]
        return tuple(faces[0])

    def detect_skin_region(self, img: np.ndarray,
                            face_rect: tuple | None = None) -> np.ndarray | None:
        """
        Create a feathered skin mask using face detection + YCrCb skin colour.

        Returns a uint8 mask (0-255) where 255 = skin, 0 = non-skin,
        or None if no face / skin is found.
        """
        h, w = img.shape[:2]

        if face_rect is None:
            face_rect = self._detect_face(img)
        if face_rect is None:
            return None

        face_x, face_y, face_w, face_h = face_rect
        face_center_x = face_x + face_w // 2
        face_center_y = face_y + face_h // 2

        # Elliptical mask covering the face area
        ellipse_mask = np.zeros((h, w), dtype=np.uint8)
        axes = (int(face_w * 0.8), int(face_h * 0.70))
        cv2.ellipse(ellipse_mask, (face_center_x, face_center_y), axes,
                     0, 0, 360, 255, -1)

        # Refine with skin colour in YCrCb
        ycrcb = cv2.cvtColor(img, cv2.COLOR_BGR2YCrCb)
        skin_color_mask = cv2.inRange(ycrcb, self.SKIN_YCRCB_MIN,
                                       self.SKIN_YCRCB_MAX)

        skin_mask = cv2.bitwise_and(ellipse_mask, skin_color_mask)

        # Exclude eye region (top ~45 % of face)
        eye_y1 = face_y
        eye_y2 = face_y + int(face_h * 0.45)
        eye_x1 = face_x + int(face_w * 0.05)
        eye_x2 = face_x + int(face_w * 0.95)
        skin_mask[eye_y1:eye_y2, eye_x1:eye_x2] = 0

        # Exclude mouth region (bottom ~30 % centre of face)
        mouth_y1 = face_y + int(face_h * 0.60)
        mouth_y2 = face_y + face_h
        mouth_x1 = face_x + int(face_w * 0.15)
        mouth_x2 = face_x + int(face_w * 0.85)
        skin_mask[mouth_y1:mouth_y2, mouth_x1:mouth_x2] = 0

        # Feather edges
        skin_mask = cv2.GaussianBlur(skin_mask, (15, 15), 0)

        return skin_mask

    def beautify(self, img: np.ndarray,
                 face_rect: tuple | None = None) -> np.ndarray:
        """
        Apply light skin smoothing and brightening.

        Args:
            img: BGR uint8 (H, W, 3).
            face_rect: Optional pre-detected (x, y, w, h) to skip detection.

        Returns:
            BGR beautified image (same dimensions).
        """
        skin_mask = self.detect_skin_region(img, face_rect)

        if skin_mask is None:
            return img  # no face → nothing to beautify

        mask_float = skin_mask.astype(np.float32) / 255.0

        # Bilateral filter — smaller kernel for speed (d=5 vs old d=9)
        smoothed = cv2.bilateralFilter(img, d=5, sigmaColor=50, sigmaSpace=50)

        # Blend smoothed with original only in skin regions
        mask_3ch = np.stack([mask_float] * 3, axis=2)
        img_float = img.astype(np.float32)
        smoothed_float = smoothed.astype(np.float32)
        blended = img_float * (1 - mask_3ch) + smoothed_float * mask_3ch

        # Brighten skin in HSV (+8 %)
        hsv = cv2.cvtColor(blended.astype(np.uint8), cv2.COLOR_BGR2HSV)
        h, s, v = cv2.split(hsv)
        v_float = v.astype(np.float32)
        brighten_factor = 1.08
        v_boosted = v_float * (1 + (brighten_factor - 1) * mask_float)
        v_boosted = np.clip(v_boosted, 0, 255).astype(np.uint8)
        hsv_brightened = cv2.merge([h, s, v_boosted])
        result = cv2.cvtColor(hsv_brightened, cv2.COLOR_HSV2BGR)

        return result
