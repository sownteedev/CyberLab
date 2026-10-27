# Configured Node Environments (0.6.0)

## Scope and Status

Nodes can now declare their own real container account, hostname, home, and
terminal shell. This is not a cosmetic prompt alias and never creates a user
on the Ubuntu host. CLI → System D-Bus → cyberlabd → engine → Docker remains
unchanged. Quickshell, assessment, login services, arbitrary image builds, and
root terminals are not added.

The user confirmed the 0.5.0 initial-files verifier and manual VM checks.
The user subsequently supplied a 0.6.0 screenshot confirming the client's real
Alice UID/GID, hostname, home, prompt and initial files. This does not by itself
prove server/reset acceptance; the administrator verifier remains the complete
check. Version 0.7.0 reuses this image for docs/import; see `documents-imports.md`.
MemoryRuntime remains a test double, not a shell or Linux account database.

## Node Configuration

The separate `labs/demo-users/lab.yaml` sample includes:

```yaml
- id: client
  hostname: workstation
  image: cyberlab/demo-users:0.6.0
  command: ["sleep", "3600"]
  networks: [lan]
  user:
    name: alice
    uid: 2000
    gid: 2000
    home: /home/alice
    shell: /bin/sh
  files:
    - source: assets/client
      target: exercises
```

Its terminal begins in `/home/alice` and shows `alice@workstation:~$`.
The second node is `bob@fileserver:~$`, with UID/GID 2001 and `/home/bob`.
Initial files are in `~/exercises/message.txt` for Alice and
`~/data/banner.txt` for Bob. These subdirectories are explicitly declared by
the example mappings; a target of `message.txt` goes directly into home.
Other files directly in the writable home are
also temporary and disappear on reset or stop.

- `hostname` is optional, defaults to the node ID, and accepts one lowercase
  DNS label (up to 63 characters). It changes the container's actual hostname.
  Network aliases remain node IDs: the client addresses the other node as
  `server`, regardless of its display hostname `fileserver`.
- `user` is optional; if present, all five fields are required. Account names
  use up to 32 lowercase ASCII letters, digits, underscores, or hyphens, starting
  with a letter or underscore. `root` and `nobody` are disallowed here.
- UID and primary GID must be integers from 1000 through 60000, never zero.
  These belong to the container, not the D-Bus caller. Session ownership still
  uses the actual host caller's UID and existing authorization rules.
- Home is restricted to exactly `/home/<name>`; it is not an arbitrary mount
  destination. Shell is restricted to `/bin/sh` or `/bin/bash` and must exist
  and be executable in the approved image. The supplied BusyBox image has sh,
  not bash. Bash support requires an administrator-approved image containing it.
- The image must already contain the declared account in `/etc/passwd`, with
  the matching UID, primary GID, home, and shell. Configuring a name does not
  dynamically run `useradd`. Image preparation is an administrator operation.

Definitions without `user` keep the old UID/GID 65534, shell `/bin/sh`, home
`/tmp`, and initial-files workspace `/tmp/lab`. Existing `demo-basic` and
`demo-files` are not rewritten. To see the new experience, start `demo-users`.
Changing the host catalog does not alter an existing Session's captured model.

## Runtime and Security

The daemon always creates the node and its terminals with numeric non-root
UID:GID. For configured users, a fixed startup check verifies `/etc/passwd`, the
actual `id -un`, numeric UID/GID, home/cwd, and executable shell before executing
the Lab command. A missing or mismatched image account fails startup and uses
the existing Session cleanup; it never falls back to root or a fake username.
Terminal attachment repeats the account check.

Each configured home is a separate 16 MiB tmpfs with the selected UID/GID and
mode 0700, plus `noexec,nosuid,nodev`. The existing 16 MiB `/tmp` tmpfs remains.
Files are copied to `<home>`, using the configured numeric owner, through
the same bounded stdin bootstrap as 0.5.0. Nodes without mappings still finish
environment initialization before the Session becomes RUNNING. File snapshot
quotas and path checks are unchanged. Both tmpfs mounts count toward the node's
128 MiB memory limit; no host bind, volume, or Docker socket is provided.

