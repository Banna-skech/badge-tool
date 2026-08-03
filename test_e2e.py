"""
End-to-end test: upload photos, process, download ZIP.
Uses 2 sample photos from the user's existing data.
"""
import os
import sys
import time
import json
import urllib.request
import urllib.parse
from pathlib import Path

BASE_URL = "http://localhost:8010"
SAMPLE_DIR = Path(r"C:\Users\07469\Desktop\工牌、座位牌\工牌、座位牌\7月员工照片\0702工牌照")

def upload_photos(session):
    """Upload sample photos."""
    photos = sorted(SAMPLE_DIR.glob("*.jpg"))[:2]  # 2 photos for quick test
    if not photos:
        print("No sample photos found!")
        return None

    print(f"Uploading {len(photos)} photos: {[p.name for p in photos]}")

    # Build multipart form data
    boundary = '----TestBoundary12345'
    body = b''

    for photo in photos:
        body += f'--{boundary}\r\n'.encode()
        body += f'Content-Disposition: form-data; name="files"; filename="{photo.name}"\r\n'.encode()
        body += b'Content-Type: image/jpeg\r\n\r\n'
        body += photo.read_bytes()
        body += b'\r\n'

    body += f'--{boundary}--\r\n'.encode()

    req = urllib.request.Request(
        f"{BASE_URL}/api/upload/photos",
        data=body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())

    print(f"Upload result: {result['file_count']} files, session={result['session_id']}")
    return result

def upload_namelist(session_id):
    """Upload name list from Excel."""
    xlsx_path = SAMPLE_DIR / "0702工牌信息.xlsx"
    if not xlsx_path.exists():
        print("Excel not found, using text mode")
        return None

    print(f"Uploading name list: {xlsx_path.name}")

    boundary = '----TestBoundary67890'
    body = b''
    body += f'--{boundary}\r\n'.encode()
    body += f'Content-Disposition: form-data; name="session_id"\r\n\r\n'.encode()
    body += session_id.encode()
    body += b'\r\n'
    body += f'--{boundary}\r\n'.encode()
    body += f'Content-Disposition: form-data; name="file"; filename="{xlsx_path.name}"\r\n'.encode()
    body += b'Content-Type: application/vnd.openxmlformats-officedocument.spreadsheetml.sheet\r\n\r\n'
    body += xlsx_path.read_bytes()
    body += b'\r\n'
    body += f'--{boundary}--\r\n'.encode()

    req = urllib.request.Request(
        f"{BASE_URL}/api/upload/namelist",
        data=body,
        headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())

    print(f"Namelist result: {result.get('name_count', 0)} names, columns={result.get('columns', [])}")
    return result

def start_process(session_id, namelist_mode="filename"):
    """Start the batch processing job."""
    print(f"Starting processing (mode={namelist_mode})...")

    data = json.dumps({
        "session_id": session_id,
        "badge_photo": True,
        "seat_card": True,
        "namelist_mode": namelist_mode,
    }).encode()

    req = urllib.request.Request(
        f"{BASE_URL}/api/process",
        data=data,
        headers={'Content-Type': 'application/json'}
    )

    with urllib.request.urlopen(req) as resp:
        result = json.loads(resp.read().decode())

    print(f"Job started: {result['job_id']}")
    return result['job_id']

def wait_for_completion(job_id, timeout=300):
    """Poll SSE endpoint for completion."""
    print(f"Waiting for job {job_id} to complete...")

    start = time.time()
    last_progress = -1

    while time.time() - start < timeout:
        req = urllib.request.Request(f"{BASE_URL}/api/process/{job_id}/status")
        req.add_header('Accept', 'text/event-stream')

        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                data = resp.read().decode()
                for line in data.split('\n'):
                    if line.startswith('data: '):
                        event = json.loads(line[6:])
                        progress = event.get('progress', 0)
                        total = event.get('total', 0)
                        status = event.get('status', '')

                        if progress != last_progress:
                            last_progress = progress
                            pct = round(progress / total * 100) if total else 0
                            print(f"  Progress: {progress}/{total} ({pct}%) - {event.get('current_file', '')}")

                        if status == 'completed':
                            print(f"  ✅ Completed! Errors: {len(event.get('errors', []))}")
                            return event
                        elif status == 'error':
                            print(f"  ❌ Failed!")
                            return event
        except Exception as e:
            pass

        time.sleep(1)

    print("  ⚠ Timeout waiting for completion")
    return None

def download_result(job_id):
    """Download the ZIP file."""
    print(f"Downloading result ZIP...")

    req = urllib.request.Request(f"{BASE_URL}/api/process/{job_id}/download")

    with urllib.request.urlopen(req) as resp:
        zip_data = resp.read()

    output_path = Path(__file__).parent / "test_output.zip"
    output_path.write_bytes(zip_data)
    print(f"Downloaded: {len(zip_data)} bytes → {output_path}")

    # List contents
    import zipfile, io
    with zipfile.ZipFile(io.BytesIO(zip_data)) as zf:
        for name in zf.namelist():
            info = zf.getinfo(name)
            print(f"  {name} ({info.file_size} bytes)")

    return True

def main():
    print("=" * 60)
    print("End-to-End Test: Photo Processor")
    print("=" * 60)

    # Step 1: Upload photos
    result = upload_photos(None)
    if not result:
        print("❌ Upload failed")
        return

    session_id = result['session_id']

    # Step 2: Upload name list (Excel)
    namelist_result = upload_namelist(session_id)

    # Step 3: Start processing
    mode = "namelist" if namelist_result else "filename"
    job_id = start_process(session_id, mode)

    # Step 4: Wait for completion
    event = wait_for_completion(job_id)
    if not event or event.get('status') != 'completed':
        print("❌ Processing failed")
        return

    # Step 5: Download
    download_result(job_id)

    print("\n✅ End-to-end test passed!")

if __name__ == '__main__':
    main()
