# Running a live analysis on your own scans

Agent Analysis compares two scans of one person taken about 12, 15 or 18 months apart. The hosted demo plays real runs that
were recorded earlier on OASIS-2 scans (**Watch recorded run**). To run the same pipeline live on a new pair, use a computer
that meets the requirements below.

Nothing here is a diagnosis or a prediction. Every report is a draft for clinical review.

## What you need

| Need | Detail |
|---|---|
| Two scans of one person | NIfTI (`.nii`, `.nii.gz`) or Analyze (`.hdr`/`.img`). 12, 15 or 18 months apart (1.5 months either side). The recorded gap must be known. DICOM is not enabled. |
| Computer | Linux or macOS, or Ubuntu under Windows (WSL). At least 2 CPU cores and 4 GB of memory. Measured on a 2-core machine with a 256 x 256 x 128 pair: alignment about 33 seconds, about 0.8 GB for the alignment process, a few seconds for the other steps. |
| Alignment package | `pip install -r backend/requirements-agent.txt` (antspyx). It does not install on Windows with Python 3.14; use WSL or Python 3.10 to 3.13 on Linux. |
| Segmentation | SynthSeg 1.0 run once on each scan, outside NeuroTwin. Steps are in `docs/AGENT_ANALYSIS_SEGMENTATION.md`. Without it, validation, alignment and quality review run, and the regional steps show as Unavailable. |
| Memory for SynthSeg | Run it on a separate machine or environment if memory is short; it is not part of the server. |

## Steps

1. Put the original scans under the imaging data folder (`backend/imaging_data/`). OASIS-2 pairs use `scripts/oasis2_extract.py`.
2. Run SynthSeg on both scans and import each result:
   `python scripts/agent_segmentation.py prepare MRI_ID` then SynthSeg, then `python scripts/agent_segmentation.py import MRI_ID SEG TOOL VERSION`.
3. Start the server and open Brain Analytics, then Agent Analysis. Choose the pair and press **Run Agent Analysis**. The Agent Activity
   panel opens and follows each step. A step the computer cannot run is shown as Unavailable with the reason.
4. When the run finishes the result is saved and appears under Saved analyses, where it can be watched again as a recording.

## What the hosted demo does instead

The hosted demo has no live computation. **Watch recorded run** replays the stored events of a real run at 10x speed (real time and
30x are available), labelled as a replay, then loads the results one section at a time. The recorded timings stay visible in the
timeline. **Show result now** skips to the stored result. **Run live** is switched off on a server that cannot run it, with the
reason shown.
