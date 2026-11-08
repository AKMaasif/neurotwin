// Translate static source segments before interpolation. Never translate patient data.
const ntPageLocale = (() => {
  try {
    return localStorage.getItem("neurotwin.locale") === "ar" ? "ar" : "en";
  } catch {
    return "en";
  }
})();
function ntLocale() {
  return ntPageLocale;
}
function ntTr(value) {
  return ntLocale() === "ar" ? (window.NT_AR?.[value] ?? value) : value;
}
function ntIntlLocale() {
  return ntLocale() === "ar" ? "ar-AE" : undefined;
}
function ntText(strings, ...values) {
  return strings.reduce(
    (out, part, i) =>
      out +
      part.replace(/^(\s*)([\s\S]*?)(\s*)$/, (_, a, s, b) => a + ntTr(s) + b) +
      (i < values.length ? String(values[i]) : ""),
    "",
  );
}
const ntNativeConfirm = window.confirm;
window.confirm = (text) => ntNativeConfirm.call(window, ntTr(text));
function ntEscape(value) {
  return String(value).replace(
    /[&<>"']/g,
    (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c],
  );
}
function ntDecode(value) {
  return value
    .replace(/&amp;/g, "&")
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'")
    .replace(/&lt;/g, "<")
    .replace(/&gt;/g, ">");
}
function ntStatic(value) {
  return value.replace(
    /^(\s*)([\s\S]*?)(\s*)$/,
    (_, a, text, b) =>
      a + (window.NT_AR?.[ntDecode(text)] ? ntEscape(window.NT_AR[ntDecode(text)]) : text) + b,
  );
}
function ntUi(strings, ...values) {
  if (typeof strings === "string") strings = [strings];
  if (ntLocale() !== "ar")
    return strings.reduce(
      (s, part, i) => s + part + (i < values.length ? String(values[i]) : ""),
      "",
    );
  let html = strings.reduce(
    (s, part, i) => s + part + (i < values.length ? `\uE000${i}\uE001` : ""),
    "",
  );
  const translate = (text) =>
    text
      .split(/(\uE000\d+\uE001)/g)
      .map((s) => (s.startsWith("\uE000") ? s : ntStatic(s)))
      .join("");
  html = html.replace(/<[^>]*>|[^<]+/g, (token) =>
    token.startsWith("<")
      ? token.replace(
          /\b(aria-label|title|placeholder|alt)=(['"])(.*?)\2/gs,
          (_, name, q, text) => `${name}=${q}${translate(text)}${q}`,
        )
      : translate(token),
  );
  // Use a replacement function: dollar signs and markup in dynamic values stay literal.
  return html.replace(/\uE000(\d+)\uE001/g, (_, i) => String(values[Number(i)]));
}
document.documentElement.lang = ntLocale();
document.documentElement.dir = ntLocale() === "ar" ? "rtl" : "ltr";
function ntBindLanguage() {
  document
    .querySelectorAll(
      'textarea,input:not([type="password"]):not([type="email"]):not([type="url"]),.chat,.care-message-text,.source-text',
    )
    .forEach((el) => {
      if (!el.hasAttribute("dir")) el.setAttribute("dir", "auto");
    });
  if (document.getElementById("application-language")) return;
  const parent = document.querySelector(".settings-page, .login, .topbar, .workspace-state");
  if (!parent) return;
  const box = document.createElement("div");
  box.className = "application-language";
  box.innerHTML = `<label for="application-language">${ntEscape(ntTr("Application language"))}</label><select id="application-language" aria-label="${ntEscape(ntTr("Application language"))}"><option value="en" lang="en">English</option><option value="ar" lang="ar">العربية</option></select>`;
  const select = box.querySelector("select");
  select.value = ntLocale();
  select.onchange = () => {
    if (
      typeof S !== "undefined" &&
      (S.assessmentActive || S.assessmentBusy || S.busy || S.recording)
    ) {
      select.value = ntLocale();
      return;
    }
    const modified = [...document.querySelectorAll("input,textarea")].some(
      (el) => !["password", "checkbox", "radio"].includes(el.type) && el.value !== el.defaultValue,
    );
    if (
      modified &&
      !confirm(
        ntTr("Changing language reloads the application and clears unsaved input. Continue?"),
      )
    ) {
      select.value = ntLocale();
      return;
    }
    try {
      localStorage.setItem("neurotwin.locale", select.value);
    } catch {
      select.value = ntLocale();
      return;
    }
    location.reload();
  };
  parent.prepend(box);
  if (ntLocale() === "ar" && !parent.matches(".topbar")) {
    const notice = document.createElement("p");
    notice.className = "localization-review-note";
    notice.textContent = ntTr(
      "Arabic interface wording is a draft; qualified language review is pending.",
    );
    box.append(notice);
  }
}
document.addEventListener("DOMContentLoaded", () => {
  ntBindLanguage();
  new MutationObserver(ntBindLanguage).observe(document.getElementById("app"), {
    childList: true,
    subtree: true,
  });
});
