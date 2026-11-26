# Checkwork, difficulty and editing protection

> **Tài liệu lịch sử.** Trạng thái và lệnh bên dưới thuộc lần ghi nhận này,
> không thay thế [hướng dẫn hiện hành](../../README.md).

## Scope and decisions

- Keep Studio -> CLI -> system D-Bus -> daemon -> engine.
- Review Checkwork results, goals, capture failures and saved reports with isolated regressions.
- Optional schema metadata.difficulty: easy / medium / hard. Studio-created labs require a choice. Legacy catalogs remain unchanged and display unclassified.
- Require an editing password for protected labs through the daemon, including drafts, cloning, asset reads, software jobs and draft export.
- Import/run and published-package export do not require an editing password. Protected imports install to the library rather than opening a draft.
- This is application editing authorization, NOT encryption, DRM or a guarantee against a machine administrator or modifications outside CyberLab. Exported packages contain readable definitions and a salted password verifier. A trusted remote assessment service would be required for a stronger adversarial boundary.
- Password settings apply immediately, independently of unsaved lab content. Editing drafts of the same installed lab share its protection; clones have independent protection.
- No catalog migration, production fixtures, system configuration changes or automatic Session termination.

## Implementation ledger

- Baseline: source /home/nguyenthanhson/CyberLab contains earlier uncommitted work; preserved. Initial status recorded in /tmp/cyberlab-nov24-status-before by the preceding execution context.
- Checkwork slice: dedicated evaluator tests/audit in progress.
- Difficulty slice: schema/model/UI tests in progress; main integrates authoring/IPC creation.
- Protection: red tests first (missing module); then daemon authorization, SQLite families/links, scrypt verifier, memory-only UID/resource/version-bound grants, wrong-password throttling and revocation.
- Exchange: v1 remains compatible; protected v2 requires validated protection metadata. Old readers reject v2 rather than interpreting it as unprotected.
- Protected import uses an inaccessible temporary draft under the shared lifecycle lock, records protection before atomic publication, deletes the temporary draft on success or failure.
- Regression coverage includes existing drafts created before locking, password changes, clone independence, software job paths, daemon restart, import failure and v1 compatibility.
- Runtime/packaging checks and deployment status: pending; do not treat source checks as installed-app verification.

## Security and compatibility notes

- Passwords/tokens travel through CLI stdin and D-Bus, not process arguments or persisted UI preferences.
- Verifier algorithm is a fixed bounded scrypt profile (N=131072, r=8, p=1), random 16-byte salt, 32-byte output; constant-time comparison. Import cannot select unbounded KDF parameters.
- Tokens are revoked on editor exit/switch and invalidate on password change; daemon restart loses grants, not draft data. A 12-hour server expiry and bounded grant count limit stale grants if a client dies.
- The database contains protection records independently of lab.yaml, so normal draft saves cannot remove protection.
- Do not downgrade the daemon against a protected database: older runtimes do not enforce this feature. Package v2 guards exchange compatibility, not administrator-controlled runtime downgrades.
- Published export is deliberately allowed for sharing. It is not a secret-content export.
