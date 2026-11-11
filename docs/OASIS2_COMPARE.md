# Compare visits (OASIS-2), Level 1

Shows two visits of the same person side by side in Brain Analytics, under **Compare visits**. Open to every clinician demo account in demo mode (see IMAGING_PREVIEW.md); participant and family accounts have no access. Observed images only: no registration, no segmentation, no prediction.

## Prepare the data (once)

Everything stays in `backend/imaging_data/oasis2/`, which git ignores.

1. Build the manifest from the demographic table and the archive listings (see `scripts/oasis2_manifest.py`). Listings come from `tar -tvzf <archive> > list_partN.txt`; both GNU and Windows (UTF-16) listings are read.
2. Extract the subjects you want to compare. Subjects near the start of an archive are quick:

   ```
   python scripts/oasis2_extract.py <path-to>/OAS2_RAW_PART1.tar.gz OAS2_0001 OAS2_0002 OAS2_0004 OAS2_0005
   ```

   Only `mpr-1` of each visit is written, into `imaging_data/oasis2/extracted/`. Pass `--scans mpr-1 mpr-2` for repeats.
3. Start with `start-imaging.ps1` and open Brain Analytics, then **Compare visits**.

A person appears in the list only when at least two of their visits are extracted.

## What you see and what it means

- Elapsed time comes from the table's `MR Delay` column (days). Some gaps are shorter than a year.
- Age, MMSE, CDR and nWBV under each image are **imported** from the OASIS table.
- The views are along **voxel axes**. These raw files are Analyze format with no verified orientation, so the app does not call any view axial, coronal or sagittal. When the first axis was labelled "axial" during testing, the image was a side-on view, which is why neutral names are used.
- The two visits are **not registered**. The same slice number can show different anatomy, so differences between panels are not evidence of change.
- Voxels that are not cubic are drawn in true proportion.
- **Trend over visits.** For a person with three or more recorded visits, imported nWBV is plotted against years since the first visit with the average change per year. It is descriptive only: no uncertainty range, no normal/abnormal call, no forecast. With fewer than three visits the page says there are not enough visits.
- Each visit has several repeat scans of the same session. They are not extra time points.

## Not included

Registration, regional volumes and any statement of change or forecast. Those need a validated method (stages 4 and 8) and are listed in `IMAGING_WORKFLOW_STAGES_1_10.md`.
