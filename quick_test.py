"""Quick end-to-end test — finds a test photo via glob and tests the full pipeline."""
import os, glob, io, zipfile, json, time, urllib.request, sys

BASE = 'http://localhost:8010'

# Find a test photo
photo_dir = r'C:\Users\07469\Desktop\工牌、座位牌\工牌、座位牌\7月员工照片\0702工牌照'
photos = glob.glob(os.path.join(photo_dir, '*.jpg'))
if not photos:
    print("No test photos found!")
    sys.exit(1)

test_photo = photos[0]
photo_name = os.path.basename(test_photo)
print(f"Using test photo: {photo_name} ({os.path.getsize(test_photo)} bytes)")

# Step 1: Upload
print("\n=== Step 1: Upload photo ===")
boundary = '----TestBoundary'
with open(test_photo, 'rb') as f:
    photo_data = f.read()

body = (
    f'--{boundary}\r\n'
    f'Content-Disposition: form-data; name="files"; filename="test.jpg"\r\n'
    f'Content-Type: image/jpeg\r\n\r\n'
).encode('ascii')
body += photo_data
body += f'\r\n--{boundary}--\r\n'.encode('ascii')

req = urllib.request.Request(
    f'{BASE}/api/upload/photos', data=body,
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)
with urllib.request.urlopen(req) as r:
    result = json.loads(r.read())
sid = result['session_id']
print(f"Session: {sid}")

# Step 2: Start processing
print("\n=== Step 2: Start processing ===")
data = json.dumps({
    'session_id': sid,
    'badge_photo': True,
    'seat_card': True,
    'namelist_mode': 'filename'
}).encode()
req = urllib.request.Request(
    f'{BASE}/api/process', data=data,
    headers={'Content-Type': 'application/json'}
)
with urllib.request.urlopen(req) as r:
    result = json.loads(r.read())
jid = result['job_id']
print(f"Job ID: {jid}")

# Step 3: Poll until completion or timeout
print("\n=== Step 3: Wait for completion ===")
start = time.time()
while time.time() - start < 180:  # 3 min max
    req = urllib.request.Request(f'{BASE}/api/process/{jid}/status')
    req.add_header('Accept', 'text/event-stream')
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read().decode()
            for line in raw.split('\n'):
                if line.startswith('data: '):
                    evt = json.loads(line[6:])
                    st = evt.get('status', '?')
                    pct = f"{evt.get('progress',0)}/{evt.get('total',0)}"
                    err = evt.get('error_message', '')
                    fname = evt.get('current_file', '')
                    print(f"  [{st}] {pct} {fname} {err}")

                    if st == 'completed':
                        # Step 4: Download
                        print("\n=== Step 4: Download ZIP ===")
                        dl_req = urllib.request.Request(f'{BASE}/api/process/{jid}/download')
                        with urllib.request.urlopen(dl_req) as dl_r:
                            zip_bytes = dl_r.read()
                        print(f"ZIP size: {len(zip_bytes)} bytes")

                        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                            for name in zf.namelist():
                                info = zf.getinfo(name)
                                print(f"  {name} ({info.file_size} bytes)")

                        print("\n" + "=" * 40)
                        print("  TEST PASSED")
                        print("=" * 40)
                        sys.exit(0)

                    if st == 'error':
                        print(f"\n  FAILED: {err}")
                        sys.exit(1)
    except Exception as e:
        pass
    time.sleep(2)

print("\nTIMEOUT - job did not complete")
