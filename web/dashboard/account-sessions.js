function renderAccountSessions() {
  return `<details class="account-sessions"><summary>Other signed-in sessions</summary><p>Review other active sessions for your own account. Several sessions may belong to the same device.</p><button type="button" data-account-load>Check active sessions</button><p data-account-state role="status" aria-live="polite"></p><div data-account-content></div></details>`;
}

function bindAccountSessions() {
  const panel = document.querySelector(".account-sessions");
  if (!panel) return;
  const actor = S.user.id,
    epoch = S.workspaceEpoch;
  const current = () => panel.isConnected && S.user?.id === actor && S.workspaceEpoch === epoch;
  const state = panel.querySelector("[data-account-state]");
  let busy = false;
  const load = async () => {
    const summary = await api("/account/sessions");
    if (!current()) return;
    panel.querySelector("[data-account-content]").innerHTML =
      `<p><strong>${summary.other_active_sessions}</strong> other active ${summary.other_active_sessions === 1 ? "session" : "sessions"}.</p><p>This session expires ${esc(new Date(summary.current_expires).toLocaleString())}.</p>${summary.other_active_sessions ? '<button type="button" data-account-revoke>Sign out other sessions</button>' : ""}<p>This does not change your password or prevent later sign-ins. Previously downloaded information cannot be recalled.</p>`;
    const revoke = panel.querySelector("[data-account-revoke]");
    if (revoke)
      revoke.onclick = () => {
        if (
          !confirm(
            "Sign out all other active sessions for your account? This session stays signed in. Your password will not change.",
          )
        )
          return;
        run(async () => {
          const result = await api("/account/sessions/revoke-others", "POST");
          if (!current()) return;
          await load();
          if (current())
            state.textContent = `${result.revoked} other ${result.revoked === 1 ? "session" : "sessions"} signed out. This session is still active.`;
        });
      };
  };
  const run = async (operation) => {
    if (busy || !current()) return;
    busy = true;
    state.textContent = "Checking account sessions…";
    panel.setAttribute("aria-busy", "true");
    panel.querySelectorAll("button").forEach((b) => (b.disabled = true));
    try {
      await operation();
    } catch (error) {
      if (current()) {
        panel.querySelector("[data-account-content]").replaceChildren();
        state.textContent = error.message;
      }
    } finally {
      busy = false;
      if (current()) {
        panel.removeAttribute("aria-busy");
        panel.querySelectorAll("button").forEach((b) => (b.disabled = false));
      }
    }
  };
  panel.querySelector("[data-account-load]").onclick = () =>
    run(async () => {
      await load();
      if (current())
        state.textContent = "Current session information loaded. Refresh to see later changes.";
    });
}
