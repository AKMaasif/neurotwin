// Presentation follows the selected mobile reference; values come from authenticated state.
function brandMark() {
  return ntUi(
    '<svg viewBox="0 0 32 32" fill="none" aria-hidden="true"><path d="M14 5C7 3 3 10 7 14c-5 4-1 12 6 11m5-20c7-2 11 5 7 9 5 4 1 12-6 11M13 9c-4 0-5 4-2 6m9-6c4 0 5 4 2 6M10 19c-1 3 1 4 3 4m9-4c1 3-1 4-3 4M16 4v24" stroke="currentColor" stroke-width="2.1" stroke-linecap="round"/></svg>',
  );
}
function companionFigure() {
  return ntUi`<div class="companion-figure companion-presence ${S.recording ? "is-recording" : ""}" aria-hidden="true"><svg viewBox="0 0 160 120" fill="none"><path d="M30 68c0-28 30-43 50-18 20-25 50-10 50 18s-30 43-50 18c-20 25-50 10-50-18Z" stroke="currentColor" stroke-width="3"/><path d="M59 63v10m14-18v26m14-26v26m14-18v10" stroke="currentColor" stroke-width="5" stroke-linecap="round"/></svg></div>`;
}
function homePlanOverview(tasks) {
  const done = tasks.filter((task) => task.status === "completed").length;
  const total = tasks.length;
  return ntUi`<section class="plan-glance" aria-label="Current plan at a glance"><div class="section-label"><h2>Today at a glance</h2><span>${total} ${ntTr(total === 1 ? "activity" : "activities")}</span></div><div class="glance-content">${total ? ntUi`<div class="activity-ring"><svg viewBox="0 0 80 80" aria-hidden="true"><circle cx="40" cy="40" r="33"/><circle class="ring-value" cx="40" cy="40" r="33" pathLength="100" stroke-dasharray="${(100 * done) / total} 100"/></svg><strong>${done}/${total}</strong></div>` : ntUi('<span class="glance-empty" aria-hidden="true">—</span>')}<div><strong>${total ? (done === total ? ntTr("Your responses are recorded") : ntTr("Keep going!")) : ntTr("Room for your next step")}</strong><p>${total ? ntText`${total - done} not confirmed in the current plan.` : ntTr("View your scheduled routines in My Plan.")}</p><small>Participant reports · not a health score</small></div></div></section>`;
}
function renderMobileHome(tasks, plan) {
  const family = S.user.role === "family";
  if (family) return renderFamilyOverview(plan);
  const name = S.memory?.enabled && S.memory.preferred_name ? S.memory.preferred_name : S.user.name;
  const pending = tasks.find((t) => t.status === "pending");
  const hasRoutine = S.routineData?.occurrences.some(activeOccurrence);
  const activity =
    hasRoutine || family ? renderDailyActivities(1) : pending ? taskCard(pending, true) : "";
  const queued = !hasRoutine && !family && S.offlineActions?.length ? renderDailyActivities(1) : "";
  const shortcuts = [
    ["plan", ntTr("My Plan"), ntTr("See approved activities"), "plan"],
    ["check", ntTr("My Check"), ntTr("View check availability"), "check"],
    ["companion", ntTr("Companion"), ntTr("Talk or type for help"), "companion"],
    ["support", ntTr("Support"), ntTr("Contact your care circle"), "support"],
  ];
  return ntUi`<div class="home-first-screen"><div class="home-heading"><p class="home-date">${esc(new Intl.DateTimeFormat(ntLocale() === "ar" ? "ar-AE" : "en", { dateStyle: "full" }).format(new Date()))}</p><h1>${family ? ntTr("Care circle overview") : ntTr(new Date().getHours() < 12 ? ntTr("Good morning") : new Date().getHours() < 18 ? ntTr("Good afternoon") : ntTr("Good evening")) + ", " + esc(name) + ntUi(' <span aria-hidden="true">👋</span>')}</h1><p>${family ? ntTr("Support, one shared step at a time.") : ntTr("Let’s keep the progress going today.")}</p></div><section class="day-introduction"><svg viewBox="0 0 480 92" preserveAspectRatio="none" aria-hidden="true"><circle cx="353" cy="36" r="24" fill="#ffe0a0"/><path d="M0 70C35 49 62 68 98 49S158 67 201 47 260 61 307 39 361 53 410 34 455 37 480 19V92H0Z" fill="#d9edff"/><path d="M0 84C44 67 67 78 112 68S185 89 231 70 309 77 351 57 425 66 480 42V92H0Z" fill="#96d2f2"/></svg><div><span class="hero-brain" aria-hidden="true"><img src="assets/reference-v2/brain.webp" alt="" width="512" height="512" decoding="async"></span><p class="eyebrow">YOUR EVERYDAY SUPPORT</p><h2>Your day,<br>one step at a time.</h2><p>Follow your approved routines and stay on track.</p><button data-tab="plan">See scheduled activities <span aria-hidden="true">→</span></button></div></section>${homePlanOverview(tasks)}<section class="home-shortcuts" aria-label="Quick actions">${shortcuts.map(([tab, label, detail, symbol]) => ntUi`<button data-tab="${tab}" aria-label="${esc(label + ": " + detail)}" class="home-shortcut"><span class="shortcut-icon">${referenceQuickIcon(symbol)}</span><strong>${ntTr(label)}</strong><span>${detail}</span></button>`).join("")}</section></div>${queued}<section class="next-activity" aria-label="Next activity"><div class="section-label"><span>${family ? ntTr("Needs your attention") : ntTr("Your next activity")}</span><span class="day-marker">${family ? "Follow-up" : ntTr("Next step")}</span></div>${activity || ntUi('<section class="card quiet-state"><h2>No activity waiting</h2><p>You can review your plan or ask your care team for help.</p><button data-tab="plan">View my plan</button></section>')}</section><section class="card plan-preview"><div class="section-label"><span>From your care team</span>${icon("plan")}</div><h2>Your current plan</h2><p>${esc(plan?.payload.source_review_required ? ntTr("Your plan is waiting for care-team review.") : plan?.payload.instructions || ntTr("No approved plan available."))}</p><p class="muted">${esc(plan?.payload.signed_by || ntTr("Awaiting care-team approval"))} · Synthetic support plan</p>${plan?.payload.source_review_required ? ntUi('<p class="error">A source was corrected. Ask your care team before acting on affected instructions.</p>') : ""}<button data-tab="plan">Review plan</button></section><section class="home-connections" aria-label="Stay connected">${S.data.scopes.includes("messages") ? ntUi`<button data-tab="messages" aria-label="Messages"><span class="shortcut-icon">${icon("messages")}</span><span><strong>Your care circle</strong><small>Messages with family and your care team</small></span><span aria-hidden="true">→</span></button>` : ""}<button data-tab="weekly" aria-label="Weekly summary"><span class="shortcut-icon">${icon("plan")}</span><span><strong>Weekly summary</strong><small>Recorded activities and shared reports</small></span><span aria-hidden="true">→</span></button></section>`;
}
function renderMobilePlan(tasks, plan) {
  const family = S.user.role === "family";
  const held = (task) =>
    records("plan").some((p) => p.id === task.payload.plan_id && p.payload.source_review_required);
  const next = tasks.find((task) => task.status === "pending" && !held(task));
  const confirmed = tasks.filter((task) => task.status === "completed").length;
  const periods = [
    ["morning", ntTr("Morning"), ntTr("A gentle start"), ["morning"]],
    ["afternoon", ntTr("Afternoon"), ntTr("At your own pace"), ["afternoon"]],
    ["evening", ntTr("Evening"), ntTr("Time to wind down"), ["evening", "night"]],
    ["anytime", ntTr("Other activities"), ntTr("As your plan describes"), []],
  ];
  const bucket = (task) => {
    const period = String(task.payload.period || "")
      .toLowerCase()
      .trim();
    return periods.find((group) => group[3].includes(period))?.[0] || "anytime";
  };
  return ntUi`<div class="plan-page"><div class="plan-page-heading reference-page-heading"><button class="reference-back plain" data-tab="home" aria-label="Back to home">←</button>${referenceIllustration("plan")}<h1>${family ? ntTr("Shared tasks") : ntTr("My Plan")}</h1><p>Your personalized routines<br>for better wellbeing.</p></div><div class="plan-layout"><div class="plan-primary"><section id="scheduled-activities" class="plan-scheduled" tabindex="-1"><div class="plan-section-heading"><span class="plan-section-icon" aria-hidden="true">${icon("check")}</span><div><h2>Scheduled activities</h2><p>Your reminders and recurring routines.</p></div></div>${renderDailyActivities()}${renderRoutineManager()}${!S.routineData?.occurrences.some(activeOccurrence) ? ntUi('<p class="plan-no-reminders">No activity is waiting for confirmation here.</p>') : ""}</section><section class="plan-spotlight" aria-label="Plan overview"><div class="plan-orbit" aria-hidden="true"><span></span><i></i><b></b></div><div class="plan-spotlight-content"><span class="plan-spotlight-label">${next ? ntTr("NEXT IN YOUR PLAN") : ntTr("ROOM TO GO AT YOUR PACE")}</span><h2>${esc(next?.payload.title || (plan?.payload.source_review_required ? ntTr("Your care team is reviewing your plan") : ntTr("Your day, one step at a time")))}</h2><p>${next ? esc([next.payload.period, next.payload.time].filter(Boolean).join(" · ")) : ntTr("Follow your approved instructions and ask for support whenever you need it.")}</p>${next ? ntUi`<a class="button plan-jump" href="#plan-task-${esc(next.id)}">Find next activity <span aria-hidden="true">↓</span></a>` : ntUi('<a class="button plan-jump" href="#scheduled-activities">See scheduled activities <span aria-hidden="true">↓</span></a>')}</div></section>${tasks.length ? ntUi`<div class="plan-confirmation-count"><span class="plan-count-mark" aria-hidden="true">✓</span><span><strong>${confirmed} of ${tasks.length} plan activities confirmed</strong><small>Participant reports · not a clinical assessment</small></span></div>` : ""}<div class="plan-filters" role="group" aria-label="Filter approved plan activities">${[
    ["all", ntTr("All"), tasks.length],
    ["pending", ntTr("Not confirmed"), tasks.length - confirmed],
    ["completed", ntTr("Confirmed"), confirmed],
  ]
    .map(
      ([value, label, count]) =>
        ntUi`<button data-plan-filter="${value}" aria-pressed="${(S.planFilter || "all") === value}">${label} <span>${count}</span></button>`,
    )
    .join(
      "",
    )}</div><p class="plan-filter-empty" hidden role="status">No plan activities match this filter. Scheduled routines remain below.</p><section class="plan-timeline" aria-label="Approved plan activities">${periods
    .map(([key, label, caption]) => {
      const items = tasks.filter((task) => bucket(task) === key);
      if (!items.length) return "";
      return ntUi`<section class="plan-period period-${key}" aria-labelledby="period-${key}"><div class="plan-period-heading"><span class="period-symbol" aria-hidden="true"></span><div><h2 id="period-${key}">${label}</h2><p>${caption}</p></div></div><ol>${items.map((task) => ntUi`<li id="plan-task-${esc(task.id)}" tabindex="-1" class="plan-timeline-item ${task.status === "completed" ? "is-confirmed" : ""}"><span class="timeline-dot" aria-hidden="true">${task.status === "completed" ? "✓" : ""}</span>${taskCard(task)}</li>`).join("")}</ol></section>`;
    })
    .join(
      "",
    )}${!tasks.length ? ntUi('<section class="card plan-empty"><h2>No separate plan activities</h2><p>Any scheduled routines are listed below. Your care team can help you review your plan.</p></section>') : ""}</section></div><aside class="plan-context" aria-label="Care team and support"><section class="plan-care-note"><span aria-hidden="true">${icon("plan")}</span><div><h2>From your care team</h2><p>${esc(plan?.payload.source_review_required ? ntTr("Please ask your care team before acting on instructions affected by the source correction.") : plan?.payload.instructions || ntTr("No approved plan is available yet."))}</p>${plan?.payload.signed_by ? ntUi`<small>${esc(plan.payload.signed_by)}</small>` : ""}</div></section><section class="plan-help-strip"><div><h2>A little help is always an option.</h2><p>Ask for guidance or contact your care circle.</p></div><div class="actions"><button data-tab="companion">Step-by-step help</button><button data-tab="support">Ask for help</button></div></section></aside></div></div>`;
}
function mobileNavigation(family) {
  return family
    ? [
        ["home", ntTr("Overview")],
        ["plan", ntTr("Tasks")],
        ["messages", ntTr("Messages")],
        ["weekly", ntTr("Reports")],
        ["settings", ntTr("Circle")],
      ]
    : [
        ["home", ntTr("Home")],
        ["check", ntTr("My Check")],
        ["companion", ntTr("Companion")],
        ["plan", ntTr("My Plan")],
        ["support", ntTr("Support")],
      ];
}
let mobileDockObserver;
function syncMobileDock() {
  mobileDockObserver?.disconnect();
  const dock = document.querySelector("nav[data-primary-navigation]");
  const update = () => {
    document.documentElement.style.setProperty(
      "--mobile-dock-height",
      (window.matchMedia("(min-width: 48rem)").matches
        ? 0
        : dock?.getBoundingClientRect().height || 88) + "px",
    );
  };
  update();
  if (dock && window.ResizeObserver) {
    mobileDockObserver = new ResizeObserver(update);
    mobileDockObserver.observe(dock);
  }
}

