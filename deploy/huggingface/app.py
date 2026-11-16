"""Entry point for a free Hugging Face Space (Gradio SDK).

The Space runs `python app.py`. Instead of a Gradio interface, this starts NeuroTwin's own server, which serves the
prebuilt web app from frontend/dist. Settings match start-imaging.ps1; anything set in the Space's
"Variables and secrets" wins over these defaults. Provider keys come only from the Space secrets.
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
DATA = ROOT / "data"
DATA.mkdir(exist_ok=True)

defaults = {
    "NEUROTWIN_DATABASE_URL": f"sqlite:///{DATA / 'neurotwin.db'}",
    "NEUROTWIN_IMAGING_USERS": "demo-dr-layla",
    "NEUROTWIN_SEED_HISTORY": "1",
    "NEUROTWIN_SECURE_COOKIES": "1",
}
for key, value in defaults.items():
    os.environ.setdefault(key, value)

os.chdir(BACKEND)
sys.path.insert(0, str(BACKEND))

import uvicorn  # noqa: E402

if __name__ == "__main__":
    uvicorn.run("app.main:create_app", factory=True, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)),
                proxy_headers=True, forwarded_allow_ips="*", access_log=False)
