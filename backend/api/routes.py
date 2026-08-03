"""
API routes for the photo processing web application.
"""
import asyncio
import json
import os
import shutil
import tempfile
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Dict, List, Optional
from urllib.parse import quote

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel

from backend.services.name_parser import (
    parse_excel, parse_text, match_photos_to_names,
    extract_names_from_column
)
from backend.services.photo_processor import PhotoProcessor
from backend.services.zip_packager import create_zip, create_zip_from_filename_mode
from backend.services.excel_processor import (
    parse_raw_employee_excel, generate_output_excel
)

router = APIRouter()

# Session storage — in production you'd use Redis, but for local use this is fine
sessions: Dict[str, dict] = {}
# Job storage
jobs: Dict[str, dict] = {}
# Thread pool for CPU-bound image processing
executor = ThreadPoolExecutor(max_workers=4)

# Global processor instance (models loaded once)
processor = PhotoProcessor()

# Temp directory for file storage
TEMP_DIR = Path(__file__).parent.parent.parent / "output"
TEMP_DIR.mkdir(exist_ok=True)


class ProcessOptions(BaseModel):
    session_id: str
    badge_photo: bool = True
    seat_card: bool = True
    namelist_mode: str = "filename"  # "filename" or "namelist"


class NameListColumnSelect(BaseModel):
    session_id: str
    column_name: str