// Keep the message viewport anchored after mobile-only shell/composer sizing.
// Reading an older position stays under the user's control across layout changes.
let mobileHistoryObserver;
function syncMobileHistory(followLatest) {
  mobileHistoryObserver?.disconnect();
  const history = document.querySelector(".care-history");
  if (!history) return;
  let follow = !!followLatest;
  const align = () => {
    if (follow && history.isConnected) history.scrollTop = history.scrollHeight;
  };
  align();
  history.addEventListener(
    "scroll",
    () => {
      follow = history.scrollHeight - history.clientHeight - history.scrollTop < 60;
    },
    { passive: true },
  );
  if (window.ResizeObserver) {
    mobileHistoryObserver = new ResizeObserver(align);
    mobileHistoryObserver.observe(history);
  }
}

function bindPlanFilters() {
  const apply = () => {
    const filter = S.planFilter || "all";
    document
      .querySelectorAll("[data-plan-filter]")
      .forEach((button) =>
        button.setAttribute("aria-pressed", String(button.dataset.planFilter === filter)),
      );
    let shown = 0;
    document.querySelectorAll(".plan-timeline-item").forEach((item) => {
      const task = records("task").find((task) => "plan-task-" + task.id === item.id);
      item.hidden =
        filter === "completed"
          ? task?.status !== "completed"
          : filter === "pending"
            ? task?.status === "completed"
            : false;
      if (!item.hidden) shown++;
    });
    document
      .querySelectorAll(".plan-period")
      .forEach(
        (period) =>
          (period.hidden = ![...period.querySelectorAll(".plan-timeline-item")].some(
            (item) => !item.hidden,
          )),
      );
    const empty = document.querySelector(".plan-filter-empty");
    if (empty) empty.hidden = shown > 0 || filter === "all";
  };
  document.querySelectorAll("[data-plan-filter]").forEach(
    (button) =>
      (button.onclick = () => {
        S.planFilter = button.dataset.planFilter;
        apply();
      }),
  );
  apply();
}

