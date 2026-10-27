# Technical Documentation

Start with the architecture and installation guides. The remaining files describe
active contracts, workflows and explicit limitations, not development progress.

The optional test suite and example Labs are not shipped in this checkout.
References to regression test files or old sample-based verification in feature
notes describe the archived development kit, not commands available after a
fresh clone. Use the installation guide for current install/update commands;
legacy MVP/demo/OVA tools have also been archived outside the checkout. They
must not substitute the production catalog for missing fixtures.

## Architecture and Operation

| Guide | Contents |
| --- | --- |
| [Engine boundaries](engine-package-boundaries.md) | Components, dependencies and data ownership. |
| [Installation](install-mvp.md) | Host prerequisites, launchers and guarded runtime updates. |
| [Studio](quickshell-studio.md) | Library, practice and basic Lab editing. |
| [Studio source](studio-structure.md) | QML components, responsive layout, fonts and packaging. |
| [External catalog](external-lab-catalog.md) | Persistent Labs outside the source repository. |

## Labs and Sessions

| Guide | Contents |
| --- | --- |
| [Authoring](lab-authoring.md) | Private drafts, assets, revisions and publication. |
| [Home files](home-file-placement.md) | Template assets and their destinations in each node. |
| [Documents and imports](documents-imports.md) | Instructions and bounded workspace transfers. |
| [Networks and terminals](network-terminal-configuration.md) | Private networks, addresses, DNS and terminal slots. |
| [Node environments](node-environments.md) | Accounts, shells, hostnames and image constraints. |
| [Terminal windows](terminal-windows.md) | Opening, attaching and closing configured terminals. |
| [Saved practice](saved-practice.md) | Checkpoints, suspend/resume and destructive reset. |
| [Lab deletion](lab-deletion.md) | Confirmation, authorization and active-Session guards. |
| [Lab packages](lab-packages.md) | Bounded import/export and Labtainer conversion limits. |

## Optional Features and Limits

| Guide | Contents |
| --- | --- |
| [Checkwork](checkwork-and-quiz.md) | Self-checks, evidence and submission workflows. |
| [Quiz](lab-quiz.md) | Groups, attempts and pre-start preparation gates. |
| [Parameters](parameterization.md) | Deterministic values and substitutions. |
| [Results and goals](results-goals-parity.md) | Supported operators and evaluation boundaries. |
| [Labedit inventory](labedit-parity.md) | Full feature inventory and known gaps. |
| [Remaining work](labedit-completion-plan.md) | Unfinished behavior and required acceptance gates. |
| [Offline packaging](offline-images-and-studio.md) | Historical image/OVA design; old release tools are archived, not the current installer. |

The authoritative definition schema is
[`schemas/v1/lab.schema.json`](../schemas/v1/lab.schema.json). Shared D-Bus method
signatures are in
[`daemon/cyberlab_ipc/org.ptit.CyberLab1.xml`](../daemon/cyberlab_ipc/org.ptit.CyberLab1.xml).
Development and security constraints remain in [`AGENTS.md`](../AGENTS.md).
