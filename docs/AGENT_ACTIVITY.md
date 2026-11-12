# Agent Activity panel

Status: built and verified on real OASIS-2 scans (three saved pairs, one live run per behaviour below). It shows what the
Agent Analysis pipeline really did. It does not connect, start or simulate any AI agent.

## What the user sees

- **Compact card** in Brain Analytics, Agent Analysis tab, under "Saved analyses" and above the scan-pair picker. It holds the
  title, a Live / Historical record / Saved result badge, the running step and its one-line action, finished / remaining / not-run
  counts, a segment bar (no percentage: none can be measured reliably), Expand, and a fold button. It sits in the page flow, so it
  never covers the pair picker, the viewer or the results.
- **Expanded view** (a modal panel): the workflow graph with pan, zoom, Fit, Reset, "Follow active step" and a minimap; a step
  details panel; a timeline with start times and durations; an event list. Minimize or Esc returns to the card and puts focus
  back on Expand. Position, zoom and the selected step are kept.
- Three kinds of node are drawn differently and labelled in words: **Tool** (ordinary software step), **AI agent**, and **Human
  review**. Not built means dashed and labelled Unavailable.

## Saved results and live runs

Each saved analysis has two buttons. **View saved result** opens the stored result at once, labelled "Historical record"; nothing is
recomputed and the live panel stays closed. **Run live** starts a new real analysis of the same two scans. The Agent Activity panel
opens by itself with "Follow active step" on, shows each step as it runs, and the results appear only as each step finishes. A
step this server cannot run is shown as Unavailable with the reason. Where alignment is not installed (for example on Windows
with Python 3.14), a live run stops at alignment and says so. The "Run Agent Analysis" button behaves the same way. Replay is
labelled "Replay a recorded run (no processing)".

## What is real

| Node | Kind | Status today |
|---|---|---|
| Scan-pair selection and identity validation | Tool | runs |
| Technical scan checks | Tool | runs |
| Image preparation and alignment | Tool (ANTsPy rigid) | runs where antspyx is installed, else Unavailable |
| Brain extraction | Tool | **Unavailable**: no brain-extraction tool is installed |
| Quality review | Tool (rules) | runs |
| Segmentation import | Tool (SynthSeg output imported) | runs when segmentations are imported, else Unavailable |
| Regional measurements and comparison | Tool | runs after segmentation |
| Findings review | Tool (rules) | runs after measurements |
| Draft report | Tool (template, no model) | runs after the findings review |
| Evidence explanation, Report review | AI agent | **Unavailable**: planned, not connected |
| Clinician review | Human gate | **Awaiting review** once a report exists; no approval is recorded |

A finished run never turns the planned agents or brain extraction green.

## How the events work

- `agent_analysis._write` appends events to `agent_analysis/<run>/events.jsonl` through `agent_activity.sync`, by comparing each
  stage's status with the last one logged. A stage that did not run has no running or completed event.
- Each event has `seq`, `id` (`<run>:<seq>`), `run_id`, `node`, `type` (status, run, tool call, hand-off), `ts`, `status`
  and a summary. Statuses: waiting, queued, running, completed, completed with warnings, failed, blocked, unavailable, cancelled,
  skipped, awaiting review.
- `GET /api/imaging/agent/runs/{id}/activity?after=<seq>` returns the nodes and only the newer events. The browser polls it every
  second while a run is live and resumes from the last `seq` after a dropped connection, so nothing is lost or repeated. The log
  is written before the run record, so a client that sees a finished state has every event.
- `GET /api/imaging/agent/workflow` gives the graph before any run, so the idle card shows what is built and what this server can run.
- Retries start a new run (`parent_run_id`); no branch is drawn unless one exists. Nothing in the pipeline runs in parallel today.
- Saved runs show their recorded events as a **historical record**. "Replay recorded events" steps through the stored log and
  runs nothing. A run saved before event recording existed has no log: it shows its stored final state and says so.
- Events carry stage names, statuses, tool names and versions and short summaries. They carry no prompts, model reasoning or credentials.

## A fix found while verifying

ANTs holds Python's global lock for its whole call. In the first build, the live panel and Cancel stalled for the ~40 s of the
registration, and on a shared server it would have stalled everyone. Registration and label warping now run in a separate
process (`app/ants_worker.py`), so the server keeps answering, and Cancel terminates that process.

## Tested

- `backend/tests/test_agent_activity.py` (11 tests) and 2 new worker tests: event order and ids, idempotent sync, cursor,
  half-written lines, blocked and cancelled runs, planned agents never completed, unavailable stages never completed, times and
  outputs on a real completed run, legacy runs without a log, endpoint access control. Full suite: 237 passed.
- In a browser on real scans (Chromium, 1440 wide): idle card; live run with the running step named; expand, zoom, select a
  step, minimize while running (the run continued), restore (view and selection kept), focus return; blocked network for a few
  seconds (banner shown, then cleared, 40 events on the client and 40 on the server, all unique); replay to the middle of a
  run (later steps still Waiting); arrow-key panning; Cancel (cancelled, later steps Skipped); a saved run without a log; reduced motion
  (no animations or transitions); layout direction flipped to RTL.

## Limits

- The Brain Analytics workspace is English only today. The panel uses logical CSS properties and flips with the page direction
  (checked), but no Arabic wording was written for it; that needs a native speaker's review.
- The graph keeps left-to-right order in every language.
- The workspace itself is desktop-first: below about 600 px the existing page overflows sideways and the clinician layout hides the
  Brain Analytics button. The expanded panel stacks and fits a phone width; the compact card inherits the page's width.
- A server restart during a run leaves that run "running"; there is no orphan cleanup yet.
- Polling, not push: updates arrive within about a second.
- Event times are server clock times. Unit and browser tests do not replace testing with assistive technology on real devices.
