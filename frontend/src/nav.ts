/** Browser history for the signed-in application.
 *
 *  The app draws its screens from state, not URLs, so without this the Back button leaves the page. Rules enforced here:
 *   1. While signed in, the stack is always  [ ... , guard, view(0), view(1) ... ].  Back can reach `guard`, never what is below it,
 *      and landing on `guard` puts the person straight back on their dashboard. Back therefore never goes to the sign-in or landing page.
 *   2. A screen or dialog above the dashboard (Brain Analytics, a report, a sub-page) is a "layer": it pushes one entry, Back closes it,
 *      and closing it with the app's own Back/Close button removes that entry, so the two always agree.
 *   3. Signing out (the button, or an expired session) drops all of it. Dashboard state is not in the URL and is never cached.
 *  Pure browser logic: no credentials and no network. */
type Layer = { id: number; onPop: () => void };

const VIEW = "view", GUARD = "guard";
let active = false, nextId = 1, layers: Layer[] = [], waiting = false;
const queue: (() => void)[] = [];

const stateOf = (d: number) => ({ nt: VIEW, d });
const when = (fn: () => void) => { if (waiting) queue.push(fn); else fn(); };   // a history.back() is still in flight: do this after it lands
const flush = () => { waiting = false; while (queue.length && !waiting) queue.shift()!(); };

function onPop(e: PopStateEvent) {
  if (!active) return;
  const st = e.state as { nt?: string; d?: number } | null;
  if (st?.nt === VIEW && typeof st.d === "number") {
    // Back closed the top layers; a stray Forward to a layer that is not open is flattened to where we really are.
    while (layers.length > st.d) layers.pop()!.onPop();
    if (st.d > layers.length) history.replaceState(stateOf(layers.length), "");
  } else {
    // Back reached the guard (or anything older): close every layer and stay on the dashboard.
    while (layers.length) layers.pop()!.onPop();
    history.pushState(stateOf(0), "");
  }
  flush();
}

/** Call once a person is signed in (also after a page refresh while signed in). */
export function enter() {
  if (active) return;
  active = true; layers = []; waiting = false; queue.length = 0;
  window.addEventListener("popstate", onPop);
  const st = history.state as { nt?: string } | null;
  if (st?.nt === VIEW) history.replaceState(stateOf(0), "");              // refreshed on the dashboard: the guard is still underneath
  else { history.replaceState({ nt: GUARD }, ""); history.pushState(stateOf(0), ""); }
}

/** Call when the person signs out or the session ends. */
export function exit() {
  if (!active) return;
  active = false; layers = []; waiting = false; queue.length = 0;
  window.removeEventListener("popstate", onPop);
  history.replaceState({ nt: "public" }, "");                               // nothing left that names a dashboard screen
}

/** Open a layer. `onPop` runs when the browser's Back closes it. Returns its id. */
export function open(onPopFn: () => void): number {
  const id = nextId++;
  when(() => {
    if (!active) return;
    layers.push({ id, onPop: onPopFn });
    history.pushState(stateOf(layers.length), "");
  });
  return id;
}

/** Close a layer from the app's own button. The matching history entry is removed so Back does not land on a dead screen. */
export function close(id: number) {
  when(() => {
    const at = layers.findIndex((l) => l.id === id);
    if (at < 0 || !active) return;                                          // already closed by Back
    const count = layers.length - at;                                       // closing a lower layer closes those above it too
    layers.splice(at);
    waiting = true; history.go(-count);
    setTimeout(() => { if (waiting) flush(); }, 1500);                      // never leave the queue stuck if the browser did not report the move
  });
}

/** Test hook. */
export const _debug = () => ({ active, depth: layers.length, waiting });
