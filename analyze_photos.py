"""
Analyze all reference photos — originals vs badge vs seat card.
Finds exact dimensions, ratios, and crop patterns.
"""
import os, sys
from pathlib import Path
from PIL import Image

# Windows console encoding fix
sys.stdout.reconfigure(encoding='utf-8')

def scan_dir(d, label, photo_type):
    """Scan a directory for images and return dimension info."""
    results = []
    if not d.exists():
        print(f"  SKIP (not found): {d}")
        return results
    for f in sorted(d.iterdir()):
        if f.suffix.lower() in ('.jpg', '.jpeg', '.png'):
            try:
                img = Image.open(f)
                w, h = img.size
                results.append({
                    'batch': label,
                    'name': f.stem,
                    'w': w, 'h': h,
                    'ratio': round(w/h, 4),
                    'mp': round(w*h/1e6, 2),
                    'type': photo_type,
                })
            except Exception as e:
                print(f"  ERROR reading {f.name}: {e}")
    return results

def stats(items, label):
    """Print summary statistics."""
    if not items:
        print(f'\n=== {label}: NO DATA ===')
        return
    dims = [(r['w'], r['h']) for r in items]
    ratios = [r['ratio'] for r in items]
    widths = [r['w'] for r in items]
    heights = [r['h'] for r in items]
    unique_dims = sorted(set(dims))

    print(f'\n{"="*60}')
    print(f'=== {label} ({len(items)} photos) ===')
    print(f'  Unique dimensions: {unique_dims}')
    print(f'  Width:  {min(widths)}-{max(widths)} (avg {sum(widths)/len(widths):.0f})')
    print(f'  Height: {min(heights)}-{max(heights)} (avg {sum(heights)/len(heights):.0f})')
    print(f'  Ratio:  {min(ratios):.4f} - {max(ratios):.4f} (avg {sum(ratios)/len(ratios):.4f})')

    # Print first few
    for r in items[:5]:
        print(f'  {r["batch"]:25s} {r["name"]:12s} {r["w"]:5d}x{r["h"]:<5d}  r={r["ratio"]:.4f}  {r["mp"]:.2f}MP')
    if len(items) > 5:
        print(f'  ... ({len(items)-5} more)')

all_results = []

# === ORIGINALS ===
orig_dir = Path(r'C:\Users\07469\Desktop\原图')
print('\nScanning originals...')
originals = scan_dir(orig_dir, '原图', 'original')
all_results.extend(originals)
stats(originals, '原图 (ORIGINALS)')

# === 0702 BADGE ===
base = Path(r'C:\Users\07469\Desktop\工牌、座位牌\工牌、座位牌')
badge_0702_dir = base / '7月员工照片' / '0702工牌照'
seat_0702_dir = base / '7月员工照片' / '0702座位牌'
badge_0716_dir = base / '7月员工照片' / '0716工牌照'
seat_0716_dir = base / '7月员工照片' / '0716座位牌'

print('\nScanning 0702 badge photos...')
badges_0702 = scan_dir(badge_0702_dir, '0702工牌照', 'badge')
all_results.extend(badges_0702)
stats(badges_0702, '0702 工牌照 (BADGE)')

print('\nScanning 0702 seat card photos...')
seats_0702 = scan_dir(seat_0702_dir, '0702座位牌', 'seat_card')
all_results.extend(seats_0702)
stats(seats_0702, '0702 座位牌 (SEAT CARD)')

print('\nScanning 0716 badge photos...')
badges_0716 = scan_dir(badge_0716_dir, '0716工牌照', 'badge')
all_results.extend(badges_0716)
stats(badges_0716, '0716 工牌照 (BADGE)')

print('\nScanning 0716 seat card photos...')
seats_0716 = scan_dir(seat_0716_dir, '0716座位牌', 'seat_card')
all_results.extend(seats_0716)
stats(seats_0716, '0716 座位牌 (SEAT CARD)')

# === Also scan other batches ===
for batch_name, label in [
    ('6月员工照片/0603工牌照', '0603工牌照'),
    ('6月员工照片/0603座位牌', '0603座位牌'),
    ('6月员工照片/0612工牌照', '0612工牌照'),
    ('6月员工照片/0612座位牌', '0612座位牌'),
    ('6月员工照片/0624工牌照', '0624工牌照'),
    ('6月员工照片/0624座位牌', '0624座位牌'),
]:
    d = base / batch_name
    if d.exists():
        print(f'\nScanning {label}...')
        ptype = 'badge' if '工牌' in batch_name else 'seat_card'
        r = scan_dir(d, label, ptype)
        all_results.extend(r)
        stats(r, label)

