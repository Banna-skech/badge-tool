"""
Benchmark / validation script — processes all 14 original photos through
the upgraded pipeline and reports timing + output dimensions.
"""
import sys, time, io, zipfile, json, urllib.request
from pathlib import Path

BASE = 'http://127.0.0.1:8008'
PHOTO_DIR = Path(r'C:\Users\07469\Desktop\原图')

photos = sorted(PHOTO_DIR.glob('*.jpg'))
if not photos:
    print("No photos found!")
    sys.exit(1)

print(f'Found {len(photos)} photos\n')

# === Step 1: Upload all photos ===
print('=== Step 1: Upload ===')

# Build multipart body manually with proper encoding
boundary = b'----BenchmarkBoundary'
body = bytearray()
for p in photos:
    with open(p, 'rb') as f:
        data = f.read()
    header = (
        f'--{boundary.decode()}\r\n'
        f'Content-Disposition: form-data; name="files"; filename="{p.name}"\r\n'
        f'Content-Type: image/jpeg\r\n\r\n'
    ).encode('utf-8')
    body.extend(header)
    body.extend(data)
    body.extend(b'\r\n')
body.extend(f'--{boundary.decode()}--\r\n'.encode('utf-8'))

req = urllib.request.Request(
    f'{BASE}/api/upload/photos', data=bytes(body),
    headers={'Content-Type': f'multipart/form-data; boundary={boundary.decode()}'}
)
with urllib.request.urlopen(req, timeout=60) as r:
    result = json.loads(r.read())
sid = result['session_id']
print(f'Session: {sid}, {result["file_count"]} files')
for f in result['files'][:3]:
    print(f'  {f["filename"]}')
print(f'  ... ({len(result["files"])} total)')

# === Step 2: Start processing ===
print('\n=== Step 2: Start processing (badge + seat card) ===')
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
with urllib.request.urlopen(req, timeout=10) as r:
    result = json.loads(r.read())
jid = result['job_id']
print(f'Job ID: {jid}')

# === Step 3: Poll for progress ===
print('\n=== Step 3: Processing progress ===')
start = time.time()
total_time = None
while time.time() - start < 300:
    req = urllib.request.Request(f'{BASE}/api/process/{jid}/status')
    req.add_header('Accept', 'text/event-stream')
    try:
        with urllib.request.urlopen(req, timeout=5) as r:
            raw = r.read().decode('utf-8')
            for line in raw.split('\n'):
                if line.startswith('data: '):
                    evt = json.loads(line[6:])
                    st = evt.get('status', '?')
                    pct = f"{evt.get('progress',0)}/{evt.get('total',0)}"
                    cur = evt.get('current_file', '')
                    errs = evt.get('errors', [])
                    print(f'  [{st}] {pct} {cur}')
                    for e in errs:
                        print(f'    ERROR: {e["filename"]}: {e["error"]}')

                    if st == 'completed':
                        total_time = time.time() - start
                        total = evt.get('total', 1)
                        avg = total_time / total if total else 0
                        print(f'\n  Total time: {total_time:.1f}s for {total} photos')
                        print(f'  Avg per photo: {avg:.1f}s')

                        # === Step 4: Download and verify ===
                        print('\n=== Step 4: Download & verify ZIP ===')
                        dl_req = urllib.request.Request(f'{BASE}/api/process/{jid}/download')
                        with urllib.request.urlopen(dl_req, timeout=30) as dl_r:
                            zip_bytes = dl_r.read()
                        zkb = len(zip_bytes) / 1024
                        print(f'ZIP size: {len(zip_bytes):,} bytes ({zkb:.0f} KB)')

                        with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
                            names = zf.namelist()
                            badge_count = sum(1 for n in names if '工牌照' in n)
                            seat_count = sum(1 for n in names if '座位牌' in n)
                            print(f'Badge photos: {badge_count}, Seat cards: {seat_count}')

                            from PIL import Image
                            print('\n  Sample output dimensions:')
                            badge_names = [n for n in sorted(names) if '工牌照' in n][:3]
                            seat_names = [n for n in sorted(names) if '座位牌' in n][:3]
                            for name in badge_names + seat_names:
                                with zf.open(name) as f:
                                    img = Image.open(f)
                                    r = img.size[0] / img.size[1]
                                    print(f'    {name}: {img.size[0]}x{img.size[1]} ratio={r:.4f}')

                            # Verify all are 1080x1440
                            mismatches = []
                            for name in names:
                                with zf.open(name) as f:
                                    img = Image.open(f)
                                    w, h = img.size
                                    if (w, h) != (1080, 1440):
                                        mismatches.append(f'{name}: {w}x{h}')

                            if mismatches:
                                print(f'\n  ❌ MISMATCHES ({len(mismatches)}):')
                                for m in mismatches[:10]:
                                    print(f'    {m}')
                            else:
                                print(f'\n  ✅ ALL {len(names)} outputs are 1080x1440 (3:4)')

                        print(f'\n{"="*50}')
                        print(f'  BENCHMARK COMPLETE')
                        print(f'  Photos:  {len(photos)}')
                        print(f'  Outputs: {len(names)}')
                        print(f'  Time:    {total_time:.1f}s ({total_time/len(photos):.1f}s/photo)')
                        print(f'  ZIP:     {zkb:.0f} KB')
                        print(f'{"="*50}')
                        sys.exit(0)

                    if st == 'error':
                        print(f'\n  FAILED: {evt.get("error_message","")}')
                        sys.exit(1)
    except Exception as e:
        pass
    time.sleep(1)

print('\nTIMEOUT')
