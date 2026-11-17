"""Entry point for a free Hugging Face Space (Gradio SDK).

The Space runs `python app.py`. Instead of a Gradio interface, this starts NeuroTwin's own server, which serves the
prebuilt web app from frontend/dist. Settings match start-imaging.ps1; anything set in the Space's
"Variables and secrets" wins over these defaults. Provider keys come only from the Space secrets.

Free accounts get Gradio Spaces only on ZeroGPU hardware. ZeroGPU stops a Space whose server does not report in at
startup with at least one `@spaces.GPU` function. NeuroTwin needs no GPU, so it declares one function that does nothing
and is never called, and sends the startup report through the `spaces` package just before the server starts.
Everything else runs on the CPU. Outside a ZeroGPU Space (or without the `spaces` package) both are skipped.
"""
import importlib
import os
import sys
from pathlib import Path

try:
    import spaces  # must come before anything that could start CUDA; NeuroTwin itself never does
    HAVE_SPACES = True
except ImportError:                          # running outside a Space without the package
    HAVE_SPACES = False

    class spaces:  # noqa: N801  (stand-in so the decorator below is a plain no-op)
        @staticmethod
        def GPU(fn):  # noqa: N802
            return fn

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

from app.main import create_app  # noqa: E402

# Kept at the start of the line, outside any block, where the ZeroGPU check looks for it.
@spaces.GPU
def no_gpu_needed():
    """Never called. Present only so the ZeroGPU startup check finds a GPU function."""
    return None


def report_to_zerogpu():
    """On a ZeroGPU Space only: send the startup report, as Gradio's own server start would. `spaces.zero.startup` exists in
    both the older `spaces` package preinstalled on ZeroGPU machines and newer ones (where it is kept for compatibility)."""
    if not HAVE_SPACES or str(os.environ.get("SPACES_ZERO_GPU", "")).lower() not in ("1", "t", "true"):
        return
    zero = importlib.import_module("spaces.zero")
    if hasattr(zero, "startup"):
        zero.startup()
    else:                                    # older layout: the same two steps the startup call makes
        importlib.import_module("spaces.zero.torch").pack()
        importlib.import_module("spaces.zero.client").startup_report()
    print("ZeroGPU startup report sent", flush=True)


if __name__ == "__main__":
    application = create_app()
    report_to_zerogpu()
    uvicorn.run(application, host="0.0.0.0", port=int(os.environ.get("PORT", 7860)),
                proxy_headers=True, forwarded_allow_ips="*", access_log=False)
