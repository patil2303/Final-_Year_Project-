import os
import sys
import uvicorn

if __name__ == "__main__":
    port_env = os.environ.get("PORT", "10000")
    try:
        port = int(port_env)
    except (ValueError, TypeError):
        port = 10000

    print(f"[Startup] Launching FastAPI server on 0.0.0.0:{port}...")
    uvicorn.run("backend.app:app", host="0.0.0.0", port=port, log_level="info")
