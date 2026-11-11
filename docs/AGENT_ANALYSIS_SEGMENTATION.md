# Producing the segmentations for Agent Analysis

NeuroTwin does not segment brains itself. It imports the output of a validated, free tool and records which tool and version made
it. We use **SynthSeg** (Apache-2.0, weights free on GitHub). It labels about 32 structures: cortex, white matter, hippocampus,
amygdala, ventricles, thalamus, caudate and others.

Both scans of a pair must come from the **same tool and version**; otherwise the run stops with a clear message.

## Steps on your PC (from `D:\NeuroTwin\backend`)

1. Write single-volume copies of the scans (originals are untouched):
   `python scripts/agent_segmentation.py prepare OAS2_0001_MR1 OAS2_0001_MR2`
   Files appear in `imaging_data/oasis2/segmentation_inputs/`. They keep the scan's own orientation from its header; the tool needs
   it, and a segmentation of a sideways-written head comes out nearly empty. Check the printed axes (for these scans `PSL`-style codes).
2. Run SynthSeg on each file. Either option is fine:
   - SynthSeg repo `BBillot/SynthSeg` (Python 3.8 environment from its `requirements_python3.8.txt`):
     `python scripts/commands/SynthSeg_predict.py --i OAS2_0001_MR1.nii.gz --o OAS2_0001_MR1_seg.nii.gz --v1 --vol OAS2_0001_MR1.csv`
   - FreeSurfer 7.3 or newer (SynthSeg 2.0): `mri_synthseg --i OAS2_0001_MR1.nii.gz --o OAS2_0001_MR1_seg.nii.gz --vol OAS2_0001_MR1.csv`
     (Windows users: through WSL.)
3. Import each result, naming the tool and version exactly (use the same text for both scans):
   `python scripts/agent_segmentation.py import OAS2_0001_MR1 path\to\OAS2_0001_MR1_seg.nii.gz SynthSeg 1.0`
   The tool may write a finer grid (SynthSeg 1.0 uses 1 mm cubes). That is fine: the import only checks that the scan's field of view
   lies inside the segmentation's. Volumes are counted on the tool's own grid; the scan grid is used only for display.
4. Sanity check before trusting a result: total brain tissue should be roughly 1,000,000 to 1,400,000 mm³ (the volumes CSV).

Do this for the 12-, 15- and 18-month pairs you want in the demo. Candidates in the extracted data: OAS2_0001 (15 mo) and
OAS2_0004 (18 mo). A 12-month subject (for example OAS2_0071) needs extracting first.

## What the app does with it

Region volumes are voxel counts of each scan's own segmentation, so alignment does not alter them. The later labels are carried
onto the earlier anatomy with the stored rigid transform and nearest-label sampling for the overlays only. With no repeat-scan
spread yet, every regional difference is marked **uncertain**. SynthSeg 2.0 also writes a CSF label (24) that the app ignores and
says so.

## For the deployed demo

Run these steps once, commit nothing from `imaging_data/`, and place the finished `segmentations/` and run folders on the server, or
rebuild them there. The site then shows real outputs with the tool and version on record.
