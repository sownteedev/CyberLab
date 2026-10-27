import argparse
import asyncio
import json
import os
from pathlib import Path
import sys

from dbus_next import BusType, Message, MessageType, Variant
from dbus_next.aio import MessageBus

from cyberlab_ipc import BUS_NAME, INTERFACE, METHODS, OBJECT_PATH


class ClientError(Exception):
    pass


def unpack(value):
    if isinstance(value, Variant):
        return unpack(value.value)
    if isinstance(value, dict):
        return {key: unpack(item) for key, item in value.items()}
    if isinstance(value, list):
        return [unpack(item) for item in value]
    return value


async def request(bus, method, body):
    signature, expected = METHODS[method]
    response = await asyncio.wait_for(bus.call(Message(
        destination=BUS_NAME, path=OBJECT_PATH, interface=INTERFACE,
        member=method, signature=signature, body=body,
    )), timeout=180)
    if response.message_type == MessageType.ERROR:
        raise ClientError(f"{response.error_name}: {response.body[0] if response.body else 'Request failed'}")
    if response.signature != expected:
        raise ClientError("Unexpected daemon response signature")
    return unpack(response.body[0])


async def run(arguments):
    if arguments.command in {"submit", "finish-submission"}:
        from . import submissions

        submissions.prepare(arguments)
    if arguments.command == "delete-lab" and not getattr(arguments, "yes", False):
        raise ClientError("Deletion is permanent; pass --yes to confirm the selected Lab")
    if arguments.command in {"discard", "delete-report", "delete-lab-quiz"} and not getattr(arguments, "yes", False):
        raise ClientError("Permanent deletion requires --yes")
    if arguments.command == "lab-quiz" and arguments.answers and not arguments.digest:
        raise ClientError("Lab quiz submission requires --digest from cyberlab lab-quiz LAB")
    imported = None
    prepared = None
    package_data = None
    workspace_commands = {"files", "import-folder", "export-file", "export-folder"}
    if arguments.command in workspace_commands:
        from . import workspace

        prepared = workspace.prepare(arguments)
    if arguments.command == "draft":
        from . import drafts

        prepared = drafts.prepare(arguments)
    if arguments.command == "import-file":
        from .files import read_import

        imported = read_import(arguments.file, arguments.name)
    if arguments.command in {"export-lab", "export-draft"} and os.path.lexists(arguments.output):
        raise ClientError("Export destination already exists; choose a new filename")
    if arguments.command == "import-lab":
        from .packages import read_package

        package_data = read_package(arguments.file)
    if arguments.command == "import-labtainer":
        from .packages import read_labtainer

        package_data = read_labtainer(arguments.file)
    if arguments.command == "review-submissions":
        from .packages import read_submissions

        package_data = read_submissions(arguments.files)
    if arguments.command == "export-submission" and arguments.output.exists():
        raise ClientError("Export destination already exists; choose a new filename")
    bus = await MessageBus(bus_type=BusType.SESSION if arguments.test_session_bus else BusType.SYSTEM).connect()
    try:
        if arguments.command in {"submit", "finish-submission"}:
            return await submissions.run(bus, request, arguments)
        if arguments.command in workspace_commands:
            return await workspace.run(bus, request, arguments, prepared)
        if arguments.command == "draft":
            return await drafts.run(bus, request, arguments, prepared)
        if arguments.command == "docs":
            method = "GetSessionDocumentation" if arguments.session else "GetLabDocumentation"
            return await request(bus, method, [arguments.id])
        if arguments.command == "import-file":
            name, data = imported
            return await request(bus, "ImportFile", [arguments.id, arguments.node, name, data])
        if arguments.command == "checkwork":
            return json.loads(await request(bus, "CheckWork", [arguments.id]))
        if arguments.command == "reports":
            return json.loads(await request(bus, "ListCheckReports", [arguments.id or ""]))
        if arguments.command == "report":
            return json.loads(await request(bus, "GetCheckReport", [arguments.id]))
        if arguments.command == "delete-report":
            return await request(bus, "DeleteCheckReport", [arguments.id])
        if arguments.command == "export-submission":
            data = await request(bus, "ExportSubmission", [arguments.id])
            from .workspace import write_export

            return write_export(arguments.output, data)
        if arguments.command == "export-lab":
            data = await request(bus, "ExportLabPackage", [arguments.id])
            from .workspace import write_export

            return write_export(arguments.output, data)
        if arguments.command == "export-draft":
            data = await request(bus, "ExportDraftPackage", [arguments.id, arguments.revision])
            from .workspace import write_export

            return write_export(arguments.output, data)
        if arguments.command == "import-lab":
            return json.loads(await request(bus, "ImportLabPackage", [
                package_data, arguments.target_lab_id or "", arguments.title or ""
            ]))
        if arguments.command == "import-labtainer":
            return json.loads(await request(bus, "ImportLabtainer", [
                package_data, arguments.target_lab_id or "", arguments.title or ""
            ]))
        if arguments.command == "review-submissions":
            return json.loads(await request(bus, "ReviewSubmissions", [package_data]))
        if arguments.command == "delete-lab-quiz":
            return await request(bus, "DeleteLabQuizAttempt", [arguments.id])
        if arguments.command == "lab-quiz" and not arguments.digest:
            return json.loads(await request(bus, "GetLabQuiz", [arguments.id]))
        if arguments.command in {"quiz", "lab-quiz"}:
            answers = {}
            for item in arguments.answers:
                if "=" not in item:
                    raise ClientError("Quiz answers must use question-id=option-index")
                identifier, value = item.split("=", 1)
                if not identifier or identifier in answers:
                    raise ClientError("Quiz question IDs must be unique and non-empty")
                try:
                    answers[identifier] = int(value)
                except ValueError:
                    raise ClientError("Quiz option indexes must be integers") from None
            payload = json.dumps(answers, ensure_ascii=True)
            if arguments.command == "lab-quiz":
                return json.loads(await request(bus, "SubmitLabQuiz", [arguments.id, arguments.digest, payload]))
            return json.loads(await request(bus, "SubmitQuiz", [arguments.id, payload]))
        if arguments.command == "quiz-result":
            return json.loads(await request(bus, "GetQuizAttempt", [arguments.id]))
        if arguments.command == "start" and getattr(arguments, "parameters", None):
            values = {}
            for item in arguments.parameters:
                if "=" not in item:
                    raise ClientError("Parameters must use id=value")
                key, value = item.split("=", 1)
                if not key or key in values:
                    raise ClientError("Parameter IDs must be unique and non-empty")
                values[key] = value
            return await request(bus, "StartLabWithParameters", [arguments.id, values])
        if arguments.command == "terminal":
            from .terminal import interact

            return await interact(bus, request, arguments.id, arguments.node, arguments.slot)
        if arguments.command == "info":
            return {
                "version": await request(bus, "GetVersion", []),
                "capabilities": await request(bus, "GetCapabilities", []),
            }
        methods = {
            "labs": "ListLabs", "show": "GetLab", "delete-lab": "DeleteLab", "start": "StartLab",
            "sessions": "ListSessions", "status": "GetSession",
            "stop": "StopSession", "reset": "ResetSession",
            "save": "SaveSession", "suspend": "SuspendSession", "resume": "ResumeSession",
            "discard": "DiscardSessionCheckpoint",
            "imports": "ListImports",
            "open-terminals": "GetSession",
        }
        body = [arguments.id] if hasattr(arguments, "id") else []
        return await request(bus, methods[arguments.command], body)
    finally:
        bus.disconnect()


