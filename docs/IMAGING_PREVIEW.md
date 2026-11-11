# Single-participant Brain Analytics preview

This is NeuroTwin's own local imaging page, using supplied FreeSurfer derivatives for OASIS-1 participant/visit `OAS1_0001_MR1`. It does not run a new reconstruction or prediction model. Dataset files stay in ignored local storage and are not bundled with the app or committed to git.

## Open the prepared preview

Run `start-imaging.ps1` from the project root. It starts the app on http://127.0.0.1:8001 and explicitly enables the local demo clinician (`demo-dr-layla`) for this research case. Open the clinician view, then **Brain Analytics** (or **تحليل صور الدماغ**). The imaging tools are currently an English research preview.

In demo mode every clinician demo account can open Brain Analytics, so anyone who enters through the landing page's clinical card can try the Images & 3D, Import & processing, Compare visits, Measurements and Source & quality tabs. Participant and family accounts never have access, and signed-out visitors are refused. Set `NEUROTWIN_IMAGING_OPEN=0` to return to the explicit list in `NEUROTWIN_IMAGING_USERS`. All clinician demo visitors share one demo identity, so they can see each other's native imports. Keep the demo off the public internet unless the data provider's terms allow serving the scans there.

## What works

### Native import and preparation

Brain Analytics now opens **Import & processing** by default. This path runs without FreeSurfer and does not load its legacy artifacts. It supports one original NIfTI `.nii`/`.nii.gz` volume or a matching Analyze `.hdr`/`.img` pair. The user confirms the intended participant and T1 acquisition. A convenience action imports the already-downloaded participant's first original raw acquisition from `oasis_cross-sectional_disc1.tar.gz`.

The native path preserves originals and SHA-256 hashes, records durable processing attempts, validates supported geometry and finite/intensity-variable data, and prepares a physically scaled 8-bit display preview. Singleton trailing dimensions are accepted; actual multi-volume time series are rejected. A source with an explicit NIfTI transform can be reoriented for display; an Analyze source without that transform is shown as **voxel axes**, with anatomical orientation unverified. Neither outcome constitutes anatomical QC.

One worker prepares native image arrays at a time per server process. Waiting jobs remain queued and cancellable. Progress shows actual stage states, failures preserve history, and retryable failures/cancelled attempts can create a new attempt. On server restart, interrupted attempts are marked failed and require explicit retry. This is a single-server prototype, not a distributed job queue; run one application worker against a database. Source-file size is capped at 80 MiB, expanded compressed volumes at 160 MiB, and processing at 32 million voxels.

Native previews are kept separate from imported masks, surfaces and statistics. Their downstream segmentation, measurement, agent and forecast stages remain blocked with explicit reasons. The final native preparation status is **awaiting review**, never a diagnosis or an accepted clinical result. Metadata and display-volume access require the configured research user and the importing account; imports/cancel/retry require CSRF protection.

Use `start-imaging.ps1` to install the optional imaging dependencies and start the local preview. Native originals and output buffers are in `backend/imaging_data/native/<scan-id>/`, with source files separated from per-attempt outputs. Metadata is in the new additive `native_scans` and `native_runs` tables. No existing clinical tables or records are rewritten.

### Legacy reference viewer

- Actual left/right pial, white and inflated meshes with preserved vertex annotations.
- Rotation, zoom, pan, hemisphere visibility, wireframe and transparency.
- Anatomical region colors, thickness maps with a 0–5+ mm color scale, and cortical picking.
- Axial/coronal/sagittal MRI panels with slice sliders, wheel navigation, zoom/fit and crosshairs.
- Linked MRI coordinates from cortical picking on non-inflated geometry.
- Segmentation overlays, adjustable MRI display level/window and region lookup.
- Right-side clipping and three MRI planes positioned in the same surface-RAS frame.
- Explore Inside: camera moves near the linked cursor; cortex becomes transparent and MRI planes appear. Scroll to change distance, right-drag to pan, and Reset to return to whole-brain inspection.
- 118 imported regional measurement rows, filtering, a region inspector and CSV export.
- Source/version/checksum information, QC-pending labels and protected artifact reads.

Inflated geometry is deliberately excluded from MRI alignment and cursor linking. Transparency may have normal rasterization ordering artifacts, and internal exploration uses MRI planes rather than full volumetric ray casting. Zoom cannot reveal anatomy below the scan's resolution. Internal regions are currently shown as volume-label overlays, not separate subcortical meshes.

## Prepare the case again on another machine

Install the ordinary backend requirements and optional `backend/requirements-imaging.txt`. Run from the project root:

```powershell
.\backend\.venv\Scripts\python.exe -m pip install -r backend/requirements-imaging.txt
.\backend\.venv\Scripts\python.exe backend/scripts/prepare_imaging.py --archive 'PATH\oasis_cs_freesurfer_disc1.tar.gz' --subject OAS1_0001_MR1
.\start-imaging.ps1
```

The script streams only the selected subject's allowed artifacts, verifies required files and geometry, records source hashes, preserves the native MRI/surface/statistics files, and prepares binary viewer assets. Existing prepared output is never overwritten; use a new `--output` root for a fresh preparation and set `NEUROTWIN_IMAGING_ROOT` to that parent root. The API intentionally serves only this one configured case in this increment.

Local layout:

```text
backend/imaging_data/OAS1_0001_MR1/
  source/       native MRI, meshes, annotations, statistics and processing log
  assets/       display volumes, binary meshes/labels/scalars and manifest
backend/imaging_data/verification/
                local browser screenshots; not source assets
```

The 8-bit working MRI is a display conversion of T1.mgz, not a new source scan. Original intensities remain preserved. Binary arrays are C-order, little-endian where multibyte; the manifest records the volume shape and coordinate transforms. Mesh positions remain in FreeSurfer surface RAS. No smoothing, decimation or vertex remapping is applied by this importer.

## Verification

- `cd frontend; npm run build` checks the TypeScript app and builds production assets.
- `cd backend; .\.venv\Scripts\python.exe -m pytest tests/test_imaging.py -q` checks authorization, access revocation, artifact allowlisting, private caching, missing case handling and audit logging.
- `frontend/scripts/check-imaging.cjs` exercises the prepared page against the running preview. Set `CHROME_PATH` if using an existing Chromium executable; otherwise install the browser expected by Playwright. Optional `IMAGING_BASE_URL` defaults to port 8001. Screenshots go to ignored local imaging storage.

The browser check covers case loading, 3D picking, surface/color switches, zoom, segmentation, slice selection, inside/reset controls, inflated alignment restrictions, measurement filtering/selection, version display, narrow/phone layouts and return navigation.

Local data verification also compared volume and segmentation buffers, six meshes and cortical statistics with native source files, and checked source SHA-256 hashes and volume/surface geometry. This verifies technical consistency, not independent anatomical QC or clinical performance.

## Remaining development

The processing direction has changed: new analysis will use the NeuroTwin-owned pipeline defined in [NATIVE_IMAGING_AND_AI_PLAN.md](NATIVE_IMAGING_AND_AI_PLAN.md), rather than running FreeSurfer. The current supplied derivatives retain their original provenance and are not native NeuroTwin outputs.

Native segmentation and surface reconstruction; editable voxel/ROI tools and reruns; reviewed QC persistence; longitudinal sessions; full volume rendering; additional modalities; Arabic imaging-tool translation; ordered live AI agents; and evaluated AI forecasts remain planned. Use `NATIVE_IMAGING_AND_AI_PLAN.md` for the current roadmap.
