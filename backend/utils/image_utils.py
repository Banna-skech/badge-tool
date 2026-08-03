"""
Image utility functions: load, encode, resize with padding, aspect ratio helpers.
"""
import io
from typing import Tuple

import cv2
import numpy as np
from PIL import Image


def load_image(file_bytes: bytes) -> np.ndarray:
    """
    Load image from raw bytes. Handles JPG, PNG, and other common formats.
    Returns BGR numpy array (OpenCV format).
    """
    nparr = np.frombuffer(file_bytes, np.uint8)
    img = cv2.imdecode(nparr, cv2.IMREAD_UNCHANGED)
    if img is None:
        raise ValueError("无法解码图片，请确认文件格式为 JPG 或 PNG")
    return img


def safe_rgb(img: np.ndarray) -> np.ndarray:
    """
    Convert any OpenCV image to 3-channel BGR.
    - RGBA → BGR (blend with white background)
    - Grayscale → BGR
    """
    if img.ndim == 2:
        return cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

    if img.shape[2] == 4:
        # Alpha blend onto white
        bgr = img[:, :, :3]
        alpha = img[:, :, 3:4].astype(np.float32) / 255.0
        white = np.ones_like(bgr, dtype=np.uint8) * 255
        blended = (bgr.astype(np.float32) * alpha + white.astype(np.float32) * (1 - alpha))
        return blended.astype(np.uint8)

    return img[:, :, :3]


def safe_rgb_rgb(img: np.ndarray) -> np.ndarray:
    """
    Convert any OpenCV image to 3-channel RGB (for PIL/MediaPipe).
    """
    bgr = safe_rgb(img)
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def bgr_to_rgb(img: np.ndarray) -> np.ndarray:
    """BGR → RGB"""
    return cv2.cvtColor(img, cv2.COLOR_BGR2RGB)


def rgb_to_bgr(img: np.ndarray) -> np.ndarray:
    """RGB → BGR"""
    return cv2.cvtColor(img, cv2.COLOR_RGB2BGR)


def get_dimensions(img: np.ndarray) -> Tuple[int, int]:
    """Return (width, height) for an OpenCV image."""
    return img.shape[1], img.shape[0]


def resize_with_padding(
    img: np.ndarray,
    target_width: int,
    target_height: int,
    background_color: Tuple[int, int, int] = (255, 255, 255)
) -> np.ndarray:
    """
    Resize image to fit within target dimensions while maintaining aspect ratio.
    Add padding (background_color) to fill remaining space.
    Returns image at exactly (target_height × target_width).
    """
    h, w = img.shape[:2]
    scale = min(target_width / w, target_height / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_LANCZOS4)

    canvas = np.full((target_height, target_width, 3), background_color, dtype=np.uint8)
    x_offset = (target_width - new_w) // 2
    y_offset = (target_height - new_h) // 2
    canvas[y_offset:y_offset + new_h, x_offset:x_offset + new_w] = resized

    return canvas


def pad_to_aspect_ratio(
    img: np.ndarray,
    target_aspect: float = 4.0 / 3.0,
    background_color: Tuple[int, int, int] = (255, 255, 255)
) -> np.ndarray:
    """
    Pad an image with white to achieve the target aspect ratio (width/height).
    Maintains original pixel resolution — only adds padding, never crops.
    """
    h, w = img.shape[:2]
    current_aspect = w / h

    if abs(current_aspect - target_aspect) < 0.01:
        return img

    if current_aspect > target_aspect:
        # Image is too wide → pad top and bottom
        new_h = int(w / target_aspect)
        pad_total = new_h - h
        pad_top = pad_total // 2
        pad_bottom = pad_total - pad_top
        padded = cv2.copyMakeBorder(
            img, pad_top, pad_bottom, 0, 0,
            cv2.BORDER_CONSTANT, value=background_color
        )
    else:
        # Image is too tall → pad left and right
        new_w = int(h * target_aspect)
        pad_total = new_w - w
        pad_left = pad_total // 2
        pad_right = pad_total - pad_left
        padded = cv2.copyMakeBorder(
            img, 0, 0, pad_left, pad_right,
            cv2.BORDER_CONSTANT, value=background_color
        )

    return padded


def crop_to_aspect_ratio(
    img: np.ndarray,
    target_aspect: float = 4.0 / 3.0,
    center_x: float = 0.5,
    center_y: float = 0.5
) -> np.ndarray:
    """
    Crop from center (or given focal point) to achieve target aspect ratio.
    Maintains original pixel density — extracts the largest possible region.
    center_x, center_y are in [0, 1] range, relative to the image.
    """
    h, w = img.shape[:2]
    current_aspect = w / h

    if abs(current_aspect - target_aspect) < 0.01:
        return img

    if current_aspect > target_aspect:
        # Too wide → crop width
        new_w = int(h * target_aspect)
        crop_center_x = int(w * center_x)
        left = max(0, crop_center_x - new_w // 2)
        right = min(w, left + new_w)
        left = max(0, right - new_w)
        cropped = img[:, left:right]
    else:
        # Too tall → crop height
        new_h = int(w / target_aspect)
        crop_center_y = int(h * center_y)
        top = max(0, crop_center_y - new_h // 2)
        bottom = min(h, top + new_h)
        top = max(0, bottom - new_h)
        cropped = img[top:bottom, :]

    assert abs(cropped.shape[1] / cropped.shape[0] - target_aspect) < 0.02, \
        f"Crop aspect ratio mismatch: {cropped.shape[1] / cropped.shape[0]}"

    return cropped


def encode_jpg(img: np.ndarray, quality: int = 95) -> bytes:
    """Encode BGR image as JPEG bytes."""
    success, buf = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, quality])
    if not success:
        raise RuntimeError("JPEG 编码失败")
    return buf.tobytes()


def encode_png(img: np.ndarray) -> bytes:
    """Encode BGR image as PNG bytes."""
    success, buf = cv2.imencode('.png', img)
    if not success:
        raise RuntimeError("PNG 编码失败")
    return buf.tobytes()


def pil_to_cv2(pil_img: Image.Image) -> np.ndarray:
    """Convert PIL Image to OpenCV BGR numpy array."""
    rgb = np.array(pil_img.convert('RGB'))
    return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)


def cv2_to_pil(cv2_img: np.ndarray) -> Image.Image:
    """Convert OpenCV BGR numpy array to PIL Image."""
    rgb = cv2.cvtColor(cv2_img, cv2.COLOR_BGR2RGB)
    return Image.fromarray(rgb)
