# Verified password change

Mobile **Settings → Your session → Other signed-in sessions → Change password** and dashboard **Account security → Other signed-in sessions → Change password** now support changing the authenticated account's password. The same account panel is reachable when no patient workspace is assigned.

Enter the current password, a new passphrase and matching confirmation. The UI states that the operation signs out all sessions, including the requesting session, and asks for explicit confirmation describing unsent-draft loss. Cancelling or mismatched confirmation sends no credential-change request. After a submitted attempt, password fields are reset. Success clears current private view/capture state, informs same-browser tabs through the existing session channel and returns to sign-in with the account selected. No password is copied into application state, logs, local storage, notifications or report files by this feature.

## API and transaction

`POST /api/account/password` accepts JSON with exactly `current_password` and `new_password`. It uses existing authenticated cookie, CSRF and optional expected-actor mismatch checks; the target account always comes from the session. Current password is required, new password must be different, and the project policy is 15–300 characters with all-whitespace values rejected. Spaces and valid Unicode are preserved exactly; there are no automatic trimming, composition rules or silent truncation. Invalid UTF-8/unpaired-surrogate inputs are rejected with the same fixed validation message. Input/reference values are never included in error responses.

The route deliberately validates the JSON body locally rather than using FastAPI's default body error projection, which can echo invalid input. The body is limited to 16 KB before parsing, with existing middleware counting bytes even without Content-Length. Reauthentication attempts are limited to five per minute per client host/account in the existing in-process limiter. This is not a distributed or persistent rate-limit service.

Password verification, hashing and database work run in a thread pool. The transaction uses the same PostgreSQL account-row lock as sign-in/session revocation, reloads current account data and rechecks the requesting session after acquiring the lock. It verifies the old password, writes a new salted hash through the existing scrypt helper and removes all sessions for that account atomically. Only after commit is the response cookie cleared. Other accounts, patient permissions and medical records are untouched. A replay after success fails authentication. This is not an idempotent command receipt or a password-reset endpoint.

The browser test exposed a background-refresh race: shared HTTP-401 handling had already cleared the account before an older mobile refresh catch tried to read its ID. Both refresh loops now capture and recheck account/workspace identity. The mobile asynchronous cleanup also rechecks after awaits, preventing stale cleanup from dereferencing a signed-out account or clearing a newly signed-in workspace.

## Verification

Tests were written first and reproduced the missing route. The password/session regression partition passed **36 checks with two expected SQLite concurrency skips**. A final validation partition passed **16 checks**, overlapping 12 earlier cases and adding four malformed-Unicode cases, for **40 distinct passing checks across the overlapping runs**. The PostgreSQL concurrency cases passed; SQLite does not claim PostgreSQL row-lock semantics. Reports: ignored `test-results/password-change-tests.xml` and `password-validation-tests.xml`.

Cases cover wrong current password, unchanged password, malformed/type/length/blank/unknown-field validation without secret reflection, CSRF/actor/authentication checks, body bounds, throttling, exact Unicode/space handling, other-account isolation, atomic concurrent password changes, invalidation of current/other sessions, and old/new-password sign-in behavior.

The new isolated browser flow passed **five scenarios** for mismatch/cancellation, safe error/field clearing, responsive/enlarged-text forms, full mobile change/re-login and the clinical flow. It waits for the revoked client's background refresh to return to sign-in without page errors. Existing account-session, core, companion, care-page and clinical-design flows also passed. Reports/screenshots are under ignored `test-results/password-change/`. All credential mutations in automated testing use fresh isolated synthetic accounts; no active development account password is changed by tests. Repository formatting, Ruff and whitespace checks pass.

## Limits and operation

The development seed creates initial credentials from server configuration. A later password change updates the database and does not rewrite `.env` or make its initial password valid again. Login copy distinguishes initial and current credentials. Developers should run browser checks through the isolated runner so their fixtures use their own seed credentials.

Real enrollment, forgotten-password recovery, MFA, compromised-password screening, authentication-event audit/notification delivery, distributed rate limiting, production password-hash policy review and operational security validation remain outstanding. This feature is not production identity certification. Existing production HTTPS enforcement remains in place; the loopback development server is not a public deployment. No GitHub push is part of this implementation cycle.

Current-password verification and reauthentication follow the relevant design principles in the primary [OWASP Authentication Cheat Sheet](https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html#change-password-feature). This reference is not a claim of complete OWASP compliance.
