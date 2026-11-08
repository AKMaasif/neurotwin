let cameraCleanup = null;
function clearCameraAssistance() {
  cameraCleanup?.();
  cameraCleanup = null;
}
function renderCameraAssistance() {
  if (
    S.user.role !== "participant" ||
    !S.data.patient.synthetic ||
    !S.data.scopes.includes("assessment")
  )
    return "";
  return ntUi`<details class="card camera-panel"><summary>Camera assistance · synthetic samples only</summary><p>Choose or capture one sample image, preview it, then decide whether to send. No background camera runs. Photos and results clear when this screen refreshes or you leave it.</p><p>Use only synthetic everyday-object samples without people, personal information or medical material.</p><button type="button" data-camera-options>Check camera availability</button><p data-camera-provider></p><label>Choose or capture a sample image<input type="file" data-camera-file accept="image/jpeg,image/png,image/webp" capture="environment"></label><p>JPEG, PNG or WebP · up to 1 MB · 160 pixels per side to 4 megapixels.</p><img data-camera-preview hidden alt="Your selected sample, not yet sent"><form data-camera-form><label class="camera-consent"><input type="checkbox" data-camera-consent required disabled><span data-camera-consent-text>Read the provider and consent details before sending.</span></label><button type="submit" data-camera-send disabled>Send this sample for object suggestions</button></form><button type="button" data-camera-clear>Clear photo / stop showing result</button><p data-camera-status role="status" aria-live="polite"></p><p data-camera-result></p><p>Suggestions may be wrong. Do not use them for navigation, medication or medical decisions. Clearing a sent request cannot recall data already sent to the provider.</p></details>`;
}
function bindCameraAssistance() {
  const panel = document.querySelector(".camera-panel");
  if (!panel) return;
  const pid = S.pid,
    actor = S.user.id,
    epoch = S.workspaceEpoch;
  const current = () =>
    panel.isConnected && S.pid === pid && S.user?.id === actor && S.workspaceEpoch === epoch;
  const fileInput = panel.querySelector("[data-camera-file]"),
    preview = panel.querySelector("[data-camera-preview]");
  const consent = panel.querySelector("[data-camera-consent]"),
    send = panel.querySelector("[data-camera-send]");
  const status = panel.querySelector("[data-camera-status]"),
    result = panel.querySelector("[data-camera-result]");
  let file = null,
    url = null,
    options = null,
    pending = false,
    controller = null,
    generation = 0;
  const update = () => {
    consent.disabled = pending || !options;
    fileInput.disabled = pending;
    send.disabled = pending || !file || !options?.provider_ready || !consent.checked;
  };
  const clear = (preserveFileInput = false) => {
    generation++;
    controller?.abort();
    controller = null;
    if (url) URL.revokeObjectURL(url);
    url = null;
    file = null;
    pending = false;
    if (S.pid === pid && S.workspaceEpoch === epoch && S.user?.id === actor) S.cameraBusy = false;
    if (!preserveFileInput) fileInput.value = "";
    preview.removeAttribute("src");
    preview.hidden = true;
    consent.checked = false;
    result.textContent = "";
    update();
  };
  cameraCleanup = clear;
  const loadOptions = async () => {
    try {
      const response = await api(`/patients/${pid}/camera/options`);
      if (!current()) return;
      options = response;
      panel.querySelector("[data-camera-consent-text]").textContent = options.consent_text;
      panel.querySelector("[data-camera-provider]").textContent = options.provider_ready
        ? `Provider: ${options.provider} · ${options.model}. A request is sent only after your explicit choice below.`
        : ntTr(
            "The image provider is not enabled or configured. You can preview locally, but sending is unavailable.",
          );
      update();
    } catch (error) {
      if (current()) {
        options = null;
        update();
        status.textContent = error.message;
      }
    }
  };
  panel.querySelector("[data-camera-options]").onclick = loadOptions;
  panel.ontoggle = () => {
    if (panel.open && !options) loadOptions();
  };
  consent.onchange = update;
  fileInput.onchange = () => {
    const chosen = fileInput.files[0];
    clear(true);
    if (!chosen) return;
    if (
      !["image/jpeg", "image/png", "image/webp"].includes(chosen.type) ||
      !chosen.size ||
      chosen.size > 1024 * 1024
    ) {
      status.textContent = "Choose a nonempty JPEG, PNG or WebP sample no larger than 1 MB.";
      return;
    }
    const ticket = generation;
    url = URL.createObjectURL(chosen);
    preview.onload = () => {
      if (!current() || ticket !== generation) return;
      if (
        Math.min(preview.naturalWidth, preview.naturalHeight) < 160 ||
        preview.naturalWidth * preview.naturalHeight > 4000000
      ) {
        clear();
        status.textContent = "Use a sample at least 160 pixels per side and at most 4 megapixels.";
        return;
      }
      file = chosen;
      preview.hidden = false;
      status.textContent = "Preview only. This image has not been sent.";
      update();
    };
    preview.onerror = () => {
      if (ticket !== generation) return;
      clear();
      status.textContent = "This sample could not be previewed. Choose another still image.";
    };
    preview.src = url;
  };
  panel.querySelector("[data-camera-clear]").onclick = () => {
    clear();
    status.textContent =
      "Photo and displayed result cleared. A request already sent may still be processed by the provider.";
  };
  panel.querySelector("[data-camera-form]").onsubmit = async (event) => {
    event.preventDefault();
    if (!current() || pending || !file || !consent.checked || !options?.provider_ready) return;
    const ticket = generation;
    pending = true;
    S.cameraBusy = true;
    controller = new AbortController();
    update();
    result.textContent = "";
    status.textContent = "Checking your sample…";
    try {
      const response = await fetch(`/api/patients/${encodeURIComponent(pid)}/camera/check`, {
        method: "POST",
        signal: controller.signal,
        body: file,
        headers: {
          "Content-Type": file.type,
          "X-CSRF-Token": S.csrf,
          "X-Expected-Actor": actor,
          "X-Camera-Consent": options.consent_version,
        },
      });
      const body = await response.json();
      if (!current() || ticket !== generation) return;
      if (!response.ok) {
        if (response.status === 401)
          careSessionChanged("Your session expired or was signed out. Sign in again.");
        if (
          typeof body.detail === "string" &&
          (body.detail.startsWith("Session account changed") ||
            body.detail === "Invalid CSRF token")
        )
          careSessionChanged();
        throw new Error(
          typeof body.detail === "string" ? body.detail : ntTr("The image could not be checked"),
        );
      }
      result.textContent = body.text;
      status.textContent =
        body.status === "tentative"
          ? ntTr("Tentative object suggestions. No medical assessment was made.")
          : ntTr("No useful object suggestion. Try another sample or ask someone you trust.");
    } catch (error) {
      if (current() && ticket === generation && error.name !== "AbortError")
        status.textContent = error.message;
    } finally {
      if (current() && ticket === generation) {
        pending = false;
        S.cameraBusy = false;
        consent.checked = false;
        update();
      }
    }
  };
}
