import asyncio
from hashlib import sha256
import json
import os
from pathlib import Path
import sys
from tempfile import NamedTemporaryFile

from cyberlab_ipc import MAX_SUBMISSION_BYTES


def add_parser(commands):
    submit = commands.add_parser("submit", help="Save, export declared evidence, then stop the unchanged Session")
    submit.add_argument("id", help="Running Session ID")
    submit.add_argument("output", type=Path, help="New .cyberlab-submission.zip path; never overwritten")
    finish = commands.add_parser("finish-submission", help="Retry ending a Session after its submission was saved")
    finish.add_argument("id", help="Session ID")
    finish.add_argument("report", help="Previously prepared and exported report ID")
    finish.add_argument("--yes", action="store_true", help="Confirm the exported submission is safely saved")


def prepare(arguments):
    if arguments.command == "submit" and os.path.lexists(arguments.output):
        raise ValueError("Submission destination already exists; choose a new filename")
    if arguments.command == "finish-submission" and not arguments.yes:
        raise ValueError("Pass --yes only after confirming the exported submission is safely saved")


def write_submission(destination, data):
    if not isinstance(data, bytes) or len(data) > MAX_SUBMISSION_BYTES:
        raise ValueError("Invalid submission archive")
    destination = Path(destination).absolute()
    with NamedTemporaryFile(prefix=".cyberlab-submission-", dir=destination.parent) as output:
        output.write(data)
        output.flush()
        os.fsync(output.fileno())
        os.link(output.name, destination)
        descriptor = os.open(destination.parent, os.O_RDONLY | os.O_DIRECTORY | os.O_CLOEXEC)
        try:
            os.fsync(descriptor)
        finally:
            os.close(descriptor)
    return {"destination": str(destination), "bytes": len(data), "sha256": sha256(data).hexdigest()}


async def run(bus, request, arguments):
    if arguments.command == "finish-submission":
        return await request(bus, "FinalizeSubmission", [arguments.id, arguments.report])
    report = json.loads(await request(bus, "PrepareSubmission", [arguments.id]))
    identifier = report["id"]
    data = await request(bus, "ExportSubmission", [identifier])
    try:
        receipt = write_submission(arguments.output, data)
    except OSError as error:
        raise RuntimeError(f"Submission was not finalized: {error}. Session was not stopped; "
                           f"report {identifier} and its checkpoint remain available") from error
    try:
        session = await request(bus, "FinalizeSubmission", [arguments.id, identifier])
        if session.get("state") != "STOPPED":
            raise RuntimeError(session.get("error") or "Session cleanup is incomplete")
    except (Exception, asyncio.CancelledError) as error:
        message = (
            f"Submission saved to {receipt['destination']}, but completion was not confirmed: {error}. "
            f"Inspect Session {arguments.id}; retry with cyberlab finish-submission "
            f"{arguments.id} {identifier} --yes only after confirming the saved file")
        if isinstance(error, asyncio.CancelledError):
            print("FAIL: " + message, file=sys.stderr)
            raise
        raise RuntimeError(message) from error
    return {**session, "submission": {"report_id": identifier, **receipt}}
