// No answers or scores in browser storage. Every panel is bound to actor + patient + epoch.
let assessmentCleanup = null;
function renderAssessmentPanel() {
  if (
    !S.data.patient.synthetic ||
    !S.data.scopes.includes("assessment") ||
    !["participant", "clinician"].includes(S.user.role)
  )
    return "";
  return `<section class="card assessment-panel" aria-label="Research activities"><p class="eyebrow">OPTIONAL RESEARCH ACTIVITIES</p><h2>One activity at a time</h2><p>This SATURN-derived adaptation is for synthetic research only. Clinical approval has not been obtained. It does not diagnose dementia.</p><button type="button" data-assessment-refresh>Load activities</button><p data-assessment-status role="status" aria-live="polite"></p><div data-assessment-content></div></section>`;
}

function bindAssessments() {
  if (assessmentCleanup) assessmentCleanup();
  const panel = document.querySelector(".assessment-panel");
  if (!panel) return;
  const pid = S.pid,
    actor = S.user.id,
    epoch = S.workspaceEpoch;
  const current = () =>
    panel.isConnected && S.pid === pid && S.user?.id === actor && S.workspaceEpoch === epoch;
  const path = `/patients/${encodeURIComponent(pid)}/assessments`;
  const content = panel.querySelector("[data-assessment-content]"),
    status = panel.querySelector("[data-assessment-status]");
  let data = null,
    busy = false,
    running = null,
    timer = null,
    hidden = false;
  const stopTimer = () => {
    if (timer) clearInterval(timer);
    timer = null;
  };
  assessmentCleanup = () => {
    stopTimer();
    document.removeEventListener("visibilitychange", visibility);
    running = null;
    S.assessmentActive = false;
  };
  async function run(fn) {
    if (!current() || busy) return;
    busy = true;
    S.assessmentBusy = true;
    panel.setAttribute("aria-busy", "true");
    panel.querySelectorAll("button").forEach((b) => (b.disabled = true));
    status.textContent = "Saving or refreshing activities…";
    try {
      await fn();
      if (current()) status.textContent = "Activities are up to date.";
    } catch (error) {
      if (current()) {
        if ([401, 403].includes(error.status)) {
          data = null;
          content.replaceChildren();
          stopTimer();
          running = null;
        }
        status.textContent = `${error.message}. Refresh activities to check whether a save succeeded before continuing.`;
      }
    } finally {
      busy = false;
      if (S.pid === pid && S.user?.id === actor && S.workspaceEpoch === epoch)
        S.assessmentBusy = false;
      if (current()) {
        panel.removeAttribute("aria-busy");
        panel.querySelectorAll("button").forEach((b) => (b.disabled = b.dataset.locked === "true"));
      }
    }
  }
  const load = async () => {
    const result = await api(path);
    if (!current()) return;
    data = result;
    draw();
  };
  const command = async (row, route, extra = {}) => {
    const result = await api(`${path}/${encodeURIComponent(row.id)}/${route}`, "POST", {
      command_id: crypto.randomUUID(),
      expected_version: row.version,
      ...extra,
    });
    if (!current()) return null;
    const index = data.sessions.findIndex((r) => r.id === row.id);
    data.sessions[index] = result;
    return result;
  };
  function visibility() {
    if (document.hidden && running && current()) {
      hidden = true;
      stopTimer();
      status.textContent =
        "The activity was interrupted when this page was hidden. Stop this session; do not restart the activity.";
    }
  }
  document.addEventListener("visibilitychange", visibility);
  function draw() {
    if (!current()) return;
    stopTimer();
    const clinical = S.user.role === "clinician";
    S.assessmentActive = !clinical && data.sessions.some((row) => row.status === "active");
    const empty = document.querySelector(".check-availability");
    if (empty) empty.hidden = data.sessions.length > 0;
    const explanation = document.querySelector(".check-explanation");
    if (explanation) explanation.hidden = data.sessions.length > 0;
    panel.querySelector("[data-assessment-refresh]").textContent = "Refresh activities";
    content.innerHTML = `${clinical ? assignmentForm() : ""}${data.sessions.length ? data.sessions.map((row) => sessionCard(row, clinical)).join("") : "<p>No research assessment has been assigned.</p>"}`;
    const assign = content.querySelector("[data-assessment-assign]");
    if (assign)
      assign.onsubmit = (e) => {
        e.preventDefault();
        if (!assign.reportValidity()) return;
        const form = new FormData(assign);
        run(async () => {
          await api(path, "POST", {
            command_id: crypto.randomUUID(),
            protocol_version: data.protocol.version,
            timezone: form.get("timezone"),
            location: form.get("location"),
            acknowledge_adaptation: true,
          });
          await load();
        });
      };
    for (const article of content.querySelectorAll("[data-assessment-session]")) {
      const row = data.sessions.find((r) => r.id === article.dataset.assessmentSession),
        p = row.payload;
      const consent = article.querySelector("[data-assessment-consent]");
      if (consent)
        consent.onsubmit = (e) => {
          e.preventDefault();
          if (!consent.reportValidity()) return;
          run(async () => {
            await command(row, "consent", {
              consent_version: p.protocol.consent_version,
              understands_english: true,
              comfortable_reading: true,
              mode: consent.elements.mode.value,
              device_class: consent.elements.device_class.value,
            });
            draw();
          });
        };
      const begin = article.querySelector("[data-assessment-begin]");
      if (begin)
        begin.onclick = () =>
          run(async () => {
            const result = await command(row, "begin");
            if (!result || result.status !== "active") {
              draw();
              return;
            }
            running = {
              id: row.id,
              step: result.payload.current_step.id,
              start: performance.now(),
            };
            hidden = false;
            draw();
          });
      article.querySelectorAll("[data-assessment-action]").forEach(
        (b) =>
          (b.onclick = () => {
            const action = b.dataset.assessmentAction;
            if (
              action === "withdraw" &&
              !confirm(
                "Withdraw consent? Capture stops and results cannot be used. Existing records and audit history are retained.",
              )
            )
              return;
            run(async () => {
              await command(row, "transition", { action });
              running = null;
              draw();
            });
          }),
      );
      const finish = article.querySelector("[data-assessment-finish]");
      if (finish)
        finish.onsubmit = (e) => {
          e.preventDefault();
          if (!finish.reportValidity()) return;
          run(async () => {
            await command(row, "transition", {
              action: "complete",
              quality: finish.elements.quality.value,
            });
            running = null;
            draw();
          });
        };
      const review = article.querySelector("[data-assessment-review]");
      if (review)
        review.onsubmit = (e) => {
          e.preventDefault();
          if (!review.reportValidity()) return;
          const points = {};
          review
            .querySelectorAll("[data-item-points]")
            .forEach(
              (input) =>
                (points[input.dataset.itemPoints] =
                  input.value === "" ? null : Number(input.value)),
            );
          run(async () => {
            await command(row, "review", {
              outcome: review.elements.outcome.value,
              rationale: review.elements.rationale.value,
              participant_note: review.elements.participant_note.value,
              item_points: points,
              checked_evidence: true,
            });
            draw();
          });
        };
      if (
        !clinical &&
        row.status === "active" &&
        p.step_started_at &&
        running?.id === row.id &&
        running.step === p.current_step?.id
      )
        bindActivity(article, row);
    }
  }
  function assignmentForm() {
    const open = data.sessions.some((r) =>
      ["awaiting_consent", "active", "awaiting_review"].includes(r.status),
    );
    return open
      ? "<p>A session already awaits participation or review. Finish, cancel or review it before assigning another.</p>"
      : `<details><summary>Assign research activities</summary><form data-assessment-assign><p>English-only adaptation. Review suitability, vision, motor access and ability to consent. A synthetic clinician account does not establish clinical approval.</p><label>Session timezone<input name="timezone" value="Asia/Dubai" required maxlength="60"></label><label>Current state or emirate for orientation<input name="location" required minlength="2" maxlength="80" placeholder="For example, Dubai"></label><label class="assessment-check"><input type="checkbox" required>I understand this is an unvalidated adaptation, not an approved clinical instrument.</label><button>Assign research activities</button></form></details>`;
  }
  function sessionCard(row, clinical) {
    const p = row.payload,
      progress = p.progress,
      active = row.status === "active";
    let body = `<h3>${esc({ awaiting_consent: "Your choice to take part", active: "Research activities", awaiting_review: "Waiting for care-team review", interrupted: "Session stopped", reviewed: "Care-team review recorded", cancelled: "Session cancelled", withdrawn: "Consent withdrawn" }[row.status] || row.status)}</h3><p class="muted">${esc(new Date(row.created_at).toLocaleString())} · revision ${row.version} · ${esc(p.protocol.version)}</p>`;
    if (clinical) {
      body += `<p>Source: ${esc(p.protocol.source_version)} · ${esc(p.protocol.license)}. Clinical approval: not obtained.</p>`;
      if (p.score) {
        body += `<p><strong>Provisional research total: ${p.score.total ?? "Not calculated — missing evidence"}${p.score.total !== null ? " / 30" : ""}</strong></p><p>No diagnosis, normative comparison or automated referral.</p><details><summary>Captured evidence and administration metadata</summary><pre>${esc(JSON.stringify({ consent: p.consent, reference: p.reference, quality: p.quality, responses: p.responses }, null, 2))}</pre></details>`;
        if (["awaiting_review", "interrupted"].includes(row.status)) body += reviewForm(p);
      }
      if (p.review)
        body += `<p>Reviewer ${esc(p.review.actor)} · ${esc(p.review.outcome)} · research total ${p.review.total ?? "unavailable"}</p><p>${esc(p.review.rationale)}</p>`;
      if (row.status === "awaiting_consent")
        body += '<button type="button" data-assessment-action="cancel">Cancel assignment</button>';
    } else {
      if (row.status === "awaiting_consent")
        body += `<p>${esc(p.protocol.consent_text)}</p><form data-assessment-consent><label class="assessment-check"><input type="checkbox" required>I understand and choose to take part.</label><label class="assessment-check"><input type="checkbox" required>I understand English and can comfortably read these instructions.</label><label>How will you take part?<select name="mode" required><option value="">Choose</option><option value="self">By myself</option><option value="assisted">With assistance — results flagged</option><option value="video">During a video session — results flagged</option></select></label><label>Your device<select name="device_class" required><option value="">Choose</option><option value="phone">Phone</option><option value="tablet">Tablet</option><option value="desktop">Computer</option></select></label><button>Agree and start research activities</button></form><button type="button" data-assessment-action="cancel">Decline activities</button>`;
      if (active) {
        body += `<p>Activity ${Math.min(progress.completed + 1, progress.total)} of ${progress.total}. You may skip or stop. No answer coaching is provided.</p><progress max="${progress.total}" value="${progress.completed}" aria-label="Activities completed"></progress>`;
        if (p.expired)
          body +=
            '<p role="alert">The 15-minute session limit has passed. Stop this session and ask the care team to review it.</p>';
        else if (p.current_step) {
          body += `<h4 tabindex="-1" data-activity-heading>${esc(p.current_step.prompt)}</h4>`;
          if (!p.step_started_at)
            body += '<button type="button" data-assessment-begin>Begin this activity</button>';
          else if (running?.id !== row.id || running.step !== p.current_step.id || hidden)
            body +=
              '<p role="alert">This activity was interrupted or refreshed. It cannot be replayed. Please stop this session.</p>';
          else body += "<div data-activity></div>";
        } else
          body +=
            '<form data-assessment-finish><label>Did anything make these activities difficult?<select name="quality" required><option value="">Choose</option><option value="usable">No difficulty to report</option><option value="poor">Yes — please review the difficulties</option></select></label><button>Finish and send for review</button></form>';
        body +=
          '<button type="button" data-assessment-action="interrupt">Stop this session</button>';
      }
      if (p.review_note) body += `<h4>From your care team</h4><p>${esc(p.review_note)}</p>`;
      if (["active", "awaiting_review", "interrupted", "reviewed"].includes(row.status))
        body += '<button type="button" data-assessment-action="withdraw">Withdraw consent</button>';
    }
    if (row.status === "withdrawn")
      body +=
        "<p>No further capture or result use is permitted. Existing records and audit history are retained.</p>";
    return `<article class="assessment-session" data-assessment-session="${esc(row.id)}">${body}</article>`;
  }
  function reviewForm(p) {
    return `<form data-assessment-review><h4>Independent evidence review</h4><p>Review all 20 items. Missing evidence stays missing. Assisted, interrupted or poor-quality sessions must be invalidated. Any changed points require an explanation below.</p>${p.score.items.map((i) => `<div class="assessment-review-item"><label>${esc(i.id)} (maximum ${i.maximum})<input type="number" data-item-points="${esc(i.id)}" min="0" max="${i.maximum}" step="1" ${i.points === null ? 'disabled aria-label="No evidence; unscored"' : `value="${i.points}" required`}></label><label class="assessment-check"><input type="checkbox" required>I checked this item's evidence.</label></div>`).join("")}<label>Review outcome<select name="outcome" required><option value="">Choose</option><option value="reviewed_research">Reviewed research result — not clinical approval</option><option value="invalid">Invalid or unsuitable evidence</option></select></label><label>Review rationale and reasons for point changes<textarea name="rationale" required minlength="12" maxlength="2000"></textarea></label><label>Plain-language note for the participant (no diagnosis)<textarea name="participant_note" required minlength="12" maxlength="500"></textarea></label><label class="assessment-check"><input type="checkbox" required>I reviewed administration conditions and the raw evidence. This does not validate the adapted instrument.</label><button>Save attributed review</button></form>`;
  }
  function bindActivity(article, row) {
    const step = row.payload.current_step,
      host = article.querySelector("[data-activity]");
    if (!host) return;
    let values = [],
      attempts = [],
      corrected = false,
      trial = 0;
    host.innerHTML = `${step.image ? `<p>Six choices are shown below the large drawing. Select their numbers using the buttons.</p><a href="${esc(step.image)}" target="_blank" rel="noopener">Open full-size drawing (interrupts this activity)</a><img class="assessment-stimulus" src="${esc(step.image)}" alt="Visual matching: a large drawing and six smaller choices, numbered left to right across the top row then the bottom row.">` : ""}<div data-activity-controls></div><p data-activity-feedback role="status"></p><form data-activity-save><label>Any difficulty with this activity?<select name="difficulty"><option value="none">None</option><option value="vision">Seeing the material or colors</option><option value="hearing">Hearing</option><option value="motor">Using the controls</option><option value="understanding">Understanding instructions</option><option value="other">Another difficulty</option></select></label><button type="submit" data-answer-save>Save answer and continue</button><button type="button" data-answer-skip>Skip — leave unscored</button></form>`;
    const controls = host.querySelector("[data-activity-controls]"),
      feedback = host.querySelector("[data-activity-feedback]"),
      save = host.querySelector("[data-answer-save]");
    if (["choice", "trail"].includes(step.kind)) {
      controls.innerHTML = `<div class="assessment-choices ${step.kind === "trail" ? "assessment-trail" : ""}" role="group" aria-label="Answer choices">${step.options.map((v) => `<button type="button" data-choice="${esc(v)}" aria-pressed="false">${esc(v)}</button>`).join("")}</div>`;
      controls.querySelectorAll("[data-choice]").forEach(
        (b) =>
          (b.onclick = () => {
            const v = b.dataset.choice;
            if (step.kind === "trail") {
              values.push(v);
              b.disabled = true;
              b.dataset.locked = "true";
            } else if (values.includes(v)) {
              values = values.filter((x) => x !== v);
              corrected = true;
            } else {
              if (values.length >= (step.count || 1)) {
                corrected = true;
                values = values.slice(1);
              }
              values.push(v);
            }
            controls
              .querySelectorAll("[data-choice]")
              .forEach((button) =>
                button.setAttribute("aria-pressed", String(values.includes(button.dataset.choice))),
              );
            feedback.textContent =
              step.kind === "trail"
                ? `Your sequence: ${values.join(" → ")}`
                : `${values.length} selected of ${step.count || 1}.`;
          }),
      );
    } else if (["text", "number"].includes(step.kind)) {
      controls.innerHTML = `<label>Your answer<input data-answer-input ${step.kind === "number" ? 'inputmode="numeric" pattern="[0-9]+"' : ""} maxlength="100" autocomplete="off" required></label>`;
      let prior = "";
      controls.querySelector("input").oninput = (e) => {
        if (e.target.value.length < prior.length) corrected = true;
        prior = e.target.value;
      };
    } else if (step.kind === "learning") {
      controls.innerHTML =
        '<p class="assessment-word" data-memory-word aria-live="off">Ready…</p><p>Watch the words until the presentation finishes.</p>';
      save.disabled = true;
      save.dataset.locked = "true";
      timer = setInterval(() => {
        if (!current() || !host.isConnected || hidden) {
          stopTimer();
          return;
        }
        const elapsed = performance.now() - running.start,
          i = Math.floor(elapsed / 3000),
          visible = elapsed % 3000 < 2000;
        controls.querySelector("[data-memory-word]").textContent =
          i < 5 ? (visible ? step.words[i] : "·") : "Presentation finished";
        if (elapsed >= 15000) {
          values = ["done"];
          save.disabled = false;
          delete save.dataset.locked;
          stopTimer();
        }
      }, 50);
    } else if (step.kind === "stroop") {
      function colorTrial() {
        if (trial === step.trials.length) {
          values = ["done"];
          controls.innerHTML = "<p>Color activity finished.</p>";
          return;
        }
        attempts[trial] = [];
        const t = step.trials[trial];
        controls.innerHTML = `<p>${trial < 3 ? "Practice" : "Color trial"} ${trial + 1} of 15</p><p class="assessment-word" style="color:${{ red: "#d7191c", green: "#16783b", blue: "#1555d6" }[t.color]}">${esc(t.word)}</p><div class="assessment-choices" role="group" aria-label="Ink color">${["red", "green", "blue"].map((c) => `<button type="button" data-color="${c}">${c}</button>`).join("")}</div>`;
        controls.querySelectorAll("[data-color]").forEach(
          (b) =>
            (b.onclick = () => {
              attempts[trial].push(b.dataset.color);
              if (b.dataset.color === t.color) {
                trial++;
                feedback.textContent = "";
                colorTrial();
              } else if (attempts[trial].length >= 60) {
                feedback.textContent = "Please skip this activity or stop the session.";
                controls.querySelectorAll("button").forEach((btn) => (btn.disabled = true));
              } else feedback.textContent = "Try another ink color, or skip this activity.";
            }),
        );
      }
      colorTrial();
    } else {
      values = ["done"];
      controls.innerHTML = "<p>Choose Continue when you have read the phrase.</p>";
      save.textContent = "Continue";
    }
    const submit = (skip) => {
      if (hidden) {
        status.textContent = "The activity was interrupted. Stop this session.";
        return;
      }
      const input = controls.querySelector("[data-answer-input]");
      if (!skip && input) {
        if (!input.reportValidity()) return;
        values = [input.value.trim()];
      }
      if (!skip && !values.length) {
        feedback.textContent = "Choose an answer or use Skip.";
        return;
      }
      if (!skip && step.kind === "learning" && performance.now() - running.start < 15000) return;
      run(async () => {
        await command(row, "answer", {
          step_id: step.id,
          values: skip ? [] : values,
          attempts: skip ? [] : attempts,
          client_elapsed_ms: Math.min(900000, Math.round(performance.now() - running.start)),
          corrected: skip ? false : corrected,
          difficulty: host.querySelector("select").value,
        });
        running = null;
        draw();
      });
    };
    host.querySelector("form").onsubmit = (e) => {
      e.preventDefault();
      submit(false);
    };
    host.querySelector("[data-answer-skip]").onclick = () => submit(true);
    article.querySelector("[data-activity-heading]")?.focus({ preventScroll: true });
  }
  panel.querySelector("[data-assessment-refresh]").onclick = () => {
    running = null;
    run(load);
  };
  run(load);
}
