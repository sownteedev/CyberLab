import json
from dbus_next.signature import SignatureTree
from cyberlab_ipc import METHODS as CONTRACT
from cyberlab_ipc.editing import MAX_ENVELOPE, decode, encode

from cyberlab.authoring.store import MAX_ASSET, MAX_DEFINITION, MAX_PACKAGE, MAX_PATHS
from cyberlab.lab.exchange import MAX_ARCHIVE
from cyberlab.lab.labtainer_archive import MAX_ARCHIVE as MAX_LABTAINER_ARCHIVE

METHODS = {
    "UnlockEditing", "SetEditPassword", "RevokeEditing", "ProtectedAuthoring",
    "SetNodeAccountPassword",
    "CreateTaggedDraft",
    "SaveDraftWorkspace",
    "PlanNodeSoftware", "PrepareNodeSoftware", "GetSoftwareJob", "CancelSoftwareJob", "ApplySoftwareJob",
    "GetAuthoringInfo", "CreateDraft", "CloneLab", "EditLab", "ResolveLabDraft", "ListDrafts", "GetDraft", "SaveDraft",
    "PutDraftAssets", "GetDraftAsset", "RemoveDraftAsset", "ValidateDraft", "CheckDraftRuntime", "PublishDraft", "UpdateLab", "DeleteDraft",
    "ExportLabPackage", "ExportDraftPackage", "ImportLabPackage", "ImportLabtainer", "InspectLabtainer",
}

def bounded(member, body):
    if member == "ProtectedAuthoring":
        return len(body[0]) <= 128 and len(body[1]) <= 64 and len(body[2].encode("utf-8")) <= MAX_ENVELOPE
    if member in {"UnlockEditing", "SetEditPassword"}:
        return len(body[0]) <= 8 and len(body[1]) <= 64 and all(len(value.encode("utf-8")) <= 1024 for value in body[2:])
    if member == "SetNodeAccountPassword":
        return (len(body) == 4 and isinstance(body[0], str) and len(body[0]) <= 64
                and type(body[1]) is int and 0 <= body[1] <= 2 ** 32 - 1
                and isinstance(body[2], str) and len(body[2]) <= 64
                and isinstance(body[3], str) and len(body[3].encode("utf-8")) <= 8192)
    if member == "CreateTaggedDraft":
        return (len(body) == 4 and len(body[0]) <= 64 and len(body[1]) <= 128 and len(body[2]) <= 12
                and all(len(tag) <= 32 for tag in body[2]) and body[3] in {"easy", "medium", "hard"})
    if member == "SaveDraftWorkspace":
        return len(body[2].encode("utf-8")) <= MAX_PACKAGE * 6
    if member == "CreateDraft":
        return len(body[0]) <= 64 and len(body[1]) <= 128
    if member == "SaveDraft":
        return len(body[2].encode("utf-8")) <= MAX_DEFINITION
    if member == "PutDraftAssets":
        return len(body[2]) <= MAX_PATHS and all(len(path) <= 200 and len(data) <= MAX_ASSET for path, data in body[2]) and sum(len(data) for path, data in body[2]) <= MAX_PACKAGE
    if member == "ExportDraftPackage":
        return len(body[0]) <= 64 and type(body[1]) is int and 0 <= body[1] <= 2 ** 32 - 1
    if member == "ImportLabPackage":
        return (len(body[0]) <= MAX_ARCHIVE and len(body[1]) <= 64
                and len(body[2]) <= 128)
    if member in {"ImportLabtainer", "InspectLabtainer"}:
        return (len(body[0]) <= MAX_LABTAINER_ARCHIVE and len(body[1]) <= 64
                and len(body[2]) <= 128)
    return all(not isinstance(value, str) or len(value) <= 200 for value in body)

ACCESS_METHODS = {"UnlockEditing", "SetEditPassword", "RevokeEditing", "ProtectedAuthoring"}
DRAFT_METHODS = {
    "GetDraft", "SaveDraft", "SaveDraftWorkspace", "SetNodeAccountPassword",
    "PutDraftAssets", "GetDraftAsset", "RemoveDraftAsset", "ValidateDraft",
    "CheckDraftRuntime", "PublishDraft", "DeleteDraft", "ExportDraftPackage",
    "PlanNodeSoftware", "PrepareNodeSoftware",
}


def guard(authoring, member, body, uid, token):
    protection = authoring.protection
    if member in {"EditLab", "ResolveLabDraft", "CloneLab", "UpdateLab"}:
        protection.require("lab", body[0], uid, token)
    if member in DRAFT_METHODS:
        protection.require("draft", body[0], uid, token)
    if member == "UpdateLab" or (member == "ResolveLabDraft" and body[1]):
        protection.require("draft", body[1], uid, token)
    if member in {"GetSoftwareJob", "CancelSoftwareJob", "ApplySoftwareJob"}:
        if authoring.software is None:
            raise ValueError("Software preparation is unavailable")
        job = authoring.software.get(body[0], uid)
        protection.require("draft", job["draft"], uid, token)


