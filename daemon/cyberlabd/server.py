import asyncio
from dataclasses import asdict
from importlib.resources import files
import logging
import json

from dbus_next import Message, MessageType, Variant

from cyberlab.lab import LabError, LabNotFoundError
from cyberlab.lab.catalog import LabInUseError
from cyberlab.lab.environment import workspace
from cyberlab.lab.networking import bridge_gateway
from cyberlab.policy import PolicyDenied
from cyberlab.quiz import QuizRequired, QuizRevisionChanged, public_questions, requires_pre_start
from cyberlab.runtime import RuntimeFailure
from cyberlab.service import CheckReportNotFound, DocumentationNotFound, SessionBusy, SessionLimit, SessionNotFound
from cyberlab.authoring import DraftConflict, DraftLimit, DraftNotFound
from . import authoring as draft_api
from cyberlab.terminal import TerminalBusy, TerminalNotFound
from cyberlab.workspace import WorkspaceNotFound
from cyberlab.submission_review import MAX_BATCH_BYTES, MAX_BATCH_ITEMS, review_submissions
from cyberlab_ipc import ERROR_PREFIX, INTERFACE, MAX_IMPORT_BYTES, MAX_SUBMISSION_BYTES, MAX_WORKSPACE_UPLOAD, METHODS, OBJECT_PATH, VERSION


def lab_fields(lab, digest=""):
    return {
        **configuration_fields(lab),
        **labedit_fields(lab),
        "id": Variant("s", lab.metadata.id),
        "name": Variant("s", lab.metadata.name),
        "version": Variant("s", lab.metadata.version),
        "digest": Variant("s", digest),
        "nodes": Variant("a(sas)", [[node.id, list(node.networks)] for node in lab.nodes]),
        "networks": Variant("as", [network.id for network in lab.networks]),
        "terminals": Variant("as", list(lab.terminals)),
        "files": Variant("a(sas)", [[node.id, [workspace(node) if mapping.target == "." else workspace(node) + "/" + mapping.target for mapping in node.files]] for node in lab.nodes]),
        "environments": environment_fields(lab),
        "has_documentation": Variant("b", lab.documentation is not None),
    }

def environment_fields(lab):
    return Variant("a(sssuuss)", [
        [node.id, node.hostname or node.id, node.user.name if node.user else "nobody",
         node.user.uid if node.user else 65534, node.user.gid if node.user else 65534,
         node.user.home if node.user else "/tmp", node.user.shell if node.user else "/bin/sh"]
        for node in lab.nodes
    ])


def session_fields(session):
    return {
        **configuration_fields(session.lab),
        **labedit_fields(session.lab),
        "id": Variant("s", session.id),
        "lab_id": Variant("s", session.lab.metadata.id),
        "lab_name": Variant("s", session.lab.metadata.name),
        "lab_version": Variant("s", session.lab.metadata.version),
        "nodes": Variant("a(sas)", [[node.id, list(node.networks)] for node in session.lab.nodes]),
        "networks": Variant("as", [network.id for network in session.lab.networks]),
        "owner_uid": Variant("u", session.owner_uid),
        "state": Variant("s", str(session.state)),
        "created_at": Variant("s", session.created_at),
        "updated_at": Variant("s", session.updated_at),
        "error": Variant("s", session.error),
        "terminals": Variant("as", list(session.lab.terminals)),
        "environments": environment_fields(session.lab),
        "files": Variant("a(sas)", [[node.id, [workspace(node) if mapping.target == "." else workspace(node) + "/" + mapping.target for mapping in node.files]] for node in session.lab.nodes]),
        "has_documentation": Variant("b", session.lab.documentation is not None),
        "checkpoint_at": Variant("s", getattr(session, "checkpoint_at", "")),
        "saved": Variant("b", bool(getattr(session, "checkpoint_at", ""))),
        "resolved_parameters": Variant("a{ss}", {
            key: value for key, value in session.parameters
            if any(parameter.id == key and parameter.public for parameter in session.lab.parameters)
        }),
    }

