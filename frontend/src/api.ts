// The only way the web app reaches the server. The sign-in token lives in this tab only (sessionStorage):
// closing the tab signs out, which suits a shared family tablet.

export type Role = "participant" | "family" | "clinician";
export type User = { id: string; display_name: string; role: Role; language: "en" | "ar"; is_demo: boolean; username?: string | null };
export type DemoAccount = { username: string; display_name: string; role: Role; language: "en" | "ar" };
export type Consent = { scope: string; granted: boolean; at: string | null; text_version: string | null };
export type Grant = { id: number; owner: User; grantee: User; purpose: string; created_at: string; revoked_at: string | null; active: boolean };
export type Session = {
  id: number; protocol_code: string; protocol_version: string; language: string; device: string; assisted: boolean;
  assistance_note: string | null; unwell_today: boolean | null; interruptions: number; status: string;
  started_at: string; ended_at: string | null;
};
export type Evidence = {
  id: number; participant_id: string; session_id: number | null; kind: "observed" | "self_reported" | "inferred";
  measure: string; value_num: number | null; value_text: string | null; unit: string | null; missing_reason: string | null;
  protocol_code: string | null; protocol_version: string | null; producer_type: string; producer_id: string;
  producer_version: string; derived_from: number[]; quality: "usable" | "doubtful" | "unusable"; quality_reasons: string[];
  status: "current" | "amended" | "withdrawn"; supersedes_id: number | null; superseded_by_id: number | null;
  change_reason: string | null; recorded_at: string;
};
export type ReviewItem = {
  id: number; participant_id: string; evidence_id: number | null; session_id: number | null; reason: string;
  raised_by: string; status: string; decision: "keep" | "exclude" | null; resolved_by: string | null; resolution_note: string | null; created_at: string;
  resolved_at: string | null;
};
export type Observation = {
  measure: string; kind: "observed" | "self_reported"; value_num?: number | null; value_text?: string | null;
  unit?: string | null; missing_reason?: string | null;
};
export type ClinicianParticipant = User & { shared_since: string; open_items: number; last_activity: string | null };
export type FamilyEntry = {
  participant_id: string; display_name: string; active: boolean; since: string; ended_at: string | null;
  recent: { protocol_code: string; status: string; at: string }[];
};
export type EvidenceDetail = { evidence: Evidence; earlier_versions: Evidence[]; session: Session | null; protocol: unknown };
export type Decision = "keep" | "exclude";
export type ReportMeasure = {
  protocol_code: string | null; protocol_version: string | null; measure: string; kind: string; unit: string | null;
  records: number; usable: number; doubtful: number; unusable: number; missing: number; withdrawn: number;
  first: string | null; last: string | null; values: { at: string; value: number; quality: string; id: number }[];
};
export type Report = {
  participant: { id: string; display_name: string; is_demo: boolean }; generated_by: string; generated_at: string;
  period: { from: string | null; to: string | null };
  sessions: { total: number; by_status: Record<string, number>; assisted: number; unwell: number };
  measures: ReportMeasure[]; change: ChangeResult[]; review: { open: ReviewItem[]; resolved: ReviewItem[] }; rules_version: string;
};
export type ChangeWindow = { n: number; mean: number; ids: number[]; from: string; to: string };
export type ChangeResult = {
  method: string; level: number; protocol_code: string; protocol_version: string; measure: string; kind: string;
  unit: string | null; status: "insufficient" | "no_variation" | "within" | "outside"; direction: "higher" | "lower" | null;
  eligible_n: number; needed: { baseline: number; recent: number }; include_doubtful: boolean;
  excluded: { doubtful: number; unusable: number; withdrawn: number; missing: number };
  baseline: ChangeWindow | null; recent: ChangeWindow | null; difference: number | null; interval: [number, number] | null;
};
export type AuditRow = { id: number; actor_id: string; action: string; target: string | null; at: string };

// The sign-in itself lives in an HttpOnly cookie the page cannot read. The page keeps only the session's CSRF token,
// in memory, and sends it with every change. When the server says the session has ended, the app returns to sign-in.
let csrf: string | null = null;
export const setCsrf = (v: string | null) => { csrf = v; };
export const SIGNED_OUT = "neurotwin:signed-out";

export class ApiError extends Error {
  constructor(public status: number, message: string) { super(message); }
}

