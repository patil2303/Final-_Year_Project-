import sys
import time
import os
import webbrowser
import uvicorn

def main():
    print("=" * 70)
    print("  PHOTO TO EXCEL / CSV CONVERTER - SECTION & NUMBER EXTRACTION ENGINE")
    print("=" * 70)
    print(" [1/3] Checking environment & dependencies...")

    try:
        import easyocr
        import cv2
        import pandas
        import openpyxl
        import fastapi
        print(" [OK] Core packages verified (EasyOCR, OpenCV, Pandas, OpenPyXL, FastAPI).")
    except ImportError as e:
        print(f" [X] Missing package: {e}")
        sys.exit(1)

    host = "127.0.0.1"
    port = 8000
    url = f"http://{host}:{port}"

    print(f" [2/3] Server starting on {url} ...")
    print(" [3/3] Launching web browser interface...")

    def open_browser():
        time.sleep(1.5)
        webbrowser.open(url)

    import threading
    threading.Thread(target=open_browser, daemon=True).start()

    print("-" * 70)
    print(f"  App is running at: {url}")
    print("  Press Ctrl+C in this terminal window to stop the server.")
    print("=" * 70)

    uvicorn.run("backend.app:app", host=host, port=port, reload=False)

if __name__ == "__main__":
    main()
