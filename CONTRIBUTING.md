# Working on NeuroTwin

## Branches

| Branch | Purpose |
| --- | --- |
| `main` | Always deployable. Only release merges from `develop` land here, each tagged with a version. |
| `develop` | Integration. Finished work is merged here and tested together before a release. |
| `feature/<name>` | New capability, from `develop`. Example: `feature/change-engine` |
| `fix/<name>` | A bug fix, from `develop`. Example: `fix/checkin-skip-default` |
| `docs/<name>` | Documentation only. |
| `chore/<name>` | Tooling, CI, dependencies, deployment. |

No one commits directly to `main` or `develop`.

## A change, start to finish

1. Branch from the latest `develop`.
2. Commit in small, logical steps. Each message says what changed in the imperative ("Add …", "Fix …").
3. Open a pull request into `develop`. Its description says what changed, why, and how it was tested.
4. CI must pass: backend tests (Python 3.10 and 3.12) and the web app build.
5. Merge, then delete the working branch.

## Releases

1. Open a pull request from `develop` into `main` titled `Release vX.Y.Z`, listing what is in it.
2. After merging, tag `main`: `git tag -a vX.Y.Z -m "vX.Y.Z" && git push origin vX.Y.Z`.
3. Deploy from the tag, never from an untagged commit.

Versions: `0.x` while NeuroTwin is a research prototype. A minor bump (`0.2.0`) for new capability, a patch
bump (`0.1.1`) for fixes only.

## Before a pull request

- `cd backend && python -m pytest -q`
- `cd frontend && npm run build`
- Update `docs/STATUS.md` when something moves between implemented, experimental, planned or awaiting approval.
- No real health data, credentials or `.env` files in commits.