def main():
    parser = argparse.ArgumentParser(description="CyberLab CLI: all operations go through cyberlabd")
    parser.add_argument("--test-session-bus", action="store_true", help="Use the isolated test bus, not production")
    commands = parser.add_subparsers(dest="command", required=True)
    from .submissions import add_parser as add_submission_parser

    add_submission_parser(commands)
    from .drafts import add_parser

    add_parser(commands)
    from .workspace import add_parser as add_workspace_parser

    add_workspace_parser(commands)
    for name in ("info", "labs", "sessions"):
        commands.add_parser(name)
    for name in ("show", "status", "stop", "reset", "imports", "save", "suspend"):
        commands.add_parser(name).add_argument("id")
    resume_cmd = commands.add_parser("resume", help="Resume a suspended or saved practice Session")
    resume_cmd.add_argument("id")
    resume_cmd.add_argument("--no-terminals", action="store_true", help="Resume the Session without opening configured terminal windows")
    discard = commands.add_parser("discard", help="Delete only the saved checkpoint; a running Session is not stopped")
    discard.add_argument("id", help="Session ID")
    discard.add_argument("--yes", action="store_true", help="Confirm permanent deletion of saved progress")
    checkwork = commands.add_parser("checkwork", help="Check the current workspace against the Lab criteria")
    checkwork.add_argument("id", help="Running Session ID")
    reports = commands.add_parser("reports", help="List saved Checkwork reports")
    reports.add_argument("id", nargs="?", help="Optional Session ID filter")
    report = commands.add_parser("report", help="Read one saved Checkwork report")
    report.add_argument("id", help="Checkwork report ID")
    exported = commands.add_parser("export-submission", help="Export one saved Checkwork report and declared artifacts")
    exported.add_argument("id", help="Checkwork report ID")
    exported.add_argument("output", type=Path, help="New .cyberlab-submission.zip path")
    deleted_report = commands.add_parser("delete-report", help="Delete one saved Checkwork report")
    deleted_report.add_argument("id", help="Checkwork report ID")
    deleted_report.add_argument("--yes", action="store_true", help="Confirm permanent deletion")
    exported_lab = commands.add_parser("export-lab", help="Export an installed Lab as a bounded offline .cyberlab package")
    exported_lab.add_argument("id", help="Installed Lab ID")
    exported_lab.add_argument("output", type=Path, help="New .cyberlab package path")
    exported_draft = commands.add_parser("export-draft", help="Export a private draft as a bounded offline .cyberlab package")
    exported_draft.add_argument("id", help="Draft ID")
    exported_draft.add_argument("output", type=Path, help="New .cyberlab package path")
    exported_draft.add_argument("--revision", type=int, required=True)
    imported_lab = commands.add_parser("import-lab", help="Import an offline .cyberlab package into a private draft")
    imported_lab.add_argument("file", type=Path, help="Local .cyberlab package")
    imported_lab.add_argument("--as", dest="target_lab_id", help="Optional new Lab ID")
    imported_lab.add_argument("--title", help="Optional new Lab title")
    imported_lt = commands.add_parser("import-labtainer", help="Convert supported Labtainer content to a private draft requiring image/account review")
    imported_lt.add_argument("file", type=Path, help="Local Labtainer lab directory, .zip, .tar, .tar.gz or .tgz archive")
    imported_lt.add_argument("--as", dest="target_lab_id", help="Optional new Lab ID")
    imported_lt.add_argument("--title", help="Optional new Lab title")
    review = commands.add_parser("review-submissions", help="Review exported submissions without changing Labs or Sessions")
    review.add_argument("files", nargs="+", type=Path, help="One or more .cyberlab-submission.zip files")
    quiz = commands.add_parser("quiz", help="Submit answers for a Session quiz")
    quiz.add_argument("id", help="Session ID")
    quiz.add_argument("--answer", dest="answers", action="append", default=[], metavar="QUESTION=INDEX")
    quiz_result = commands.add_parser("quiz-result", help="Read the last saved quiz result")
    quiz_result.add_argument("id", help="Session ID")
    lab_quiz = commands.add_parser("lab-quiz", help="Read or answer a Lab quiz without starting containers")
    lab_quiz.add_argument("id", help="Lab ID")
    lab_quiz.add_argument("--digest", help="Exact lab_digest returned when reading the quiz; enables submission")
    lab_quiz.add_argument("--answer", dest="answers", action="append", default=[], metavar="QUESTION=INDEX")
    deleted_quiz = commands.add_parser("delete-lab-quiz", help="Forget your preparation answers, not Session answers or reports")
    deleted_quiz.add_argument("id", help="Lab ID")
    deleted_quiz.add_argument("--yes", action="store_true", help="Confirm deletion of your saved Lab quiz attempt")
    deletion = commands.add_parser("delete-lab", help="Permanently delete a Lab after all of its Sessions are stopped")
    deletion.add_argument("id", help="Lab ID, never a filesystem path")
    deletion.add_argument("--yes", action="store_true", help="Confirm permanent deletion of this Lab and its assets")
    start = commands.add_parser("start")
    start.add_argument("id")
    start.add_argument("--no-terminals", action="store_true", help="Start the Session without opening configured terminal windows")
    start.add_argument("--param", dest="parameters", action="append", default=[], metavar="ID=VALUE",
                       help="Override one declared Lab parameter; may be repeated")
    terminal = commands.add_parser("terminal", help="Attach to a node shell through cyberlabd")
    terminal.add_argument("id", help="Session ID, not Lab ID")
    terminal.add_argument("node", help="Node ID declared in the Lab")
    terminal.add_argument("--slot", type=int, default=0, choices=range(4), help="Independent shell slot, numbered from 0 (default)")
    windows = commands.add_parser("open-terminals", help="Open tracked desktop windows for an existing Session")
    windows.add_argument("id", help="Session ID")
    windows.add_argument("--node", help="Open one node slot instead of all auto-open slots")
    windows.add_argument("--slot", type=int, choices=range(4), help="Slot number; requires --node")
    docs = commands.add_parser("docs", help="Read packaged Markdown through cyberlabd")
    docs.add_argument("id", help="Lab ID, or Session ID with --session")
    docs.add_argument("--session", action="store_true", help="Read the captured documentation of your Session")
    docs.add_argument("--json", action="store_true", help="Print metadata and content as JSON")
    imported = commands.add_parser("import-file", help="Copy one local file into a running node without host mounts")
    imported.add_argument("id", help="Session ID")
    imported.add_argument("node", help="Declared node ID")
    imported.add_argument("file", help="Regular file readable by the current host user, at most 256 KiB")
    imported.add_argument("--name", help="Safe display filename; a unique destination is generated, never overwritten")
    arguments = parser.parse_args()
    if arguments.command == "delete-lab" and not arguments.yes:
        parser.error("delete-lab requires --yes; the Lab and its assets will be permanently removed")
    if arguments.command == "discard" and not arguments.yes:
        parser.error("discard requires --yes; the saved checkpoint will be permanently removed")
    if arguments.command == "delete-report" and not arguments.yes:
        parser.error("delete-report requires --yes; pass --yes to confirm permanent deletion")
    if arguments.command == "delete-lab-quiz" and not arguments.yes:
        parser.error("delete-lab-quiz requires --yes; your preparation answers will be removed")
    if arguments.command == "lab-quiz" and arguments.answers and not arguments.digest:
        parser.error("lab-quiz --answer requires --digest from cyberlab lab-quiz LAB")
    if arguments.command == "draft" and arguments.draft_action == "update" and not arguments.yes:
        parser.error("draft update requires --yes after reviewing the draft and installed Lab digests")
    if arguments.command == "open-terminals" and arguments.slot is not None and arguments.node is None:
        parser.error("--slot requires --node")
    try:
        result = asyncio.run(run(arguments))
    except TimeoutError:
        if arguments.command in {"lab-quiz", "delete-lab-quiz"}:
            print(f"FAIL: Request timed out; run cyberlab lab-quiz {arguments.id} to inspect your saved answers before retrying", file=sys.stderr)
        elif arguments.command == "delete-lab":
            print("FAIL: Request timed out; inspect cyberlab labs before retrying; deletion may have completed", file=sys.stderr)
        elif arguments.command == "draft":
            print("FAIL: Request timed out; inspect drafts and catalog before retrying. Saving or publishing may have completed", file=sys.stderr)
        elif arguments.command == "import-lab":
            print("FAIL: Request timed out; inspect cyberlab draft list before retrying; import may have completed", file=sys.stderr)
        elif arguments.command in {"import-file", "import-folder"}:
            print(f"FAIL: Request timed out; run cyberlab imports {arguments.id} before retrying; the import may still complete", file=sys.stderr)
        else:
            print("FAIL: Request timed out; inspect sessions before retrying start", file=sys.stderr)
        return 1
    except (KeyboardInterrupt, asyncio.CancelledError):
        return 130
    except Exception as error:
        print(f"FAIL: {error}", file=sys.stderr)
        return 1
    if arguments.command == "terminal":
        return 0
    if arguments.command == "draft" and arguments.draft_action == "show" and arguments.definition:
        from .files import terminal_text

        text = result["definition"]
        print(terminal_text(text) if sys.stdout.isatty() else text, end="" if text.endswith("\n") else "\n")
        return 0
    if arguments.command == "docs" and not arguments.json:
        from .files import terminal_text

        print(terminal_text(result["content"]), end="" if result["content"].endswith("\n") else "\n")
        return 0
    print(json.dumps(result, indent=2, ensure_ascii=True), flush=True)
    expected_states = {"stop": "STOPPED", "reset": "RUNNING", "suspend": "SUSPENDED",
                       "submit": "STOPPED", "finish-submission": "STOPPED"}
    if arguments.command in expected_states and isinstance(result, dict) and result.get("id") == arguments.id and result.get("state") == expected_states[arguments.command]:
        from .windows import close_terminals

        try:
            closed = close_terminals(arguments.id, True) if arguments.test_session_bus else close_terminals(arguments.id)
        except (OSError, ValueError):
            closed = 0
            print("WARNING: Session updated, but window cleanup failed; close its windows manually.", file=sys.stderr)
        if closed:
            suffix = "window" if closed == 1 else "windows"
            print(f"Requested closure of {closed} terminal {suffix} for Session {arguments.id}.", file=sys.stderr)
    if arguments.command == "open-terminals":
        from .windows import launch_terminals

        try:
            if result.get("state") != "RUNNING":
                raise RuntimeError("Session is not running")
            launch_terminals(result, arguments.test_session_bus, interactive=False,
                             node_id=arguments.node, slot=arguments.slot or 0)
        except (OSError, ValueError, RuntimeError) as error:
            print(f"FAIL: {error}", file=sys.stderr)
            return 1
    if arguments.command in ("start", "resume") and not getattr(arguments, "no_terminals", False):
        from .windows import launch_terminals

        launch_terminals(result, arguments.test_session_bus)
    return 1 if isinstance(result, dict) and (result.get("state") == "FAILED" or result.get("valid") is False or result.get("ready") is False) else 0


if __name__ == "__main__":
    raise SystemExit(main())
