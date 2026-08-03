"""
ZIP packaging service.
Creates download-ready archive with proper folder structure.
"""
import io
import zipfile
from typing import List, Dict


def create_zip(
    processed_results: List[Dict],
    name_mapping: Dict[str, str],  # original_filename → assigned_name
    base_name: str = ""
) -> bytes:
    """
    Create a ZIP file containing all processed photos.

    Folder structure:
        工牌照/
            张三.jpg
            李四.jpg
            ...
        座位牌/
            张三.png
            李四.png
            ...

    Args:
        processed_results: List of result dicts from PhotoProcessor.process_single()
            Each dict has: filename, badge_bytes, seat_bytes
        name_mapping: Dict mapping original_filename → assigned Chinese name
        base_name: Optional base name for the root folder in the ZIP

    Returns:
        Raw ZIP file bytes
    """
    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, 'w', zipfile.ZIP_DEFLATED) as zf:
        for result in processed_results:
            if result.get("error") and not result.get("badge_bytes") and not result.get("seat_bytes"):
                continue  # Skip completely failed photos

            original_filename = result["filename"]
            assigned_name = name_mapping.get(original_filename, original_filename)

            # Clean filename: remove original extension
            assigned_name_clean = assigned_name.rsplit('.', 1)[0] if '.' in assigned_name else assigned_name

            # Badge photo
            if result.get("badge_bytes"):
                badge_path = f"工牌照/{assigned_name_clean}.jpg"
                zf.writestr(badge_path, result["badge_bytes"])

            # Seat card photo
            if result.get("seat_bytes"):
                seat_path = f"座位牌/{assigned_name_clean}.jpg"
                zf.writestr(seat_path, result["seat_bytes"])

    buffer.seek(0)
    return buffer.getvalue()


def create_zip_from_filename_mode(processed_results: List[Dict]) -> bytes:
    """
    Create ZIP using original filenames (stripped of extension) as names.
    """
    name_mapping = {}
    for r in processed_results:
        fname = r["filename"]
        base = fname.rsplit('.', 1)[0] if '.' in fname else fname
        name_mapping[fname] = base

    return create_zip(processed_results, name_mapping)
