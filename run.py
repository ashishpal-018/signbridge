import os
import sys

# Anchor paths so BACKEND and FRONTEND are cleanly importableh
ROOT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(ROOT_DIR, "BACKEND"))
sys.path.insert(0, os.path.join(ROOT_DIR, "FRONTEND"))

import uvicorn
from database import init_db

if __name__ == "__main__":
    init_db()
    port = int(os.getenv("PORT", 8000))
    print("===========================================================")
    print(f"  SignBridge Server starting at http://127.0.0.1:{port}")
    print("===========================================================")
    uvicorn.run("main:app", host="127.0.0.1", port=port, reload=True, app_dir=os.path.join(ROOT_DIR, "FRONTEND"))