def dispatch(authoring, member, body, uid, token=""):
    if authoring is None:
        raise PermissionError("Authoring has not been enabled by an administrator")
    with authoring.lifecycle_lock, authoring.store.lock:
        if member == "ProtectedAuthoring":
            token, inner, payload = body
            if inner not in METHODS or inner in ACCESS_METHODS:
                raise ValueError("Unsupported authenticated authoring method")
            arguments = decode(payload)
            try:
                SignatureTree(CONTRACT[inner][0]).verify(arguments)
            except Exception as error:
                raise ValueError("Invalid authenticated authoring arguments") from error
            if not bounded(inner, arguments):
                raise ValueError("Authoring payload exceeds its limit")
            return encode({"value": dispatch(authoring, inner, arguments, uid, token)})
        if member in {"UnlockEditing", "SetEditPassword"}:
            if body[0] == "lab":
                from cyberlab.lab.catalog import read_package
                read_package(authoring.catalog, body[1])
            operation = authoring.protection.unlock if member == "UnlockEditing" else authoring.protection.change
            return json.dumps(operation(*body, uid), ensure_ascii=True)
        if member == "RevokeEditing":
            return authoring.protection.revoke(body[0], uid)
        guard(authoring, member, body, uid, token)
        result = _dispatch(authoring, member, body, uid)
        if isinstance(result, str):
            payload = json.loads(result)
            if isinstance(payload, dict) and "definition" in payload and "id" in payload:
                if member != "CloneLab":
                    authoring.protection.require("draft", payload["id"], uid, token)
                payload["edit_protected"] = authoring.protection.protected("draft", payload["id"], uid)
                if member == "CloneLab" and payload["edit_protected"]:
                    payload["edit_token"] = authoring.protection.grant(authoring.protection.record("draft", payload["id"], uid), uid)
                return json.dumps(payload, ensure_ascii=True)
            if member == "ListDrafts":
                for entry in payload:
                    entry["edit_protected"] = authoring.protection.protected("draft", entry["id"], uid)
                return json.dumps(payload, ensure_ascii=True)
        return result


def _dispatch(authoring, member, body, uid):
    if member in {"PlanNodeSoftware", "PrepareNodeSoftware", "GetSoftwareJob", "CancelSoftwareJob", "ApplySoftwareJob"}:
        if authoring.software is None:
            raise ValueError("Software preparation is unavailable")
        method = {"PlanNodeSoftware": "plan", "PrepareNodeSoftware": "prepare", "GetSoftwareJob": "get", "CancelSoftwareJob": "cancel", "ApplySoftwareJob": "apply"}[member]
        result = getattr(authoring.software, method)(*body, uid)
    elif member == "GetAuthoringInfo":
        result = {**authoring.capabilities(), "can_publish": True}
    elif member == "CreateDraft":
        result = authoring.create(*body, uid)
    elif member == "CreateTaggedDraft":
        result = authoring.create(body[0], body[1], uid, tags=body[2], difficulty=body[3])
    elif member == "CloneLab":
        result = authoring.clone_lab(*body, uid)
    elif member == "EditLab":
        result = authoring.edit_lab(*body, uid)
    elif member == "ResolveLabDraft":
        result = authoring.edit_lab(body[0], uid, draft_id=body[1], fresh=body[2])
    elif member == "ListDrafts":
        result = authoring.list(uid)
    elif member == "GetDraft":
        result = authoring.get(*body, uid)
    elif member == "SaveDraft":
        result = authoring.save(*body, uid)
    elif member == "SaveDraftWorkspace":
        result = authoring.save_workspace(*body, uid)
    elif member == "SetNodeAccountPassword":
        result = authoring.set_node_account_password(*body, uid)
    elif member == "PutDraftAssets":
        result = authoring.put_assets(*body, uid)
    elif member == "GetDraftAsset":
        return authoring.asset(*body, uid)
    elif member == "RemoveDraftAsset":
        result = authoring.remove_asset(*body, uid)
    elif member == "ValidateDraft":
        result = authoring.validate(*body, uid)
    elif member == "CheckDraftRuntime":
        result = authoring.check_runtime(*body, uid)
    elif member == "PublishDraft":
        result = authoring.publish(*body, uid)
    elif member == "UpdateLab":
        result = authoring.update_installed(*body, uid)
    elif member == "DeleteDraft":
        identifier, revision = body
        result = authoring.store.delete(identifier, uid, revision)
        authoring.protection.link("draft", identifier, None)
        return result
    elif member == "ExportLabPackage":
        return authoring.export_lab_package(body[0], uid)
    elif member == "ExportDraftPackage":
        return authoring.export_draft_package(body[0], body[1], uid)
    elif member == "ImportLabPackage":
        result = authoring.import_lab_package(body[0], body[1], body[2], uid)
    elif member == "ImportLabtainer":
        result = authoring.import_labtainer(body[0], body[1], body[2], uid)
    elif member == "InspectLabtainer":
        result = authoring.inspect_labtainer(body[0], body[1], body[2], uid)
    else:
        raise ValueError("Unknown authoring method")
    return json.dumps(result, ensure_ascii=True)