def get_session(session_id: str) -> dict:
    """Get or raise for invalid session ID."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="会话不存在或已过期，请重新上传")
    return sessions[session_id]


@router.post("/upload/photos")
async def upload_photos(files: List[UploadFile] = File(...)):
    """
    Upload a batch of photos. Returns session info with file list.
    """
    if not files:
        raise HTTPException(status_code=400, detail="请至少上传一张照片")

    session_id = str(uuid.uuid4())
    session_dir = TEMP_DIR / session_id
    session_dir.mkdir(parents=True, exist_ok=True)

    file_infos = []
    for f in files:
        if not f.filename:
            continue

        # Validate file type
        ext = f.filename.rsplit('.', 1)[-1].lower() if '.' in f.filename else ''
        if ext not in ('jpg', 'jpeg', 'png'):
            raise HTTPException(
                status_code=400,
                detail=f"不支持的文件格式: {f.filename}（仅支持 JPG 和 PNG）"
            )

        # Save to temp dir
        safe_name = f.filename.replace('\\', '_').replace('/', '_')
        file_path = session_dir / safe_name
        content = await f.read()
        file_path.write_bytes(content)

        file_infos.append({
            "filename": safe_name,
            "size": len(content),
        })

    # Sort by filename (lexicographic order)
    file_infos.sort(key=lambda x: x["filename"].lower())

    sessions[session_id] = {
        "session_id": session_id,
        "session_dir": str(session_dir),
        "files": file_infos,
        "names": None,
        "namelist_mode": "filename",
        "name_column": None,
        "excel_data": None,
        "columns": [],
        "suggested_column": None,
    }

    return {
        "session_id": session_id,
        "file_count": len(file_infos),
        "files": file_infos,
    }


@router.post("/upload/namelist")
async def upload_namelist(session_id: str = Form(...), file: UploadFile = File(...)):
    """
    Upload a name list file (Excel .xlsx or text .txt).
    """
    session = get_session(session_id)
    content = await file.read()

    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''

    if ext in ('xlsx', 'xls'):
        result = parse_excel(content)
        session["excel_data"] = result
        session["columns"] = result["columns"]
        session["suggested_column"] = result["suggested_name_column"]

        # Auto-select the suggested column
        if result["suggested_name_column"]:
            names = extract_names_from_column(result["data"], result["suggested_name_column"])
            session["names"] = names
            session["name_column"] = result["suggested_name_column"]
            session["namelist_mode"] = "namelist"
        else:
            session["names"] = None

        return {
            "success": True,
            "columns": result["columns"],
            "suggested_name_column": result["suggested_name_column"],
            "name_count": len(session["names"]) if session["names"] else 0,
            "file_count": len(session["files"]),
            "names_preview": session["names"][:5] if session["names"] else [],
        }

    elif ext in ('txt', 'csv', 'text'):
        names = parse_text(content)
        session["names"] = names
        session["namelist_mode"] = "namelist"
        session["name_column"] = None
        session["columns"] = []
        session["suggested_column"] = None
        session["excel_data"] = None

        return {
            "success": True,
            "columns": [],
            "name_count": len(names),
            "file_count": len(session["files"]),
            "names_preview": names[:5],
        }
    else:
        raise HTTPException(status_code=400, detail="不支持的文件格式（仅支持 .xlsx、.txt）")


@router.get("/namelist/columns")
async def get_namelist_columns(session_id: str):
    """
    Get available columns from uploaded Excel file.
    """
    session = get_session(session_id)

    if not session.get("columns"):
        raise HTTPException(status_code=400, detail="请先上传 Excel 名单文件")

    # Get matching preview
    photos = session["files"]
    names = session.get("names") or []

    preview = []
    for i, photo in enumerate(photos[:10]):
        name = names[i] if i < len(names) else "?"
        preview.append({"index": i + 1, "photo": photo["filename"], "name": name})

    return {
        "columns": session["columns"],
        "suggested": session.get("suggested_column"),
        "current": session.get("name_column"),
        "preview": preview,
        "photo_count": len(photos),
        "name_count": len(names),
    }


@router.post("/namelist/select-column")
async def select_name_column(body: NameListColumnSelect):
    """
    Select which Excel column contains names.
    """
    session = get_session(body.session_id)

    if not session.get("excel_data"):
        raise HTTPException(status_code=400, detail="请先上传 Excel 名单文件")

    if body.column_name not in session["columns"]:
        raise HTTPException(
            status_code=400,
            detail=f"列名 '{body.column_name}' 不存在"
        )

    names = extract_names_from_column(session["excel_data"]["data"], body.column_name)
    session["names"] = names
    session["name_column"] = body.column_name
    session["namelist_mode"] = "namelist"

    photos = session["files"]
    preview = []
    for i, photo in enumerate(photos[:10]):
        name = names[i] if i < len(names) else "?"
        preview.append({"index": i + 1, "photo": photo["filename"], "name": name})

    return {
        "success": True,
        "name_count": len(names),
        "photo_count": len(photos),
        "preview": preview,
    }


@router.post("/process")
async def start_processing(options: ProcessOptions):
    """
    Start batch processing. Returns a job_id for progress tracking.
    """
    session = get_session(options.session_id)

    job_id = str(uuid.uuid4())[:8]
    jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "progress": 0,
        "total": len(session["files"]),
        "current_file": "",
        "current_stage": "",
        "results": [],
        "errors": [],
    }

    # Launch processing in background
    asyncio.create_task(_run_processing(job_id, options, session))

    return {"job_id": job_id}


async def _run_processing(job_id: str, options: ProcessOptions, session: dict):
    """Run the photo processing pipeline in the background."""
    job = jobs[job_id]
    job["status"] = "processing"

    try:
        files = session["files"]
        session_dir = Path(session["session_dir"])
        names = session.get("names") or []
        namelist_mode = options.namelist_mode

        options_dict = {
            "badge_photo": options.badge_photo,
            "seat_card": options.seat_card,
        }

        # Build name mapping
        name_mapping = {}
        if namelist_mode == "namelist" and names:
            sorted_filenames = [f["filename"] for f in files]
            pairs, warning = match_photos_to_names(sorted_filenames, names)
            for fname, assigned_name in pairs:
                name_mapping[fname] = assigned_name
            if warning:
                job["warning"] = warning
        else:
            # Use original filenames
            for f in files:
                base = f["filename"].rsplit('.', 1)[0] if '.' in f["filename"] else f["filename"]
                name_mapping[f["filename"]] = base

        results = []

        for i, file_info in enumerate(files):
            fname = file_info["filename"]
            file_path = session_dir / fname

            if not file_path.exists():
                results.append({
                    "filename": fname,
                    "badge_bytes": None,
                    "seat_bytes": None,
                    "error": "文件不存在",
                })
                continue

            job["current_file"] = fname
            job["progress"] = i

            file_bytes = file_path.read_bytes()

            # Process in thread pool (CPU-bound)
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(
                executor,
                processor.process_single,
                file_bytes, fname, options_dict,
                None  # progress callback (within thread)
            )

            results.append(result)
            job["progress"] = i + 1

            if result.get("error"):
                job["errors"].append({
                    "filename": fname,
                    "error": result["error"],
                })

        job["results"] = results

        # Build ZIP
        zip_bytes = create_zip(results, name_mapping)
        job["zip_data"] = zip_bytes
        job["zip_size"] = len(zip_bytes)
        job["status"] = "completed"
        job["progress"] = len(files)

    except Exception as e:
        import traceback
        traceback.print_exc()
        job["status"] = "error"
        job["error_message"] = str(e)
        job["progress"] = job.get("progress", 0)


@router.get("/process/{job_id}/status")
async def get_process_status(job_id: str):
    """
    Server-Sent Events (SSE) endpoint for real-time progress updates.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    async def event_stream():
        job = jobs[job_id]
        last_progress = -1

        while True:
            current_progress = job.get("progress", 0)
            total = job.get("total", 0)
            status = job.get("status", "pending")

            if current_progress != last_progress or status in ("completed", "error"):
                last_progress = current_progress
                event_data = json.dumps({
                    "progress": current_progress,
                    "total": total,
                    "status": status,
                    "current_file": job.get("current_file", ""),
                    "warning": job.get("warning"),
                    "error_message": job.get("error_message", ""),
                    "errors": job.get("errors", []),
                }, ensure_ascii=False)

                yield f"data: {event_data}\n\n"

            if status in ("completed", "error"):
                break

            await asyncio.sleep(0.3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        }
    )