function referenceIllustration(kind) {
  const asset = kind === "support" ? "support" : "plan";
  return ntUi`<img class="reference-illustration" src="assets/reference-v2/${asset}.webp" alt="" width="512" height="512" decoding="async">`;
}
function bindRoutineFilters() {
  const apply = () => {
    const selected = S.routineFilter || "all";
    document
      .querySelectorAll("[data-routine-filter]")
      .forEach((button) =>
        button.setAttribute("aria-pressed", String(button.dataset.routineFilter === selected)),
      );
    let shown = 0;
    document.querySelectorAll("[data-routine-state]").forEach((row) => {
      row.hidden = selected !== "all" && row.dataset.routineState !== selected;
      if (!row.hidden) shown++;
    });
    const empty = document.querySelector(".routine-filter-empty");
    if (empty) empty.hidden = shown > 0 || selected === "all";
  };
  document.querySelectorAll("[data-routine-filter]").forEach(
    (button) =>
      (button.onclick = () => {
        S.routineFilter = button.dataset.routineFilter;
        apply();
      }),
  );
  apply();
}

function referenceQuickIcon(kind) {
  const shapes = {
    plan: ntUi(
      '<rect x="5" y="6" width="22" height="23" rx="5" fill="#0875f9"/><path d="M5 13h22M11 3v7m10-7v7M11 18h3m4 0h3m-10 5h3m4 0h3" stroke="white" stroke-width="2" stroke-linecap="round"/>',
    ),
    check: ntUi(
      '<circle cx="16" cy="16" r="13" fill="#fa7878"/><path d="M5 17h6l3-7 4 13 3-7h6" stroke="white" stroke-width="1.8" stroke-linejoin="round" fill="none"/>',
    ),
    companion: ntUi(
      '<g fill="#08b6b5"><circle cx="16" cy="10" r="5"/><circle cx="6" cy="12" r="3.5"/><circle cx="26" cy="12" r="3.5"/><path d="M8 28v-5a8 8 0 0 1 16 0v5ZM1 25v-4a5 5 0 0 1 7-5 12 12 0 0 0-3 9ZM31 25v-4a5 5 0 0 0-7-5 12 12 0 0 1 3 9Z"/></g>',
    ),
    support: ntUi(
      '<circle cx="16" cy="16" r="12" fill="#ff8c43" stroke="white" stroke-width="1.4"/><circle cx="16" cy="16" r="6" fill="#fff0df" stroke="white" stroke-width="1.5"/><path d="m8 7 4 4m8 10 4 4M7 24l5-4m8-8 5-5" stroke="white" stroke-width="4"/>',
    ),
  };
  return ntUi`<svg viewBox="0 0 32 32" fill="none" aria-hidden="true">${shapes[kind] || shapes.plan}</svg>`;
}
