# Deploying NeuroTwin to a free Hugging Face Space

The hosted app behaves like `start-imaging.ps1`: imaging is on for `dr.layla`, the demo people have six months of
synthetic history, and the AI and voice settings come from the same values as your `backend/.env`.

Free tier ("CPU basic"): 2 CPUs, 16 GB memory. The Space sleeps after about 48 hours without visitors and wakes on the
next visit. Its disk is not kept: the demo database is rebuilt on every restart, which is fine for a demo.

## Before you start

- **OASIS terms.** The Space contains de-identified OASIS-1 and OASIS-2 scans (about 600 MB), and files in a public
  Space can be downloaded. Confirm that your OASIS permission allows this public hosting.
- **Your API quota.** Anyone with the link can use the live AI features, charged to your Gemini and Meta keys.
  Keep the `*_DAILY_CALLS` limits low.

## Steps

1. **Create the Space.** Sign in at https://huggingface.co, choose *New Space*, enter a name (for example `neurotwin`),
   then pick SDK **Docker** with the **Blank** template, hardware **CPU basic (free)**, and visibility **Public**.

2. **Add your settings.** In the Space: *Settings → Variables and secrets*.
   - Add as **Secrets** (hidden): `GEMINI_API_KEY`, `META_API_KEY`.
   - Add as **Variables**, copying the values from `backend/.env`: `NEUROTWIN_AI_PROVIDER`,
     `NEUROTWIN_AGENTS_MODE`, `GEMINI_MODEL`, `NEUROTWIN_COMPANION`, `GEMINI_TTS_MODEL`, `GEMINI_TTS_VOICE`,
     `META_API_BASE_URL`, `META_MODEL`, `NEUROTWIN_AGENTS_SEND_IMAGES`, `NEUROTWIN_AI_DAILY_CALLS`,
     `NEUROTWIN_AGENTS_DAILY_CALLS`, `NEUROTWIN_STT_DAILY_CALLS`, `NEUROTWIN_TTS_DAILY_CALLS`,
     `NEUROTWIN_NLU_DAILY_CALLS`.
   - Already set in the Dockerfile, so you don't add them: imaging for `demo-dr-layla`, synthetic history,
     secure cookies, port 7860.

3. **Install the upload tool and sign in** (once). Create a *Write* token at https://huggingface.co/settings/tokens, then:

   ```powershell
   python -m pip install -U huggingface_hub
   hf auth login
   ```

4. **Build the upload folder.** This writes `output\hf-space` (about 670 MB). It contains no `.env` and no database.

   ```powershell
   .\deploy\huggingface\prepare-space.ps1
   ```

5. **Upload.** Replace `YOUR-NAME/neurotwin` with your Space.

   ```powershell
   hf upload YOUR-NAME/neurotwin output\hf-space . --repo-type space
   ```

   The Space then builds; this takes about 5–10 minutes. Watch the *Logs* tab until it says
   `Uvicorn running on http://0.0.0.0:7860`.

6. **Open the direct address:** `https://YOUR-NAME-neurotwin.hf.space`. Share this link, not the
   `huggingface.co/spaces/...` page. The session cookie is `SameSite=Strict`, so signing in does not stick inside the
   page's embedded frame. It works on the direct address.

To update the app later, run steps 4 and 5 again.

## Testing locally first

```powershell
docker build -t neurotwin-space output\hf-space
docker run --rm -p 7860:7860 --env-file backend\.env neurotwin-space
```

Then open http://localhost:7860. `--env-file` passes your keys only to the local container; they are never stored in
the image.

## What is uploaded

| Included | Left out |
|---|---|
| Backend and frontend code, Dockerfile, licences | `.env`, databases, `.claude`, `docs/`, backend tests and evaluation sets |
| `imaging_data/OAS1_0001_MR1/assets` (3D case) | `imaging_data/OAS1_0001_MR1/source` |
| `imaging_data/agent_analysis` (recorded runs) | `imaging_data/native` (local test imports) |
| `imaging_data/oasis2` manifest, extracted scans, segmentations | `oasis2/segmentation_inputs`, `imaging_data/verification` |

Live alignment for new agent runs needs `antspyx`, which is not installed (the same as `start-imaging.ps1`). Saved
runs replay normally.
