# Studio System Update Implementation Plan

> **Tài liệu lịch sử.** Trạng thái và lệnh bên dưới thuộc lần ghi nhận này,
> không thay thế [hướng dẫn hiện hành](../../README.md).

**Goal:** Move account management below Terminal and expose safe, visible system updates.
**Architecture:** Studio checks through `cyberlab update --check --json`. A detached,
unprivileged updater snapshots its UI/stdlib runner before Studio closes, reuses
the CLI update engine and pkexec for the existing guarded installer. No new
daemon API or updater exemption from maintenance checks.
**Spec:** User-approved flow in this chat on November 25, 2026: notification and
Settings page, separate updater, actual download percentage, indeterminate build,
explicit restart after success. Never discard edits or stop labs automatically.
**Tech Stack:** Python stdlib, Quickshell/QML, existing MD3-style components.

## Constraints and review focus
- Preserve dirty worktree and production data; no deployment without safeguards.
- Automatic checks are read-only and once on opening Studio; offline is quiet.
- Pin the checked commit through installation; validate receipt before success.
- Copy updater resources before replacing runtime; use system Python for runner.
- Authentication cancellation, malformed output, process failure and missing
  pkexec leave Studio open where possible or show actionable failure.
- No fake percentages, embedded passwords, relaxed process guards or auto-restart.

## Tasks
- [x] Test and move the account summary to the Terminal column, responsive layout.
- [x] Add JSON check/progress and GUI authentication to the shared update engine;
  test unknown metadata, no update, failure, bounded download and completion.
- [x] Add detached updater staging/lifetime/handshake and restart handling; test
  with fake processes and private temporary resources, never root installation.
- [x] Add Settings update page, startup notification/badge, unsaved/session guards
  and update confirmation; exercise light/dark/narrow/offline/busy states.
- [x] Run focused regressions, full Studio packaged-QML load and document actual
  evidence and unverified system-install/authentication/GitHub deployment paths.

Evidence and remaining live acceptance: `docs/installation/README.md`.
No system installation, repository push or production-data changes were made.
