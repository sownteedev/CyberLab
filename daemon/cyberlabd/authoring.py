import json

from cyberlab.authoring.store import MAX_ASSET, MAX_DEFINITION, MAX_PACKAGE, MAX_PATHS
from cyberlab.lab.exchange import MAX_ARCHIVE
from cyberlab.lab.labtainer_archive import MAX_ARCHIVE as MAX_LABTAINER_ARCHIVE

METHODS = {
    "GetAuthoringInfo", "CreateDraft", "CloneLab", "EditLab", "ListDrafts", "GetDraft", "SaveDraft",
    "PutDraftAssets", "GetDraftAsset", "RemoveDraftAsset", "ValidateDraft", "CheckDraftRuntime", "PublishDraft", "UpdateLab", "DeleteDraft",
    "ExportLabPackage", "ExportDraftPackage", "ImportLabPackage", "ImportLabtainer",
}

def bounded(member, body):
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
    if member == "ImportLabtainer":
        return (len(body[0]) <= MAX_LABTAINER_ARCHIVE and len(body[1]) <= 64
                and len(body[2]) <= 128)
    return all(not isinstance(value, str) or len(value) <= 200 for value in body)

def dispatch(authoring, member, body, uid):
    if authoring is None:
        raise PermissionError("Authoring has not been enabled by an administrator")
    if member == "GetAuthoringInfo":
        result = {**authoring.capabilities(), "can_publish": True}
    elif member == "CreateDraft":
        result = authoring.create(*body, uid)
    elif member == "CloneLab":
        result = authoring.clone_lab(*body, uid)
    elif member == "EditLab":
        result = authoring.edit_lab(*body, uid)
    elif member == "ListDrafts":
        result = authoring.list(uid)
    elif member == "GetDraft":
        result = authoring.get(*body, uid)
    elif member == "SaveDraft":
        result = authoring.save(*body, uid)
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
        return authoring.store.delete(identifier, uid, revision)
    elif member == "ExportLabPackage":
        return authoring.export_lab_package(body[0], uid)
    elif member == "ExportDraftPackage":
        return authoring.export_draft_package(body[0], body[1], uid)
    elif member == "ImportLabPackage":
        result = authoring.import_lab_package(body[0], body[1], body[2], uid)
    elif member == "ImportLabtainer":
        result = authoring.import_labtainer(body[0], body[1], body[2], uid)
    else:
        raise ValueError("Unknown authoring method")
    return json.dumps(result, ensure_ascii=True)
