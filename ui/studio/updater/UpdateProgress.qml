import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import ".." as Studio

ColumnLayout {
    id: progress
    property string phase: "waiting"
    property int percent: -1
    property real received: 0
    property bool running: true
    property bool completed: false
    property string problem: ""
    property string details: ""
    signal restartRequested()
    signal closeRequested()
    readonly property var labels: ({waiting: qsTr("Đang chờ Studio đóng"), download: qsTr("Đang tải bản cập nhật"),
        extract: qsTr("Đang kiểm tra gói tải về"), authorize: qsTr("Xác thực quản trị"), build: qsTr("Đang chuẩn bị bản cài"),
        install: qsTr("Đang cài đặt"), verify: qsTr("Đang kiểm tra bản cập nhật")})
    function acceptEvent(event) {
        if (!event || typeof event.event !== "string") return;
        if (event.event === "complete") {
            completed = true;
            phase = "complete";
            percent = 100;
        } else if (event.event === "error") {
            completed = false;
            problem = event.message || qsTr("Cập nhật chưa hoàn tất.");
            percent = -1;
        } else if (labels[event.event]) {
            phase = event.event;
            if (event.event === "download" && typeof event.received === "number") received = Math.max(0, event.received);
            percent = event.event === "download" && typeof event.percent === "number" ? Math.max(0, Math.min(100, event.percent)) : -1;
        }
    }
    function finish(code) {
        running = false;
        if (code !== 0 || !completed) {
            completed = false;
            if (!problem) problem = qsTr("Cập nhật bị gián đoạn. Kiểm tra chi tiết trước khi thử lại.");
        }
    }
    spacing: Studio.Theme.space24
    Studio.Icon {
        Layout.alignment: Qt.AlignHCenter
        size: 48
        name: progress.problem ? "error" : progress.completed ? "check_circle" : "download"
        color: progress.problem ? Studio.Theme.error : Studio.Theme.primary
    }
    Label {
        objectName: "updateProgressTitle"
        Layout.fillWidth: true
        text: progress.problem ? qsTr("Chưa cập nhật xong") : progress.completed ? qsTr("Cập nhật hoàn tất") : progress.labels[progress.phase] || qsTr("Cập nhật CyberLab")
        font.pixelSize: Studio.Theme.titleLarge
        font.weight: Font.DemiBold
        color: Studio.Theme.textOnSurface
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }
    Label {
        Layout.fillWidth: true
        text: progress.problem || (progress.completed ? qsTr("Khởi động lại CyberLab để dùng bản mới.") : progress.phase === "authorize"
            ? qsTr("Xác nhận trong hộp thoại của hệ thống. Không nhập mật khẩu vào CyberLab.") : qsTr("Giữ cửa sổ này mở đến khi hoàn tất."))
        textFormat: Text.PlainText
        color: Studio.Theme.textOnSurfaceVariant
        horizontalAlignment: Text.AlignHCenter
        wrapMode: Text.WordWrap
    }
    ProgressBar {
        objectName: "systemUpdateProgress"
        Layout.fillWidth: true
        visible: progress.running && !progress.problem
        indeterminate: progress.percent < 0
        from: 0; to: 100; value: progress.percent
        background: Rectangle { implicitHeight: 8; radius: 4; color: Studio.Theme.surfaceContainerHigh }
        contentItem: Item {
            implicitHeight: 8
            clip: true
            Rectangle {
                height: parent.height
                radius: 4
                color: Studio.Theme.primary
                width: progress.percent >= 0 ? parent.width * progress.percent / 100 : parent.width * 0.3
                x: progress.percent >= 0 ? 0 : (parent.width - width) * pulse.position
                QtObject { id: pulse; property real position: 0 }
                SequentialAnimation {
                    running: progress.running && progress.percent < 0
                    loops: Animation.Infinite
                    NumberAnimation { target: pulse; property: "position"; from: 0; to: 1; duration: 950; easing.type: Easing.InOutSine }
                    NumberAnimation { target: pulse; property: "position"; from: 1; to: 0; duration: 950; easing.type: Easing.InOutSine }
                }
            }
        }
    }
    Label {
        objectName: "systemUpdatePercent"
        Layout.alignment: Qt.AlignHCenter
        visible: progress.running && progress.phase === "download" && (progress.percent >= 0 || progress.received > 0)
        text: progress.percent >= 0 ? qsTr("Tải xuống · %1%").arg(progress.percent) : qsTr("Đã tải %1 MB").arg((progress.received / 1048576).toFixed(1))
        color: Studio.Theme.textOnSurfaceVariant
    }
    Studio.StudioButton {
        Layout.alignment: Qt.AlignHCenter
        visible: !progress.running
        objectName: "restartAfterUpdate"
        text: progress.completed ? qsTr("Khởi động lại CyberLab") : qsTr("Mở lại CyberLab")
        iconName: "restart_alt"
        highlighted: true
        onClicked: progress.restartRequested()
    }
    Studio.StudioButton {
        Layout.alignment: Qt.AlignHCenter
        visible: !progress.running && !progress.completed
        text: qsTr("Đóng")
        flat: true
        onClicked: progress.closeRequested()
    }
    Disclosure {
        Layout.fillWidth: true
        visible: progress.problem.length > 0 && progress.details.length > 0
    }
    component Disclosure: ColumnLayout {
        Studio.StudioButton { text: qsTr("Chi tiết lỗi"); flat: true; onClicked: diagnostics.visible = !diagnostics.visible }
        ScrollView {
            id: diagnostics
            visible: false
            Layout.fillWidth: true
            Layout.preferredHeight: 130
            clip: true
            TextArea {
                text: progress.details
                textFormat: TextEdit.PlainText
                readOnly: true
                wrapMode: TextEdit.WrapAnywhere
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                background: Rectangle { color: Studio.Theme.surfaceContainerLow; radius: Studio.Theme.shapeSmall }
            }
        }
    }
}
