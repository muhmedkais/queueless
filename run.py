import sys
import uvicorn

# Ensure UTF-8 output on Windows consoles
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

if __name__ == "__main__":
    print("=" * 60)
    print("WaitLess - Smart Remote Queue System Starting")
    print("Public Queue URL:     http://localhost:8000")
    print("Join Line Directly:   http://localhost:8000/join")
    print("Staff Manager:        http://localhost:8000/staff")
    print("Success Analytics:    http://localhost:8000/analytics")
    print("=" * 60)
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