@router.get("/process/{job_id}/download")
async def download_result(job_id: str):
    """
    Download the processed ZIP file.
    """
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="任务不存在或已过期")

    job = jobs[job_id]

    if job.get("status") != "completed":
        raise HTTPException(status_code=400, detail="处理尚未完成")

    zip_data = job.get("zip_data")
    if not zip_data:
        raise HTTPException(status_code=400, detail="无数据可下载")

    return Response(
        content=zip_data,
        media_type="application/zip",
        headers={
            "Content-Disposition": f"attachment; filename=processed_photos_{job_id}.zip",
            "Content-Length": str(len(zip_data)),
        }
    )


@router.get("/save/namelist")
async def generate_empty_namelist():
    """
    Generate a template name list file for download.
    """
    template = "姓名1\n姓名2\n姓名3\n姓名4\n姓名5\n"
    return Response(
        content=template.encode('utf-8'),
        media_type="text/plain; charset=utf-8",
        headers={
            "Content-Disposition": "attachment; filename=名单模板.txt"
        }
    )


# ── Excel employee table processing ──────────────────────────────────

class ExcelColumnMapping(BaseModel):
    """User-adjusted column mapping for Excel processing."""
    name_col: Optional[str] = None      # 姓名
    engname_col: Optional[str] = None   # 英文名/姓名拼音
    jobno_col: Optional[str] = None     # 工号
    dept2_col: Optional[str] = None     # 二级部门
    dept3_col: Optional[str] = None     # 三级部门
    position_col: Optional[str] = None  # 详细职位名称
    location_col: Optional[str] = None  # 工作地点


@router.post("/excel/upload")
async def upload_employee_excel(file: UploadFile = File(...)):
    """
    Upload a raw employee Excel export and return parsed preview.
    Supports the standard HR system two-row header format.
    """
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ('xlsx', 'xls'):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 格式的 Excel 文件")

    content = await file.read()

    try:
        parsed = parse_raw_employee_excel(content)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Excel 解析失败：{str(e)}")

    # Build a user-friendly column mapping display
    detected_map = {}
    field_labels = {
        "姓名": "姓名", "英文名": "英文名/姓名拼音", "工号": "工号",
        "二级部门": "二级部门", "三级部门": "三级部门", "职位": "详细职位名称",
        "工作地点": "工作地点",
    }
    for field, idx in parsed["column_map"].items():
        label = field_labels.get(field, field)
        detected_map[field] = {
            "label": label,
            "source_column": parsed["chinese_headers"][idx] if idx < len(parsed["chinese_headers"]) else "",
            "column_index": idx,
        }

    return {
        "success": True,
        "chinese_headers": parsed["chinese_headers"],
        "detected_columns": detected_map,
        "total_rows": parsed["total_rows"],
        "preview": parsed["preview"],
        "col_count": len(parsed["chinese_headers"]),
    }


@router.post("/excel/process")
async def process_employee_excel(file: UploadFile = File(...)):
    """
    Process a raw employee Excel and return the formatted output file
    with two sheets: 工牌 (sorted by 工号) and 座位牌 (sorted by 部门).
    """
    ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
    if ext not in ('xlsx', 'xls'):
        raise HTTPException(status_code=400, detail="仅支持 .xlsx 格式的 Excel 文件")

    content = await file.read()

    try:
        parsed = parse_raw_employee_excel(content)
        output_bytes = generate_output_excel(parsed)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"处理失败：{str(e)}")

    # Build a clean output filename
    base_name = file.filename.rsplit('.', 1)[0] if '.' in file.filename else file.filename
    output_filename = f"{base_name}_工牌座位牌.xlsx"
    encoded_filename = quote(output_filename)

    return Response(
        content=output_bytes,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": f"attachment; filename*=UTF-8''{encoded_filename}",
            "Content-Length": str(len(output_bytes)),
        }
    )