The root filesystem stays read-only; all capabilities remain dropped, with
no-new-privileges, 64 PIDs, half a CPU, bounded logs, and per-Session internal
networks. Reset recreates containers and mounts while keeping the Session ID
and configured user/hostname/shell, restoring the captured initial data. It
closes old terminals and does not automatically reopen windows.

The engine sets HOME, USER, LOGNAME, SHELL, TERM, and a safe `user@hostname`
PS1 for configured nodes. The shell starts interactively in home. ENV/BASH_ENV
are disabled and bash uses `--noprofile --norc`; this release does not introduce
custom shell initialization hooks. A shell prompt is still editable by its user,
so tests verify real identity rather than treating visible text as authority.

Lab and Session dictionaries add `environments` (`a(sssuuss)`), containing
node ID, hostname, username, UID, GID, home, and shell in that order. The
`node-environment` capability advertises support. Existing `files` metadata
reports the correct destinations under the configured home without exposing
host asset paths or content. No D-Bus methods or new IPC are added.

## Build and Upgrade the Existing VM

As the developer, prepare the offline Python bundle:

```sh
cd /home/student/CyberLab
.venv/bin/python -m pytest -q
.venv/bin/python tools/deploy_mvp.py build dist/mvp-users-0.6.0
.venv/bin/python tools/deploy_mvp.py check dist/mvp-users-0.6.0
```

If the bundle already exists, run only `check`. Use this new bundle with the
current deployment tool; older bundles do not include the new sample/recipe.

**Save needed data first: stopping the daemon terminates every current Session
and discards its temporary files.** The following is a separately approved
administrator action, not something performed by the coding session:

```sh
sudo systemctl disable --now cyberlabd.service &&
sudo /usr/bin/python3 -I tools/deploy_mvp.py repair dist/mvp-users-0.6.0 --uid "$(id -u)" --install-demo-users
```

This opt-in repair validates the staged Lab and prepares only the fixed recipe
in `tools/images/demo-users/Dockerfile`. The recipe creates locked-password
Alice/Bob accounts at image-build time, not in the host or a running lab.
It uses preloaded `busybox:1.37.0`, Docker Buildx's default builder, `--load`,
`--pull=false`, and network-disabled build steps; no package downloads are used.
The runtime daemon and CLI never build images. A conflicting existing image
tag or customized sample is rejected instead of overwritten.

The repair installs only `demo-users` and appends only its fixed image tag to
the existing allowlist. Other allowlisted images and allowed host UIDs are
preserved. The three-key daemon config is serialized again (comments are not
preserved); a byte-for-byte previous config is retained in the root-private
staging directory. Nonstandard catalog paths and malformed/hardlinked config
are refused. Service/D-Bus policies, host users/groups, and existing Labs are
not changed. Without the flag, package repair neither builds this image nor
changes the config. Fresh base installs can use this opt-in repair afterward.

The verifier checks actual users/UIDs/GIDs, hostnames, home cwd, shell selection,
visible prompts, writable home tmpfs, file ownership, two-Session isolation,
reset restoration, unchanged source files, and cleanup. If it fails, the service
is not enabled; retain the output and staging directory for review. Do not
blindly rerun, delete resources, or run the initial installer over this VM.

## Manual Acceptance

After `DONE`, as the student:

```sh
cyberlab info
cyberlab show demo-users
cyberlab start demo-users
```

The two configured windows should show `alice@workstation:~$` and
`bob@fileserver:~$`. In the client window:

```sh
whoami
id
hostname
pwd
printf '%s\n' "$HOME" "$SHELL"
cat ~/exercises/message.txt
printf 'edited\n' > ~/exercises/message.txt
touch ~/created
```

Expect `alice`, UID/GID 2000, `workstation`, `/home/alice`, `/bin/sh`, and
`alice-original` before the edit. In the server, `whoami` prints `bob`, `hostname`
prints `fileserver`, and `cat ~/data/banner.txt` prints `bob-original`.

In the host terminal, using the actual Session ID:

```sh
cyberlab reset SESSION_ID
cyberlab terminal SESSION_ID client
```

The prompt and identity must be unchanged, the message must again contain
`alice-original`, and `test ! -e ~/created && echo restored` must print
`restored`. Exit the node shell and use `cyberlab stop SESSION_ID` on the host
when finished. These are disposable environments, not persistent user homes.
