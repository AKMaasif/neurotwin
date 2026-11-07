# Account session security

Mobile **Settings → Your session → Other signed-in sessions** and dashboard **Account security** now expose self-service session summary and confirmed revocation. The same panel is available in the no-active-patient workspace state; account security does not depend on having patient access.

`GET /api/account/sessions` returns only the current session expiry and the number of other unexpired sessions for the authenticated account. It exposes no session IDs/hashes, bearer tokens, CSRF tokens, usernames of other users, IP addresses or invented device names. Multiple sessions may belong to one physical device. The count is a snapshot refreshed explicitly, not a device inventory or presence feed.

`POST /api/account/sessions/revoke-others` requires normal authentication, CSRF and expected-actor enforcement. It deletes only other unexpired sessions belonging to that account, preserves the requesting session and returns the actual revoked count. Repeating it is naturally idempotent when no new sessions have been created. Other accounts remain unaffected. Expired rows are excluded; this feature is not a general database cleanup job.

In PostgreSQL, sign-in and revocation acquire the same User-row lock to order those operations. Revocation re-queries its caller's session after acquiring the lock, preventing a waiting caller that was just revoked from deleting the successful caller's session. A concurrent pair of revocations therefore leaves one valid session. SQLite development mode does not provide equivalent PostgreSQL row-lock semantics.

Both shared JSON API clients and the camera image request clear active private views/capture state and return to sign-in when an authenticated request receives HTTP 401. Previously admitted in-flight server work, already downloaded files and data retained outside the current view cannot be recalled. This is not instantaneous remote erasure, password rotation or protection against later sign-ins using valid credentials. Real enrollment, recovery, MFA, dedicated authentication-event auditing and production identity operations remain separate outstanding work.

No new schema, dependencies, password changes, patient records or clinical permissions were introduced. The existing design and current-session sign-out remain intact. Revocation tests run only on fresh isolated synthetic fixtures, not on the user's active development sessions.

## Verification

Tests were written first and reproduced the missing API. The initial account-session/workflow regression run passed 40 checks across SQLite/PostgreSQL. The final account-session partition passed **13 checks with one expected SQLite concurrency skip**, covering redacted summaries, account isolation, CSRF/actor checks, expiry, current-session preservation, repeat revocation, subsequent new sign-ins, missing patient access and concurrent PostgreSQL revocations. The runs overlap; their counts must not be summed as independent tests. Final results: ignored `test-results/account-session-tests.xml`.

The new isolated browser script passed **7 scenarios** across independent browser contexts: mobile summary, cancelled/confirmed revocation and unaffected users, revoked-view cleanup, responsive/enlarged-text controls, clinical dashboard behavior, failure/retry and no-patient access. Core, companion, care-page, clinical-design and camera browser flows also passed after integration. Reports/screenshots are under ignored `test-results/account-sessions/`; the clinical screenshot was visually inspected. Formatting, Ruff and whitespace checks pass. Physical-device/security review and production operation are not certified by these local synthetic checks.