async function call<R>(method: string, path: string, body?: unknown): Promise<R> {
  const headers: Record<string, string> = { "Content-Type": "application/json" };
  if (method !== "GET" && csrf) headers["X-CSRF-Token"] = csrf;
  const res = await fetch(path, { method, headers, credentials: "same-origin",
    body: body === undefined ? undefined : JSON.stringify(body) });
  if (!res.ok) {
    let msg = res.statusText;
    try { msg = (await res.json()).detail ?? msg; } catch { /* not JSON */ }
    if (res.status === 401 && !path.startsWith("/api/auth/")) {
      csrf = null;
      window.dispatchEvent(new Event(SIGNED_OUT));
    }
    throw new ApiError(res.status, typeof msg === "string" ? msg : JSON.stringify(msg));
  }
  return res.json() as Promise<R>;
}

const get = <R,>(p: string) => call<R>("GET", p);
const post = <R,>(p: string, b?: unknown) => call<R>("POST", p, b ?? {});

export const api = {
  demoAccounts: () => get<DemoAccount[]>("/api/demo-accounts"),
  login: (username: string, password: string) => post<{ user: User; csrf: string }>("/api/auth/login", { username, password }),
  session: () => get<{ user: User; csrf: string; expires_at: string }>("/api/auth/session"),
  logout: () => post<{ ok: boolean }>("/api/auth/logout"),
  changePassword: (current_password: string, new_password: string) =>
    post<{ ok: boolean; other_sessions_ended: number }>("/api/account/password", { current_password, new_password }),
  otherSessions: () => get<{ other_active_sessions: number; current_expires_at: string }>("/api/account/sessions"),
  revokeOtherSessions: () => post<{ ended: number }>("/api/account/sessions/revoke-others"),
  me: () => get<User>("/api/me"),
  setLanguage: (language: "en" | "ar") => call<User>("PUT", "/api/me/language", { language }),

  consents: () => get<Consent[]>("/api/consents"),
  setConsent: (scope: string, granted: boolean, language: string) => post<Consent>("/api/consents", { scope, granted, language }),

  grants: () => get<Grant[]>("/api/grants"),
  grantCandidates: () => get<User[]>("/api/grants/candidates"),
  createGrant: (grantee_id: string, purpose: string) => post<Grant>("/api/grants", { grantee_id, purpose }),
  revokeGrant: (id: number) => post<Grant>(`/api/grants/${id}/revoke`),

  startSession: (b: { protocol_code: string; protocol_version: string; language: string; device?: string;
    assisted?: boolean; assistance_note?: string | null; unwell_today?: boolean | null }) => post<Session>("/api/sessions", b),
  completeSession: (id: number, b: { status: string; interruptions: number; observations: Observation[]; client_version?: string }) =>
    post<{ session: Session; evidence: Evidence[] }>(`/api/sessions/${id}/complete`, b),
  sessions: (pid: string) => get<Session[]>(`/api/participants/${encodeURIComponent(pid)}/sessions`),

  evidence: (pid: string, history = false) =>
    get<Evidence[]>(`/api/participants/${encodeURIComponent(pid)}/evidence${history ? "?include_history=true" : ""}`),
  evidenceDetail: (id: number) => get<EvidenceDetail>(`/api/evidence/${id}`),
  amend: (id: number, b: { value_num?: number | null; value_text?: string | null; reason: string }) => post<Evidence>(`/api/evidence/${id}/amend`, b),
  withdraw: (id: number, reason: string) => post<Evidence>(`/api/evidence/${id}/withdraw`, { reason }),

  reviewItems: (pid: string, status = "open") => get<ReviewItem[]>(`/api/participants/${encodeURIComponent(pid)}/review-items?status=${status}`),
  resolve: (id: number, note: string, decision: Decision) => post<ReviewItem>(`/api/review-items/${id}/resolve`, { note, decision }),
  resolveBatch: (ids: number[], note: string, decision: Decision) => post<ReviewItem[]>("/api/review-items/resolve-batch", { ids, note, decision }),
  report: (pid: string) => get<Report>(`/api/participants/${encodeURIComponent(pid)}/report`),
  change: (pid: string, includeDoubtful = false) =>
    get<ChangeResult[]>(`/api/participants/${encodeURIComponent(pid)}/change${includeDoubtful ? "?include_doubtful=true" : ""}`),
  audit: (pid: string) => get<AuditRow[]>(`/api/participants/${encodeURIComponent(pid)}/audit`),

  clinicianParticipants: () => get<ClinicianParticipant[]>("/api/clinician/participants"),
  familyShared: () => get<FamilyEntry[]>("/api/family/shared"),
};
