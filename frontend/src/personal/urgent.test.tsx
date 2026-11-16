import { describe, expect, it } from "vitest";
import { renderToStaticMarkup } from "react-dom/server";
import PersonalApp, { SCREENS, Screen } from "./PersonalApp";
import { LangContext, makeT } from "../i18n";
import type { User } from "../api";

/** The "Need urgent help?" button must be one tap away on every screen of the personal app, in English and Arabic.
 *  Each screen in SCREENS is rendered (first paint, before any data arrives) and the button is looked for in the page. */
const user: User = { id: "p1", display_name: "Test", role: "participant", language: "en", is_demo: true };

function page(screen: Screen, lang: "en" | "ar") {
  const t = makeT(lang);
  return renderToStaticMarkup(
    <LangContext.Provider value={{ t, setLang: () => undefined }}>
      <PersonalApp user={user} onSignOut={() => undefined} start={screen} startReady />
    </LangContext.Provider>,
  );
}
const count = (html: string, s: string) => html.split(s).length - 1;
const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

describe("urgent help is reachable on every screen", () => {
  for (const lang of ["en", "ar"] as const) {
    const label = esc(makeT(lang)("urgentHelp"));
    it.each(SCREENS.filter((s) => s !== "urgent"))(`${lang}: %s has the button at the top and at the bottom`, (screen) => {
      const html = page(screen, lang);
      expect(html).toContain(`class="p-urgent-btn"`);
      expect(count(html, label)).toBeGreaterThanOrEqual(2);      // header button and footer link
    });
    it(`${lang}: the urgent screen itself still offers the footer link`, () => {
      expect(count(page("urgent", lang), label)).toBeGreaterThanOrEqual(1);
    });
  }

  it("every screen in the list really renders its own page, not a fallback", () => {
    // "home" shows the consent screen first while no consent answer is known, so those two are the same page here
    const seen = new Map<string, Screen>();
    for (const s of SCREENS.filter((x) => x !== "home")) {
      const html = page(s, "en");
      expect(seen.get(html), `${s} renders the same page as ${seen.get(html)}`).toBeUndefined();
      seen.set(html, s);
    }
  });
});
