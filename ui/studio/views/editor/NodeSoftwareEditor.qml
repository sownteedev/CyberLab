import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../../models/NodeDefaults.js" as Defaults
import "../.." as Studio
import "../../models/Messages.js" as Messages

ColumnLayout {
    id: panel

    required property var editor
    required property int nodeIndex
    readonly property var node: editor.document && editor.document.nodes[nodeIndex] ? editor.document.nodes[nodeIndex] : null
    readonly property var software: node && node.software ? node.software : {gui: false, apps: [], packages: []}
    readonly property var catalog: editor.policy && editor.policy.software_catalog ? editor.policy.software_catalog : {applications: []}
    property var job: null
    property string problem: ""
    property bool applying: false
    property bool ready: false
    property int queryGeneration: 0
    property bool alive: true
    readonly property string selectionKey: editor.draft && node ? editor.draft.id + "/" + node.id : ""
    readonly property bool preparing: !!job && ["QUEUED", "PREPARING", "CANCELLING"].includes(job.state)
    readonly property bool supported: !!editor.policy && !!editor.policy.software_preparation
    readonly property bool ubuntu: !!node && node.image === "cyberlab/ubuntu:24.04-1"
    readonly property bool hasSoftware: !!software.gui || (software.packages || []).length > 0 || (software.apps || []).length > 0
    readonly property bool editable: supported && ubuntu && !preparing && !applying

    Layout.fillWidth: true
    spacing: Studio.Theme.space8

    function update(apps, packages) {
        problem = "";
        job = null;
        ready = false;
        ++queryGeneration;
        const document = JSON.parse(JSON.stringify(editor.document));
        document.nodes[nodeIndex].software = {gui: true, apps: apps, packages: packages};
        Defaults.enableGui(document.nodes[nodeIndex], editor.policy);
        editor.commit(document);
    }
    function inspect() {
        if (applying) return;
        const query = ++queryGeneration;
        job = null;
        problem = "";
        ready = false;
        if (!supported || !node || !hasSoftware || !editor.draft || editor.dirty) return;
        const draftId = editor.draft.id;
        const nodeId = node.id;
        const revision = editor.draft.revision;
        editor.backend.request(["draft", "software-plan", draftId, nodeId, "--revision", String(revision)], (result, error) => {
            if (!panel || !panel.alive || query !== panel.queryGeneration || panel.editor.dirty || !panel.node || panel.node.id !== nodeId || !panel.editor.draft || panel.editor.draft.id !== draftId || panel.editor.draft.revision !== revision) return;
            if (error) panel.problem = error;
            else if (result) {
                panel.ready = !!result.ready && !!panel.software.gui;
                if (result.latest_job && result.latest_job.revision === revision && !result.ready) {
                    panel.job = result.latest_job;
                    panel.applyReady();
                }
            }
        }, "", true);
    }
    function prepare() {
        if (!editable || !node || !editor.draft) return;
        if (!software.gui) update(software.apps || [], software.packages || []);
        const draftId = editor.draft.id;
        const nodeId = node.id;
        const start = () => {
            if (!panel || !panel.alive || !panel.node || panel.node.id !== nodeId || !panel.editor.draft || panel.editor.draft.id !== draftId || panel.editor.dirty) return;
            const revision = panel.editor.draft.revision;
            ++panel.queryGeneration;
            panel.editor.backend.request(["draft", "software-prepare", draftId, nodeId, "--revision", String(revision)], (result, error) => {
                if (!panel || !panel.alive || !panel.node || panel.node.id !== nodeId || !panel.editor.draft || panel.editor.draft.id !== draftId || panel.editor.draft.revision !== revision) return;
                if (error) panel.problem = error;
                else { panel.job = result; panel.applyReady(); }
            });
        };
        if (editor.dirty) editor.save(start); else start();
    }
    function applyReady() {
        if (!job || job.state !== "READY" || applying || editor.dirty || !editor.draft || job.draft !== editor.draft.id || job.revision !== editor.draft.revision || !node || job.node !== node.id) return;
        applying = true;
        const draftId = editor.draft.id;
        const key = selectionKey;
        const generation = editor.documentGeneration;
        editor.backend.request(["draft", "software-apply", job.id], (result, error) => {
            if (!panel || !panel.alive) return;
            panel.applying = false;
            if (panel.selectionKey !== key) return;
            if (error) { panel.problem = error; return; }
            if (!panel.editor.draft || panel.editor.draft.id !== draftId) return;
            const changed = panel.editor.documentGeneration !== generation || panel.editor.dirty;
            panel.editor.adopt(result, changed);
            panel.job = null;
            panel.ready = !changed && !!panel.software.gui;
            if (changed) panel.problem = "Môi trường đã chuẩn bị; thay đổi đang soạn được giữ nguyên. Lưu rồi chuẩn bị lại nếu cần.";
        });
    }
    onSelectionKeyChanged: {
        ++queryGeneration;
        job = null;
        problem = "";
        ready = false;
        packagePicker.reset();
        refresh.restart();
    }
    onSoftwareChanged: { ready = false; refresh.restart(); }
    Component.onCompleted: refresh.restart()
    Component.onDestruction: alive = false
    Connections {
        target: panel.editor
        function onDirtyChanged() { if (!panel.editor.dirty) refresh.restart(); }
    }
    Timer { id: refresh; interval: 1; onTriggered: panel.inspect() }

    Studio.NodePackagePicker {
        id: packagePicker
        catalog: panel.catalog
        software: panel.software
        backend: panel.editor.backend
        searchSupported: !!panel.editor.policy && !!panel.editor.policy.software_search
        contextKey: panel.selectionKey
        editable: panel.editable
        visible: panel.supported && panel.ubuntu
        onSelectionChanged: (apps, packages, gui) => panel.update(apps, packages)
        onRejected: message => panel.problem = message
    }
    Label {
        Layout.fillWidth: true
        text: !panel.ubuntu ? qsTr("Chọn Ubuntu để thêm phần mềm.") : qsTr("Cần cập nhật daemon để chuẩn bị phần mềm.")
        visible: !panel.ubuntu || !panel.supported
        color: Studio.Theme.textOnSurfaceVariant
        wrapMode: Text.WordWrap
    }
    ColumnLayout {
        Layout.fillWidth: true
        visible: (panel.ubuntu && panel.supported) || panel.problem.length > 0
        spacing: Studio.Theme.space8
        ProgressBar { Layout.fillWidth: true; visible: panel.preparing; from: 0; to: 100; value: panel.job ? panel.job.progress : 0; indeterminate: panel.preparing && value < 90 }
        Label {
            Layout.fillWidth: true
            objectName: "softwarePreparationStatus"
            textFormat: Text.PlainText
            visible: !!panel.problem || !!(panel.job && panel.job.error) || panel.preparing || panel.applying
            text: Messages.text(panel.problem || (panel.job && panel.job.error)) || (panel.preparing ? qsTr("Đang cài phần mềm…") : panel.applying ? qsTr("Đang áp dụng…") : "")
            color: panel.problem || (panel.job && panel.job.error) ? Studio.Theme.error : Studio.Theme.textOnSurfaceVariant
            wrapMode: Text.WordWrap
            Studio.ErrorNotifier { message: panel.problem || (panel.job && panel.job.error) || "" }
        }
        Flow {
            Layout.fillWidth: true
            Layout.preferredHeight: implicitHeight
            spacing: Studio.Theme.space8
            Studio.StudioButton {
                objectName: "prepareNodeSoftware"
                text: panel.preparing ? qsTr("Đang cài…") : panel.ready ? qsTr("Đã cài") : qsTr("Cài phần mềm")
                highlighted: true
                iconName: panel.ready ? "check" : "settings"
                enabled: panel.editable && !panel.ready
                onClicked: panel.prepare()
            }
            Studio.StudioButton {
                objectName: "applyNodeSoftware"
                text: qsTr("Áp dụng môi trường")
                visible: !!panel.job && panel.job.state === "READY" && !panel.ready
                enabled: !panel.applying && !panel.editor.dirty
                onClicked: panel.applyReady()
            }
            Studio.StudioButton {
                text: qsTr("Hủy chuẩn bị")
                visible: panel.preparing
                onClicked: {
                    const jobId = panel.job.id;
                    panel.editor.backend.request(["draft", "software-cancel", jobId], (result, error) => {
                        if (!panel || !panel.alive || !panel.job || panel.job.id !== jobId) return;
                        if (error) panel.problem = error; else panel.job = result;
                    });
                }
            }
        }
    }
    Label {
        objectName: "softwarePreparationHint"
        Layout.fillWidth: true
        visible: panel.ubuntu && panel.supported
        text: qsTr("Cài sẵn để khởi động nhanh hơn.")
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        wrapMode: Text.WordWrap
    }
    Timer {
        interval: 1000
        running: panel.preparing
        repeat: true
        onTriggered: {
            const jobId = panel.job.id;
            panel.editor.backend.request(["draft", "software-status", jobId], (result, error) => {
                if (!panel || !panel.alive || !panel.job || panel.job.id !== jobId) return;
                if (error) { panel.problem = error; return; }
                panel.job = result;
                panel.applyReady();
            }, "", true);
        }
    }
}