def configuration_fields(lab):
    counts = {node.id: node.terminal_count for node in lab.nodes}
    return {
        "network_config": Variant("a(sss)", [[network.id, network.subnet or "", bridge_gateway(network) if network.subnet else ""] for network in lab.networks]),
        "addresses": Variant("a(sss)", [[node.id, network_id, address] for node in lab.nodes for network_id, address in node.addresses]),
        "dns": Variant("a(sas)", [[node.id, list(node.dns)] for node in lab.nodes]),
        "terminal_counts": Variant("a(su)", [[node.id, node.terminal_count] for node in lab.nodes]),
        "terminal_slots": Variant("a(su)", [[node_id, slot] for node_id in lab.terminals for slot in range(counts[node_id])]),
        "terminal_metadata": Variant("a(sss)", [[node.id, node.terminal_group or "", node.terminal_title or ""] for node in lab.nodes]),
        "network_aliases": Variant("a(sas)", [[node.id, list(node.aliases)] for node in lab.nodes]),
        "wait_for": Variant("a(sas)", [[node.id, list(node.wait_for)] for node in lab.nodes]),
        "resources": Variant("a(suu)", [[node.id, node.resources.memory_mb, node.resources.cpu_millicores] for node in lab.nodes]),
        "extra_hosts": Variant("a(sas)", [[node.id, [hostname + "=" + address for hostname, address in node.extra_hosts]] for node in lab.nodes]),
        "workspaces": Variant("a(ss)", [[node.id, workspace(node)] for node in lab.nodes]),
        "seed_files": Variant("a(sas)", [[node.id, [entry.path for entry in node.seed if entry.data is not None]] for node in lab.nodes]),
        "seed_directories": Variant("a(sas)", [[node.id, [entry.path for entry in node.seed if entry.data is None]] for node in lab.nodes]),
    }

def labedit_fields(lab):
    return {
        "checkwork_enabled": Variant("b", lab.settings.checkwork),
        "settings": Variant("s", json.dumps({
            "host_home_xfer": lab.settings.host_home_xfer,
            "grade_node": lab.settings.grade_node,
            "collect_documentation": lab.settings.collect_documentation,
            "checkwork": lab.settings.checkwork,
        }, ensure_ascii=True)),
        "parameters": Variant("s", json.dumps([
            {"id": item.id, "type": item.type, "default": item.default,
             "choices": list(item.choices), "description": item.description, "public": item.public}
            for item in lab.parameters if item.public
        ], ensure_ascii=True)),
        "assessment": Variant("s", json.dumps({
            "artifacts": [vars(item) for item in lab.assessment.artifacts],
            "results": [{"id": item.id, "node": item.node, "path": item.path,
                         "operator": item.operator, "description": item.description}
                        for item in lab.assessment.results],
            "goals": [{"id": item.id, "type": item.goal_type, "results": list(item.results),
                       "mode": item.mode, "description": item.description,
                       **({"expression": item.expression} if item.expression else {})}
                      for item in lab.assessment.goals],
        }, ensure_ascii=True)),
        "quiz": Variant("s", json.dumps(public_questions(lab.quiz), ensure_ascii=True)),
        "pre_start_quiz": Variant("b", requires_pre_start(lab.quiz)),
    }

def import_fields(record):
    return {key: Variant("u" if key == "size" else "s", value) for key, value in asdict(record).items()}


