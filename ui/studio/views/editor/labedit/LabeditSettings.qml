import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../../.."
import "../../.." as Studio

ColumnLayout {
    id: page

    required property var editor
    readonly property var settings: (editor.document || {}).settings || {}

    spacing: Studio.Theme.space8

    Label {
        color: Studio.Theme.textOnSurface
        font.pixelSize: Studio.Theme.titleMedium
        text: "Kiểm tra và bài nộp"
    }
    Studio.StudioCheckBox {
        checked: page.settings.checkwork === true
        objectName: "enableCheckwork"
        text: "Cho phép kiểm tra bài làm"

        onToggled: page.editor.changePath(["settings", "checkwork"], checked)
    }
    Studio.StudioCheckBox {
        checked: page.settings.collect_documentation === true
        text: "Đưa hướng dẫn vào gói bài nộp"

        onToggled: page.editor.changePath(["settings", "collect_documentation"], checked)
    }
    Label {
        color: Studio.Theme.textOnSurface
        text: "Seed của bài"
    }
    StudioTextField {
        Accessible.name: "Seed của bài"
        Layout.fillWidth: true
        maximumLength: 128
        placeholderText: "Tùy chọn; kết hợp với mã phiên để sinh tham số"
        text: page.settings.master_seed || ""

        onEditingFinished: page.editor.changePath(["settings", "master_seed"], text.trim())
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
        text: "Chỉ file đã khai báo được đưa vào bài nộp."
        wrapMode: Text.WordWrap
    }
    Label {
        Layout.fillWidth: true
        color: Studio.Theme.error
        font.pixelSize: Studio.Theme.bodySmall
        text: "Bản nháp có tùy chọn thư mục trao đổi hoặc node chấm chưa được runtime hỗ trợ. Các giá trị được giữ nguyên, không tự thực thi."
        visible: !!page.settings.host_home_xfer || !!page.settings.grade_node
        wrapMode: Text.WordWrap
    }
}
