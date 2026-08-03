import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
print("Starting import...")
try:
    from backend.api.routes import router
    print("Router loaded successfully")
    for r in router.routes:
        print(f"  {r.methods} {r.path}")
except MemoryError as e:
    print(f"MemoryError: {e}")
except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")

print("Done")
