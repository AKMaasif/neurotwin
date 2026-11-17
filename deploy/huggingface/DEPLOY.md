# Deploying NeuroTwin to a free Hugging Face Space

Docker Spaces are a paid option, so this uses the free **Gradio** Space type. A Gradio Space runs `python app.py`;
here `app.py` starts NeuroTwin's own server instead of a Gradio interface, and serves the web app, which is built on
your PC by `prepare-space.ps1`.

The hosted app behaves like `start-imaging.ps1`: imaging is on for `dr.layla`, the demo people have six months of
synthetic history, and the AI settings come from the same values as your `backend/.env`.

On a free account, Gradio Spaces run on **ZeroGPU** hardware (CPU basic needs PRO). NeuroTwin needs no GPU: `app.py`
declares one GPU function that is never called, so ZeroGPU's startup check passes, and everything runs on the CPU. The Space sleeps after about 48 hours without visitors and wakes on the
next visit. Its disk is not kept: the demo database is rebuilt on every restart, which is fine for a demo.

## Before you start

- **OASIS terms.** The Space contains de-identified OASIS-1 and OASIS-2 scans (about 600 MB), and files in a public
  Space can be downloaded. Confirm that your OASIS permission allows this public hosting.
- **Your API quota.** Anyone with the link can use the live AI features, charged to your Gemini and Meta keys.
  Keep the `*_DAILY_CALLS` limits low (for example 50).

## Steps

1. **Create the Space.** At https://huggingface.co/new-space: name `neurotwin`, licence MIT, SDK **Gradio**
   with the **Blank** template, hardware **ZeroGPU (free)**, the only free choice for Gradio, visibility **Public**.

2. **Add your settings.** In the Space: *Settings → Variables and secrets*.
   - **Secrets** (hidden): `GEMINI_API_KEY`, `META_API_KEY`.
   - **Variables**, with the values from `backend/.env`: `NEUROTWIN_AI_PROVIDER`, `NEUROTWIN_AGENTS_MODE`,
     `GEMINI_MODEL`, `META_API_BASE_URL`, `META_MODEL`, `NEUROTWIN_AGENTS_SEND_IMAGES`,
     `NEUROTWIN_AI_DAILY_CALLS`, `NEUROTWIN_AGENTS_DAILY_CALLS`, `NEUROTWIN_NLU_DAILY_CALLS`.
   - Already set by `app.py`, so you don't add them: imaging for `demo-dr-layla`, synthetic history, secure cookies.

3. **Install the upload tool and sign in** (once). Create a *Write* token at https://huggingface.co/settings/tokens, then:

   ```powershell
   python -m pip install -U huggingface_hub
   hf auth login
   ```

4. **Build the upload folder.** This builds the web app and writes `output\hf-space` (about 670 MB). It contains no
   `.env` and no database.

   ```powershell
   .\deploy\huggingface\prepare-space.ps1
   ```

5. **Upload.** Replace `YOUR-NAME` with your Hugging Face username. The folder's `README.md` replaces the Space's
   starter one and carries its settings.

   ```powershell
   hf upload YOUR-NAME/neurotwin output\hf-space . --repo-type space
   ```

   The Space then installs its packages and starts, which takes about 5–10 minutes. Watch the *Logs* tab until it
   says `Uvicorn running on http://0.0.0.0:7860`.

6. **Open the direct address:** `https://YOUR-NAME-neurotwin.hf.space`. Share this link, not the
   `huggingface.co/spaces/...` page. The session cookie is `SameSite=Strict`, so signing in does not stick inside the
   page's embedded frame. It works on the direct address.

To update the app later, run steps 4 and 5 again.

## What is uploaded

| Included | Left out |
|---|---|
| Backend code, built web app (`frontend/dist`), `app.py`, `requirements.txt`, licences | `.env`, databases, `.claude`, `docs/`, backend tests and evaluation sets, Dockerfile |
| `imaging_data/OAS1_0001_MR1/assets` (3D case) | `imaging_data/OAS1_0001_MR1/source` |
| `imaging_data/agent_analysis` (recorded runs) | `imaging_data/native` (local test imports) |
| `imaging_data/oasis2` manifest, extracted scans, segmentations | `oasis2/segmentation_inputs`, `imaging_data/verification` |

Live alignment for new agent runs needs `antspyx`, which is not installed (the same as `start-imaging.ps1`). Saved
runs replay normally.

## Other hosts

The `Dockerfile` in the repository root runs the same app as one container on any Docker host (including a paid
Docker Space): `docker build -t neurotwin .` then
`docker run -p 7860:7860 --env-file backend\.env neurotwin`. Imaging data is included only if `backend\imaging_data`
is present when you build.
