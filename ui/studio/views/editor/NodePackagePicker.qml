pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

ColumnLayout {
    id: picker
    objectName: "softwarePicker"

    required property var catalog
    required property var software
    required property var backend
    property bool searchSupported: false
    property string contextKey: ""
    property bool editable: true
    readonly property var apps: software.apps || []
    readonly property var packages: software.packages || []
    readonly property var matches: repository.results
    readonly property var selected: apps.map(name => selectedEntry(name, true)).concat(packages.map(name => selectedEntry(name, false)))
    signal selectionChanged(var apps, var packages, bool gui)
    signal rejected(string message)

    function selectedEntry(name, application) {
        return {id: name, name: name, application: application};
    }
    function sourceName(entry) { return entry.source === "mozilla" ? "Mozilla APT" : "Ubuntu APT"; }
    function selectedName(entry) { return entry.application && entry.id === "firefox" ? "firefox · Mozilla" : entry.id; }
    function unavailableReason(entry) {
        if (entry.unavailable_reason === "snap") return qsTr("Cần Snap — chưa hỗ trợ trong máy lab.");
        if (entry.unavailable_reason === "wireshark") return qsTr("Chọn gói wireshark để cài kèm công cụ này.");
        return qsTr("Gói này chưa được hỗ trợ trong máy lab.");
    }
    function reset() { search.text = ""; repository.reset(); }
    function isSelected(entry) { return (entry.application ? apps : packages).includes(entry.id); }
    function select(entry, checked) {
        if (!editable) return;
        if (checked && entry.installable === false) { rejected(unavailableReason(entry)); return; }
        const nextApps = entry.application ? (checked ? Array.from(new Set(apps.concat([entry.id]))) : apps.filter(name => name !== entry.id)) : apps;
        const nextPackages = entry.application ? packages : (checked ? Array.from(new Set(packages.concat([entry.id]))) : packages.filter(name => name !== entry.id));
        if (nextPackages.length > (catalog.max_packages || 32)) { rejected(qsTr("Tối đa 32 gói trên một máy.")); return; }
        selectionChanged(nextApps, nextPackages, true);
    }

    Layout.fillWidth: true
    spacing: Studio.Theme.space12

    Studio.PackageSearchService {
        id: repository
        objectName: "softwareRepositorySearch"
        backend: picker.backend
        supported: picker.searchSupported
        active: picker.visible && picker.editable
        query: search.text
        contextKey: picker.contextKey
    }
    Studio.StudioSearchField {
        id: search
        Layout.fillWidth: true
        objectName: "softwarePackageSearch"
        Accessible.name: qsTr("Tìm gói phần mềm")
        placeholderText: qsTr("Tìm gói APT…")
        maximumLength: 100
        enabled: picker.editable
    }
    Flow {
        id: chips
        Layout.fillWidth: true
        Layout.preferredHeight: implicitHeight
        visible: picker.selected.length > 0
        spacing: Studio.Theme.space4
        Repeater {
            model: picker.selected
            Studio.StudioButton {
                required property var modelData
                width: Math.min(implicitWidth, chips.width)
                objectName: (modelData.application ? "selectedApp-" : "selectedPackage-") + modelData.id
                selected: true
                iconName: "close"
                text: picker.selectedName(modelData)
                Accessible.name: qsTr("Bỏ %1").arg(picker.selectedName(modelData))
                enabled: picker.editable
                onClicked: picker.select(modelData, false)
            }
        }
    }
    ListView {
        id: results
        objectName: "softwareResults"
        Layout.fillWidth: true
        Layout.preferredHeight: Math.min(contentHeight, 320)
        clip: true
        model: picker.matches
        boundsBehavior: Flickable.StopAtBounds
        ScrollBar.vertical: ScrollBar { policy: results.contentHeight > results.height ? ScrollBar.AlwaysOn : ScrollBar.AsNeeded }
        delegate: ItemDelegate {
            id: choice
            required property var modelData
            width: results.width - 12
            height: modelData.installable === false ? 88 : 64
            objectName: (modelData.application ? "softwareApp-" : "softwarePackage-") + modelData.id
            checkable: modelData.installable !== false
            checked: picker.isSelected(modelData)
            enabled: picker.editable && modelData.installable !== false
            Accessible.name: modelData.name + ". " + picker.sourceName(modelData) + ". " + (modelData.installable === false ? picker.unavailableReason(modelData) : modelData.description || "")
            background: Rectangle {
                radius: Studio.Theme.shapeMedium
                color: choice.hovered || choice.visualFocus ? Studio.Theme.surfaceContainerHigh : Studio.Theme.transparent
                border.width: choice.visualFocus ? 1 : 0
                border.color: Studio.Theme.primary
            }
            contentItem: RowLayout {
                spacing: Studio.Theme.space12
                Studio.Icon {
                    name: choice.modelData.installable === false ? "topic-lock" : "inventory_2"
                    color: choice.checked ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant
                    size: Studio.Theme.iconSmall
                }
                ColumnLayout {
                    Layout.fillWidth: true
                    spacing: 2
                    RowLayout {
                        Layout.fillWidth: true
                        spacing: Studio.Theme.space8
                        Label {
                            Layout.fillWidth: true
                            text: choice.modelData.id
                            textFormat: Text.PlainText
                            elide: Text.ElideRight
                            color: Studio.Theme.textOnSurface
                            font.weight: Font.Medium
                        }
                        Label {
                            objectName: "softwareSource-" + (choice.modelData.source || "ubuntu") + "-" + choice.modelData.id
                            text: picker.sourceName(choice.modelData)
                            color: choice.modelData.source === "mozilla" ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant
                            font.pixelSize: Studio.Theme.labelSmall
                        }
                    }
                    Label {
                        Layout.fillWidth: true
                        text: choice.modelData.description || choice.modelData.id
                        textFormat: Text.PlainText
                        elide: Text.ElideRight
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.labelMedium
                    }
                    Label {
                        Layout.fillWidth: true
                        objectName: "softwareAvailability-" + (choice.modelData.source || "ubuntu") + "-" + choice.modelData.id
                        visible: choice.modelData.installable === false
                        text: picker.unavailableReason(choice.modelData)
                        wrapMode: Text.WordWrap
                        color: Studio.Theme.textOnSurfaceVariant
                        font.pixelSize: Studio.Theme.labelMedium
                    }
                }
                Rectangle {
                    Layout.preferredWidth: 20
                    Layout.preferredHeight: 20
                    radius: 4
                    color: choice.checked ? Studio.Theme.primary : Studio.Theme.transparent
                    border.color: choice.checked ? Studio.Theme.primary : Studio.Theme.outlineVariant
                    border.width: 2
                    Studio.Icon {
                        anchors.centerIn: parent
                        size: 16
                        name: "check"
                        visible: choice.checked
                        color: Studio.Theme.textOnPrimary
                    }
                }
            }
            onToggled: {
                picker.select(modelData, checked);
                checked = Qt.binding(() => picker.isSelected(choice.modelData));
            }
        }
    }
    Studio.InlineError {
        message: repository.state === "error" ? qsTr("Không tải được danh sách gói từ kho Ubuntu. Hãy kiểm tra kết nối rồi thử lại.")
            : repository.sourceErrors.includes("mozilla") ? qsTr("Chưa tải được kho Mozilla. Gói Ubuntu vẫn dùng được; hãy thử lại để cập nhật Firefox.") : ""
    }
    RowLayout {
        Layout.fillWidth: true
        visible: repository.loading || repository.state === "error" || repository.sourceErrors.length > 0 || !picker.matches.length || repository.total > 40
        BusyIndicator { running: repository.loading; visible: running; Layout.preferredWidth: 20; Layout.preferredHeight: 20 }
        Label {
            Layout.fillWidth: true
            objectName: "softwareSearchStatus"
            text: !picker.searchSupported ? qsTr("Tìm gói APT chưa khả dụng.") : repository.loading ? qsTr("Đang tải danh sách gói APT…") : repository.state === "error" || repository.sourceErrors.length > 0 ? "" : repository.state === "idle" ? qsTr("Tìm gói trong kho APT.") : !picker.matches.length ? qsTr("Không tìm thấy gói phù hợp.") : qsTr("Có nhiều kết quả. Nhập cụ thể hơn.")
            color: Studio.Theme.textOnSurfaceVariant
            wrapMode: Text.WordWrap
        }
        Studio.StudioButton {
            visible: repository.state === "error" || repository.sourceErrors.length > 0
            objectName: "softwareSearchRetry"
            text: qsTr("Thử lại")
            flat: true
            onClicked: repository.fetch(true)
        }
    }
}
