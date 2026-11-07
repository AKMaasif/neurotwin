function clearPatientContext(patientId = null) {
  const nextEpoch = (S.workspaceEpoch || 0) + 1;
  const nextReportEpoch = (S.reportEpoch || 0) + 1;
  S.workspaceEpoch = nextEpoch;
  S.workspaceChanging = true;
  if (typeof stopCompanion === "function") stopCompanion(false);
  stopCareCapture();
  resetCareMessages();
  const keep = new Set([
    "user",
    "csrf",
    "workspaces",
    "workspaceEpoch",
    "workspaceChanging",
    "care",
    "voiceEpoch",
    "accountTextLarge",
  ]);
  for (const key of Object.keys(S)) if (!keep.has(key)) delete S[key];
  Object.assign(S, {
    pid: patientId,
    data: null,
    tab: S.user?.role === "clinician" ? "overview" : "home",
    chat: [],
    memory: null,
    contacts: [],
    offlineActions: [],
    draftText: "",
    helpDraft: "",
    reportHistory: [],
    reportNotes: {},
    documents: [],
    reportZone: "Asia/Dubai",
    reportEpoch: nextReportEpoch,
    busy: false,
    recording: false,
    voiceState: "idle",
    dirty: false,
  });
  if (typeof revision !== "undefined") revision = null;
  return nextEpoch;
}
// Shared patient context boundary. The API, never this picker, grants access.
async function fetchAuthorizedWorkspace(patientId) {
  try {
    return await api(`/patients/${patientId}/workspace`);
  } catch (error) {
    if (error.status !== 403 || S.pid !== patientId) throw error;
    clearPatientContext();
    try {
      S.workspaces = await api("/patients");
    } catch {
      S.workspaces = [];
    }
    S.workspaceChanging = false;
    workspaceState(
      "Access to the previous patient workspace is no longer available. Choose a currently authorized patient or refresh access.",
    );
    return null;
  }
}
function workspaceWritesBusy() {
  return !!(
    S.workspaceChanging ||
    S.pdfBusy ||
    S.sourceBusy ||
    S.draftBusy ||
    S.reportBusy ||
    S.routineSending ||
    S.busy ||
    S.care?.busy
  );
}
function renderWorkspacePicker() {
  if ((S.workspaces || []).length < 2) return "";
  return `<label class="workspace-picker">Patient workspace<select id="active-workspace" ${workspaceWritesBusy() ? "disabled" : ""}><option value="" ${!S.pid ? "selected" : ""}>Choose a patient</option>${S.workspaces.map((patient) => `<option value="${esc(patient.id)}" ${patient.id === S.pid ? "selected" : ""}>${esc(patient.name)} · ${esc(patient.region)}</option>`).join("")}</select></label>`;
}
function workspaceState(message = "Choose the patient you want to work with.", loading = false) {
  document.body.classList.remove("care-chat-page");
  const hasPatients = !!S.workspaces?.length;
  $("#app").innerHTML =
    `<main class="workspace-state"><p class="eyebrow">NEUROTWIN · AUTHORIZED WORKSPACES</p><h1>${loading ? "Opening workspace" : hasPatients ? "Choose a patient" : "No active patient workspace"}</h1><p role="status">${esc(message)}</p>${loading ? '<progress aria-label="Loading authorized patient workspace"></progress>' : `${renderWorkspacePicker()}<div class="actions"><button id="workspace-retry">Refresh access</button><button id="workspace-signout">Sign out</button></div><p class="muted">Only currently authorized patient workspaces are listed. Switching patients never changes your account or permissions.</p>`}</main>`;
  bindWorkspacePicker();
  if ($("#workspace-retry"))
    $("#workspace-retry").onclick = () =>
      guard(async () => {
        S.workspaces = await api("/patients");
        if (S.workspaces.length === 1) await activateWorkspace(S.workspaces[0].id, true);
        else workspaceState();
      });
  if ($("#workspace-signout"))
    $("#workspace-signout").onclick = () =>
      guard(async () => {
        if (typeof countOfflineActions === "function" && (await countOfflineActions(S.user.id))) {
          if (
            !confirm(
              "Signing out will discard unsent responses for all patients on this device. Continue?",
            )
          )
            return;
          await clearOfflineActions(S.user.id);
        }
        if (typeof closeDeviceNotifications === "function") await closeDeviceNotifications();
        await api("/logout", "POST");
        clearPatientContext();
        S.user = null;
        S.pid = null;
        S.data = null;
        S.workspaces = [];
        login();
      });
}
function bindWorkspacePicker() {
  const picker = $("#active-workspace");
  if (!picker) return;
  picker.onchange = () =>
    guard(async () => {
      if (!picker.value) {
        picker.value = S.pid || "";
        return;
      }
      try {
        await activateWorkspace(picker.value);
      } finally {
        if (document.contains(picker)) picker.value = S.pid || "";
      }
    });
}
async function activateWorkspace(patientId, initial = false) {
  if (!initial && workspaceWritesBusy())
    throw Error("Finish or stop the current operation before switching patients.");
  if (S.pid === patientId && S.data) return;
  if (!initial) S.workspaces = await api("/patients");
  if (!S.workspaces?.some((patient) => patient.id === patientId)) {
    if (S.data && S.workspaces?.some((patient) => patient.id === S.pid)) render();
    else {
      clearPatientContext();
      S.workspaceChanging = false;
      workspaceState("This patient is no longer available to your account.");
    }
    throw Error("This patient is no longer available to your account. Refresh access.");
  }
  const hasDrafts =
    S.dirty || hasCareDrafts() || S.draftText?.trim() || S.helpDraft?.trim() || S.recording;
  if (
    hasDrafts &&
    !confirm(
      "Switch patient and discard unsaved edits, text and recording drafts? Offline responses remain linked to their original patient.",
    )
  )
    return;
  const nextEpoch = clearPatientContext(patientId);
  workspaceState("Loading this patient's current authorized records…", true);
  try {
    // A second tab opening the same workspace must not clear existing device
    // reminders. A deliberate patient switch invalidates the old context.
    if (!initial && typeof closeDeviceNotifications === "function")
      await closeDeviceNotifications();
    await refresh();
    if (S.workspaceEpoch !== nextEpoch) return;
    if (S.user.role === "participant" && S.data.scopes.includes("preferences")) {
      const memory = await api(`/patients/${S.pid}/companion/memory`);
      if (S.workspaceEpoch !== nextEpoch) return;
      S.memory = memory;
      S.chat = memory.history.flatMap((turn) => [
        { role: "user", text: turn.user },
        { role: "bot", text: turn.assistant },
      ]);
    }
  } catch (error) {
    if (S.workspaceEpoch !== nextEpoch) return;
    S.data = null;
    S.pid = null;
    resetCareMessages();
    try {
      S.workspaces = await api("/patients");
    } catch {
      S.workspaces = [];
    }
    S.workspaceChanging = false;
    workspaceState(
      error.message || "The workspace could not be loaded. Refresh access and try again.",
    );
    return;
  } finally {
    if (S.workspaceEpoch === nextEpoch) S.workspaceChanging = false;
  }
  if (S.workspaceEpoch === nextEpoch && S.data) {
    render();
    window.scrollTo(0, 0);
  }
}
