// Family surfaces read the same recipient-scoped records; no clinical inference is added.
function renderFamilyOverview(plan) {
  const pending = records("help").filter(
    (item) => item.payload.recipient_id === S.user.id && item.status === "requested",
  );
  const accepted = records("help").filter(
    (item) => item.payload.recipient_id === S.user.id && item.status === "accepted",
  );
  return `<div class="family-overview">${carePageHeading("CONNECTED, WITH CARE", "Care circle overview", "A little coordination can make the day easier.")}<section class="family-patient-panel"><span class="family-linked-art" aria-hidden="true"><i></i><i></i></span><span class="family-panel-label">YOUR SHARED WORKSPACE</span><h2>${esc(S.data.patient.name)}</h2><p>You are viewing the information shared with your authorized family account.</p>${S.data.scopes.includes("messages") ? '<button data-tab="messages">Messages</button>' : ""}</section><section class="family-attention"><div class="care-section-heading"><h2>Waiting for your response</h2><span class="care-record-count">${pending.length}</span></div>${
    pending.length
      ? pending
          .slice(0, 3)
          .map(
            (item) =>
              `<article class="family-request-card"><span class="family-request-label">HELP REQUEST</span><p>${esc(item.payload.text)}</p><button class="primary" data-accept="${esc(item.id)}">Accept responsibility</button><small>Accept only if you can take responsibility for this request.</small></article>`,
          )
          .join("")
      : '<div class="family-clear-state"><span aria-hidden="true">—</span><div><strong>No requests waiting for you</strong><p>New requests will appear here when they are shared with you.</p></div></div>'
  }${pending.length > 3 ? '<button data-tab="support">View all help requests</button>' : ""}${accepted.length ? `<p class="family-accepted-note">You have accepted ${accepted.length} ${accepted.length === 1 ? "request" : "requests"}. Acceptance is not confirmation that the activity is complete.</p>` : ""}</section><section class="family-destinations" aria-label="Family workspace actions"><button data-tab="plan"><span class="shortcut-icon">${icon("plan")}</span><span><strong>Shared tasks</strong><small>Review the current plan and activities</small></span><span aria-hidden="true">→</span></button><button data-tab="support" aria-label="Support"><span class="shortcut-icon">${icon("support")}</span><span><strong>Practical support</strong><small>Review requests and coordinate help</small></span><span aria-hidden="true">→</span></button><button data-tab="weekly" aria-label="Weekly summary"><span class="shortcut-icon">${icon("weekly")}</span><span><strong>Weekly summary</strong><small>Recorded activity and care-team reports</small></span><span aria-hidden="true">→</span></button></section><section class="family-plan-note"><span aria-hidden="true">${icon("plan")}</span><div><h2>Current care-team instructions</h2><p>${esc(plan?.payload.source_review_required ? "The plan is waiting for source review. Ask the care team before acting on affected instructions." : plan?.payload.instructions || "No approved plan is available.")}</p><p class="muted">Task responses are participant reports, not a clinical stability estimate.</p></div></section></div>`;
}
function renderMobileReportDetails(report) {
  const labels = {
    completed: "Reported complete",
    deferred: "Postponed",
    skipped: "Skipped",
    help: "Asked for help",
    pending: "Not yet confirmed",
    unconfirmed: "No confirmation recorded",
    unknown: "Status unavailable",
  };
  return `<section class="mobile-week-record"><span class="mobile-week-label">ACTIVITY RECORD</span><p class="mobile-week-dates">${esc(report.start)} — ${esc(report.end)}<small>${esc(report.timezone)}</small></p><h2><strong>${report.counts.completed}</strong> reported complete</h2><p>of ${report.denominator} recorded activities</p><p class="mobile-evidence-boundary">Activity evidence is not a measure of memory or clinical stability.</p></section><section class="card mobile-record-states"><h2>What was recorded</h2><dl>${Object.entries(
    report.counts,
  )
    .filter(([key, value]) => value > 0 || key === "completed")
    .map(([key, value]) => `<div><dt>${esc(labels[key] || key)}</dt><dd>${value}</dd></div>`)
    .join(
      "",
    )}</dl><p class="mobile-missing-records">${report.data_quality.dates_without_recorded_activities} dates have no recorded activities. Expected activity count is unavailable.</p><details><summary>How to read these counts</summary>${report.notes.map((note) => `<p>${esc(note)}</p>`).join("")}<p>${report.data_quality.invalid_activity_dates} activity records have unusable dates.</p></details></section><section class="card mobile-daily-record"><details open><summary>Daily activity records</summary><p class="muted">Blue: reported complete. Grey: other recorded states. Empty bars mean no recorded activity, not a missed activity.</p>${reportBars(report.daily, "Daily activity counts")}</details></section><section class="card"><details><summary>Four-week comparison</summary><p class="muted">Each row has its own recorded denominator. This does not establish improvement or decline.</p>${reportBars(report.trend, "Four-week activity counts")}</details></section><section class="card"><details><summary>Recorded actions</summary><p class="muted">${report.timeline_total} actions in this week.${report.timeline_truncated ? " Showing the latest 200." : ""}</p>${
    report.timeline.length
      ? `<ol class="report-timeline">${[...report.timeline]
          .reverse()
          .map(
            (item) =>
              `<li><time>${esc(new Date(item.at).toLocaleString("en", { timeZone: report.timezone }))}</time><strong>${esc(item.action.replaceAll(".", " · "))}${item.response ? " · " + esc(item.response) : ""}</strong><span>${esc(item.title)}</span><small>Source: ${esc(item.source_id)}</small></li>`,
          )
          .join("")}</ol>`
      : "<p>No actions recorded in this interval.</p>"
  }</details></section>`;
}
