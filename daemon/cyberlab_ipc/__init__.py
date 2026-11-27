"""Versioned transport contract shared by the daemon and CLI, not the engine."""

BUS_NAME = "org.ptit.CyberLab1"
OBJECT_PATH = "/org/ptit/CyberLab1"
INTERFACE = BUS_NAME
VERSION = "0.9.0"
MAX_DRAFT_DEFINITION = 64 * 1024
MAX_DRAFT_ASSET = 8 * 1024 * 1024
MAX_DRAFT_PACKAGE = 16 * 1024 * 1024
MAX_LAB_PACKAGE = 24 * 1024 * 1024
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
    "UnlockEditing": ("sss", "s"),
    "SetEditPassword": ("ssss", "s"),
    "RevokeEditing": ("s", "b"),
    "ProtectedAuthoring": ("sss", "s"),
    "PrepareDesktopContext": ("s", "s"),
    "ReleaseDesktopContext": ("s", "b"),
    "StartLabWithDesktop": ("sa{ss}s", "a{sv}"),
    "ResumeSessionWithDesktop": ("ss", "a{sv}"),
    "ResetSessionWithDesktop": ("ss", "a{sv}"),
    "ReconnectNativeDesktop": ("sss", "b"),
    "GetAuthoringInfo": ("", "s"),
    "CreateDraft": ("ss", "s"),
    "CreateTaggedDraft": ("ssass", "s"),
    "CloneLab": ("sss", "s"),
    "EditLab": ("s", "s"),
    "ResolveLabDraft": ("ssb", "s"),
    "ListDrafts": ("", "s"),
    "GetDraft": ("s", "s"),
    "PlanNodeSoftware": ("sus", "s"),
    "PrepareNodeSoftware": ("sus", "s"),
    "GetSoftwareJob": ("s", "s"),
    "CancelSoftwareJob": ("s", "s"),
    "ApplySoftwareJob": ("s", "s"),
    "SaveDraft": ("sus", "s"),
    "SaveDraftWorkspace": ("sus", "s"),
    "SetNodeAccountPassword": ("suss", "s"),
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
    "InspectLabtainer": ("ayss", "s"),
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
    "GetDesktopStatus": ("ss", "s"),
    "PrepareDesktop": ("ss", "b"),
    "OpenDesktop": ("ss", "(say)"),
    "ConfirmDesktop": ("s", "b"),
    "ReadDesktop": ("s", "(ayb)"),
    "WriteDesktop": ("say", "u"),
    "CloseDesktop": ("s", "b"),
}
