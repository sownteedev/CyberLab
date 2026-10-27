"""Versioned transport contract shared by the daemon and CLI, not the engine."""

BUS_NAME = "org.ptit.CyberLab1"
OBJECT_PATH = "/org/ptit/CyberLab1"
INTERFACE = BUS_NAME
VERSION = "0.9.0"
MAX_DRAFT_DEFINITION = 64 * 1024
MAX_DRAFT_ASSET = 1024 * 1024
MAX_DRAFT_PACKAGE = 2 * 1024 * 1024
MAX_LAB_PACKAGE = 4 * 1024 * 1024
MAX_LABTAINER_ARCHIVE = 32 * 1024 * 1024
MAX_LABTAINER_CONTENT = 32 * 1024 * 1024
MAX_LABTAINER_ENTRIES = 512
MAX_SUBMISSION_BYTES = 8 * 1024 * 1024
MAX_REVIEW_BYTES = 32 * 1024 * 1024
MAX_REVIEW_ITEMS = 32
MAX_IMPORT_BYTES = 256 * 1024
MAX_WORKSPACE_UPLOAD = 8 * 1024 * 1024
ERROR_PREFIX = f"{BUS_NAME}.Error"
METHODS = {
    "GetAuthoringInfo": ("", "s"),
    "CreateDraft": ("ss", "s"),
    "CloneLab": ("sss", "s"),
    "EditLab": ("s", "s"),
    "ListDrafts": ("", "s"),
    "GetDraft": ("s", "s"),
    "SaveDraft": ("sus", "s"),
    "PutDraftAssets": ("sua(say)", "s"),
    "GetDraftAsset": ("sus", "ay"),
    "RemoveDraftAsset": ("sus", "s"),
    "ValidateDraft": ("su", "s"),
    "CheckDraftRuntime": ("su", "s"),
    "PublishDraft": ("sus", "s"),
    "UpdateLab": ("ssuss", "s"),
    "DeleteDraft": ("su", "b"),
    "ExportLabPackage": ("s", "ay"),
    "ExportDraftPackage": ("su", "ay"),
    "ImportLabPackage": ("ayss", "s"),
    "ImportLabtainer": ("ayss", "s"),
    "GetVersion": ("", "s"),
    "GetCapabilities": ("", "as"),
    "ListLabs": ("", "aa{sv}"),
    "GetLab": ("s", "a{sv}"),
    "DeleteLab": ("s", "b"),
    "GetLabDocumentation": ("s", "a{sv}"),
    "GetSessionDocumentation": ("s", "a{sv}"),
    "CheckWork": ("s", "s"),
    "ListCheckReports": ("s", "s"),
    "GetCheckReport": ("s", "s"),
    "DeleteCheckReport": ("s", "b"),
    "ExportSubmission": ("s", "ay"),
    "PrepareSubmission": ("s", "s"),
    "FinalizeSubmission": ("ss", "a{sv}"),
    "ReviewSubmissions": ("a(say)", "s"),
    "SubmitQuiz": ("ss", "s"),
    "GetQuizAttempt": ("s", "s"),
    "GetLabQuiz": ("s", "s"),
    "SubmitLabQuiz": ("sss", "s"),
    "DeleteLabQuizAttempt": ("s", "b"),
    "ImportFile": ("sssay", "a{sv}"),
    "ListImports": ("s", "aa{sv}"),
    "ListWorkspace": ("ss", "s"),
    "ReadWorkspaceFile": ("sss", "ay"),
    "ExportWorkspace": ("sss", "ay"),
    "ImportWorkspace": ("sssay", "s"),
    "StartLab": ("s", "a{sv}"),
    "StartLabWithParameters": ("sa{ss}", "a{sv}"),
    "ListSessions": ("", "aa{sv}"),
    "GetSession": ("s", "a{sv}"),
    "StopSession": ("s", "a{sv}"),
    "ResetSession": ("s", "a{sv}"),
    "SaveSession": ("s", "a{sv}"),
    "SuspendSession": ("s", "a{sv}"),
    "ResumeSession": ("s", "a{sv}"),
    "DiscardSessionCheckpoint": ("s", "a{sv}"),
    "OpenTerminal": ("ssqq", "s"),
    "OpenTerminalSlot": ("ssuqq", "s"),
    "ReadTerminal": ("s", "(ayb)"),
    "WriteTerminal": ("say", "u"),
    "ResizeTerminal": ("sqq", "b"),
    "CloseTerminal": ("s", "b"),
}