# === CROSS-REFERENCE: match originals to 0716 processed ===
print(f'\n{"="*60}')
print('=== CROSS-REFERENCE: 原图 vs 0716工牌照 vs 0716座位牌 ===')
orig_by_name = {r['name']: r for r in originals}
badge0716_by_name = {r['name']: r for r in badges_0716}
seat0716_by_name = {r['name']: r for r in seats_0716}

matched = set(orig_by_name.keys()) & set(badge0716_by_name.keys()) & set(seat0716_by_name.keys())
print(f'Matched names: {len(matched)} / {len(originals)} originals')
print(f'Originals without match: {set(orig_by_name.keys()) - matched}')
print()

for name in sorted(matched):
    o = orig_by_name[name]
    b = badge0716_by_name[name]
    s = seat0716_by_name[name]
    print(f'{name}:')
    print(f'  原图:    {o["w"]:5d}x{o["h"]:<5d}  ratio={o["ratio"]:.4f}  ({o["mp"]:.2f}MP)')
    print(f'  工牌照:  {b["w"]:5d}x{b["h"]:<5d}  ratio={b["ratio"]:.4f}  ({b["mp"]:.2f}MP)')
    print(f'  座位牌:  {s["w"]:5d}x{s["h"]:<5d}  ratio={s["ratio"]:.4f}  ({s["mp"]:.2f}MP)')
    # Calculate how much was cropped
    o_area = o['w'] * o['h']
    b_area = b['w'] * b['h']
    s_area = s['w'] * s['h']
    print(f'  面积变化: 工牌={b_area/o_area*100:.1f}%  座位={s_area/o_area*100:.1f}%')
    print()

# === OVERALL ANALYSIS ===
print(f'\n{"="*60}')
print('=== OVERALL PATTERN ANALYSIS ===')

# Badge photos from ALL batches
all_badges = [r for r in all_results if r['type'] == 'badge']
all_seats = [r for r in all_results if r['type'] == 'seat_card']

# Check consistency across batches
badge_dims_all = sorted(set((r['w'], r['h']) for r in all_badges))
seat_dims_all = sorted(set((r['w'], r['h']) for r in all_seats))

print(f'\nAll badge photo dimensions across all batches:')
for d in badge_dims_all:
    count = sum(1 for r in all_badges if (r['w'], r['h']) == d)
    print(f'  {d[0]}x{d[1]} (ratio={d[0]/d[1]:.4f}) — {count} photos')

print(f'\nAll seat card dimensions across all batches:')
for d in seat_dims_all:
    count = sum(1 for r in all_seats if (r['w'], r['h']) == d)
    print(f'  {d[0]}x{d[1]} (ratio={d[0]/d[1]:.4f}) — {count} photos')

# Also look at ratio consistency
badge_ratios = sorted(set(r['ratio'] for r in all_badges))
seat_ratios = sorted(set(r['ratio'] for r in all_seats))
print(f'\nBadge ratios seen: {badge_ratios}')
print(f'Seat card ratios seen: {seat_ratios}')

# Determine the target output dimensions
print(f'\n=== RECOMMENDATION ===')
if badge_dims_all:
    # Most common badge dimension
    from collections import Counter
    badge_dim_counter = Counter((r['w'], r['h']) for r in all_badges)
    most_common_badge = badge_dim_counter.most_common(1)[0]
    print(f'Badge target: {most_common_badge[0][0]}x{most_common_badge[0][1]} (ratio={most_common_badge[0][0]/most_common_badge[0][1]:.4f}) — {most_common_badge[1]} photos')

if seat_dims_all:
    seat_dim_counter = Counter((r['w'], r['h']) for r in all_seats)
    most_common_seat = seat_dim_counter.most_common(1)[0]
    print(f'Seat target: {most_common_seat[0][0]}x{most_common_seat[0][1]} (ratio={most_common_seat[0][0]/most_common_seat[0][1]:.4f}) — {most_common_seat[1]} photos')
