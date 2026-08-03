"""
工牌照 & 座位牌 批量照片处理工具
FastAPI backend entry point
"""
import sys
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from backend.api.routes import router as api_router

app = FastAPI(title="员工照片批量处理工具", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Health check
@app.get("/health")
async def health_check():
    return {"status": "ok", "version": "1.0.0"}

# API routes
app.include_router(api_router, prefix="/api")

# Serve frontend
frontend_dir = Path(__file__).parent.parent / "frontend"
js_dir = frontend_dir / "js"

# Mount JS files
if js_dir.exists():
    app.mount("/js", StaticFiles(directory=str(js_dir)), name="js")


@app.get("/")
async def serve_index():
    """Serve the main page."""
    return FileResponse(str(frontend_dir / "index.html"))


@app.get("/excel")
async def serve_excel_tool():
    """Serve the standalone Excel processing tool (no server needed)."""
    return FileResponse(str(frontend_dir / "excel-tool.html"))