class Server:
    def __init__(self, bus, engine, allowed_uids, authoring=None):
        self.bus = bus
        self.engine = engine
        self.allowed_uids = allowed_uids
        self.authoring = authoring
        self.tasks = set()
        self.closing = False

    def handle(self, message):
        if message.message_type != MessageType.METHOD_CALL:
            return None
        if message.path != OBJECT_PATH:
            return Message.new_error(message, "org.freedesktop.DBus.Error.UnknownObject", "Unknown object")
        introspect = message.interface == "org.freedesktop.DBus.Introspectable" and message.member == "Introspect"
        contract = ("", "s") if introspect else METHODS.get(message.member)
        if not introspect and message.interface != INTERFACE:
            contract = None
        if contract is None:
            return Message.new_error(message, "org.freedesktop.DBus.Error.UnknownMethod", "Unknown method")
        if message.signature != contract[0]:
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Invalid method signature")
        if message.member in draft_api.METHODS and not draft_api.bounded(message.member, message.body):
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Authoring payload exceeds its limit")
        if message.member == "WriteTerminal" and len(message.body[1]) > 4096:
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Terminal writes are limited to 4096 bytes")
        if message.member == "ImportFile" and (len(message.body[3]) > MAX_IMPORT_BYTES or len(message.body[2]) > 64):
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Import payload or name exceeds its limit")
        if message.member == "ImportWorkspace" and (len(message.body[2].encode("utf-8")) > 128 or len(message.body[3]) > MAX_WORKSPACE_UPLOAD):
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Workspace upload exceeds its limit")
        if message.member == "ReviewSubmissions" and (
                not 1 <= len(message.body[0]) <= MAX_BATCH_ITEMS
                or sum(len(data) for name, data in message.body[0]) > MAX_BATCH_BYTES
                or any(len(name) > 256 or len(data) > MAX_SUBMISSION_BYTES for name, data in message.body[0])):
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Review batch exceeds its limit")
        if message.member == "FinalizeSubmission" and any(not value or len(value) > 64 for value in message.body):
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Submission identifiers exceed their limits")
        if message.member in {"CheckWork", "PrepareSubmission", "ListCheckReports", "GetCheckReport", "DeleteCheckReport", "ExportSubmission", "GetQuizAttempt"} and len(message.body[0]) > 64:
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Report or Session ID exceeds its limit")
        if message.member == "SubmitQuiz" and (len(message.body[0]) > 64 or len(message.body[1].encode("utf-8")) > 256 * 1024):
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Quiz payload exceeds its limit")
        if message.member in {"GetLabQuiz", "DeleteLabQuizAttempt"} and not 1 <= len(message.body[0]) <= 64:
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Invalid Lab quiz identity")
        if message.member == "SubmitLabQuiz" and (
                not 1 <= len(message.body[0]) <= 64 or len(message.body[1]) != 64
                or len(message.body[2].encode("utf-8")) > 256 * 1024):
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Lab quiz payload exceeds its limit")
        if message.member == "StartLabWithParameters" and (len(message.body[0]) > 64 or len(message.body[1]) > 32
                or any(len(key) > 64 or len(value.encode("utf-8")) > 1024 for key, value in message.body[1].items())):
            return Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Lab parameters exceed their limit")
        if self.closing or len(self.tasks) >= 16:
            return Message.new_error(message, f"{ERROR_PREFIX}.Busy", "Service is busy; retry later")
        task = asyncio.create_task(self.reply(message, contract[1], introspect))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)
        return True

    async def caller_uid(self, sender):
        if not sender or not sender.startswith(":"):
            raise PermissionError
        response = await asyncio.wait_for(self.bus.call(Message(
            destination="org.freedesktop.DBus", path="/org/freedesktop/DBus",
            interface="org.freedesktop.DBus", member="GetConnectionUnixUser",
            signature="s", body=[sender],
        )), timeout=5)
        if response.message_type != MessageType.METHOD_RETURN or response.signature != "u":
            raise PermissionError
        uid = response.body[0]
        if uid != 0 and uid not in self.allowed_uids:
            raise PermissionError
        return uid

    def dispatch(self, member, body, uid, sender=None):
        if member in draft_api.METHODS:
            return draft_api.dispatch(self.authoring, member, body, uid)
        if member == "GetVersion":
            return VERSION
        if member == "GetCapabilities":
            return [f"runtime:{self.engine.runtime.name}", "start", "stop", "reset", "delete-lab", "terminal", "terminal-plan", "terminal-slots", "static-networking", "seed-files", "node-environment", "documentation", "import-file", "workspace-files", "volatile-sessions", "parameters", "submission-review"] + (["session-persistence", "discard-checkpoint", "checkwork", "submissions", "submit-and-finish", "quiz", "lab-quiz"] if self.engine.practice_store is not None else []) + (["authoring", "lab-package-export", "lab-package-import", "labtainer-import"] if self.authoring is not None else [])
        if member in {"GetLabDocumentation", "GetSessionDocumentation"}:
            result = self.engine.documentation(body[0], uid, session=member == "GetSessionDocumentation")
            return {key: Variant("s", value) for key, value in result.items()}
        if member == "CheckWork":
            return json.dumps(self.engine.checkwork(body[0], uid), ensure_ascii=True)
        if member == "PrepareSubmission":
            return json.dumps(self.engine.prepare_submission(body[0], uid), ensure_ascii=True)
        if member == "FinalizeSubmission":
            return session_fields(self.engine.finalize_submission(body[0], body[1], uid))
        if member == "ListCheckReports":
            return json.dumps(self.engine.check_reports(uid, session_id=body[0] or None), ensure_ascii=True)
        if member == "GetCheckReport":
            return json.dumps(self.engine.check_report(body[0], uid), ensure_ascii=True)
        if member == "DeleteCheckReport":
            return self.engine.delete_check_report(body[0], uid)
        if member == "ExportSubmission":
            return self.engine.export_submission(body[0], uid)
        if member == "ReviewSubmissions":
            return json.dumps(review_submissions(body[0]), ensure_ascii=True)
        if member == "SubmitQuiz":
            return json.dumps(self.engine.submit_quiz(body[0], json.loads(body[1]), uid), ensure_ascii=True)
        if member == "GetQuizAttempt":
            return json.dumps(self.engine.quiz_attempt(body[0], uid) or {}, ensure_ascii=True)
        if member == "GetLabQuiz":
            return json.dumps(self.engine.lab_quiz(body[0], uid), ensure_ascii=True)
        if member == "SubmitLabQuiz":
            return json.dumps(self.engine.submit_lab_quiz(body[0], body[1], json.loads(body[2]), uid), ensure_ascii=True)
        if member == "DeleteLabQuizAttempt":
            return self.engine.delete_lab_quiz(body[0], uid)
        if member == "ImportFile":
            return import_fields(self.engine.import_file(body[0], body[1], body[2], body[3], uid))
        if member == "ListImports":
            return [import_fields(record) for record in self.engine.imports(body[0], uid)]
        if member == "ListWorkspace":
            return json.dumps(self.engine.list_workspace(body[0], body[1], uid), ensure_ascii=True)
        if member in {"ReadWorkspaceFile", "ExportWorkspace"}:
            return self.engine.export_workspace(body[0], body[1], body[2], uid, file=member == "ReadWorkspaceFile")
        if member == "ImportWorkspace":
            return json.dumps(asdict(self.engine.import_workspace(body[0], body[1], body[2], body[3], uid)), ensure_ascii=True)
        if member == "OpenTerminal":
            return self.engine.open_terminal(body[0], body[1], uid, sender, body[2], body[3])
        if member == "OpenTerminalSlot":
            return self.engine.open_terminal(body[0], body[1], uid, sender, body[3], body[4], slot=body[2])
        terminals = {
            "ReadTerminal": "read", "WriteTerminal": "write",
            "ResizeTerminal": "resize", "CloseTerminal": "close",
        }
        if member in terminals:
            return self.engine.terminal(terminals[member], body[0], uid, sender, *body[1:])
        if member == "ListLabs":
            return [lab_fields(lab) for lab in self.engine.labs()]
        if member == "GetLab":
            return lab_fields(self.engine.lab(body[0]))
        if member == "DeleteLab":
            return self.engine.delete_lab(body[0], uid)
        if member == "ListSessions":
            return [session_fields(session) for session in self.engine.sessions(uid)]
        if member == "StartLabWithParameters":
            return session_fields(self.engine.start(body[0], uid, dict(body[1])))
        operations = {
            "StartLab": self.engine.start, "GetSession": self.engine.status,
            "StopSession": self.engine.stop, "ResetSession": self.engine.reset,
            "SaveSession": self.engine.save, "SuspendSession": self.engine.suspend,
            "ResumeSession": self.engine.resume,
            "DiscardSessionCheckpoint": self.engine.discard,
        }
        return session_fields(operations[member](body[0], uid))

    async def reply(self, message, signature, introspect):
        try:
            uid = await self.caller_uid(message.sender)
            if introspect:
                result = files("cyberlab_ipc").joinpath("org.ptit.CyberLab1.xml").read_text()
            else:
                result = await asyncio.to_thread(self.dispatch, message.member, message.body, uid, message.sender)
            response = Message.new_method_return(message, signature=signature, body=[result])
        except PermissionError:
            response = Message.new_error(message, f"{ERROR_PREFIX}.AccessDenied", "Caller is not authorized")
        except (SessionNotFound, CheckReportNotFound, LabNotFoundError, TerminalNotFound, DocumentationNotFound, DraftNotFound, WorkspaceNotFound):
            response = Message.new_error(message, f"{ERROR_PREFIX}.NotFound", "Lab, Session, node, or terminal not found")
        except LabInUseError as error:
            response = Message.new_error(message, f"{ERROR_PREFIX}.InUse", str(error))
        except TerminalBusy:
            response = Message.new_error(message, f"{ERROR_PREFIX}.Busy", "Node already has an attached terminal")
        except SessionBusy as error:
            response = Message.new_error(message, f"{ERROR_PREFIX}.Busy", str(error))
        except DraftConflict as error:
            response = Message.new_error(message, f"{ERROR_PREFIX}.Conflict", str(error))
        except RuntimeFailure as error:
            response = Message.new_error(message, f"{ERROR_PREFIX}.RuntimeFailed", str(error))
        except QuizRequired as error:
            response = Message.new_error(message, f"{ERROR_PREFIX}.QuizRequired", str(error))
        except QuizRevisionChanged as error:
            response = Message.new_error(message, f"{ERROR_PREFIX}.Conflict", str(error))
        except ValueError:
            response = Message.new_error(message, "org.freedesktop.DBus.Error.InvalidArgs", "Invalid request values")
        except PolicyDenied as error:
            response = Message.new_error(message, f"{ERROR_PREFIX}.PolicyDenied", str(error))
        except (SessionLimit, DraftLimit) as error:
            response = Message.new_error(message, f"{ERROR_PREFIX}.LimitReached", str(error))
        except LabError:
            response = Message.new_error(message, f"{ERROR_PREFIX}.InvalidLab", "Catalog is invalid or unavailable; ask administrator")
        except Exception as error:
            logging.error("Request failed (%s)", type(error).__name__)
            response = Message.new_error(message, f"{ERROR_PREFIX}.Internal", "Request failed; inspect Session state before retrying")
        try:
            await self.bus.send(response)
        except Exception:
            logging.warning("Could not deliver D-Bus reply")

    async def shutdown(self):
        self.closing = True
        if self.tasks:
            await asyncio.gather(*tuple(self.tasks), return_exceptions=True)
        await asyncio.to_thread(self.engine.shutdown)
