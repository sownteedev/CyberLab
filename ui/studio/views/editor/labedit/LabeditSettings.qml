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
    Label { text: "Kiểm tra và bài nộp"; font.pixelSize: Studio.Theme.titleMedium; color: Studio.Theme.textOnSurface }
    CheckBox {
        objectName: "enableCheckwork"
        text: "Cho phép kiểm tra bài làm"
        checked: page.settings.checkwork === true
        onToggled: page.editor.changePath(["settings", "checkwork"], checked)
    }
    CheckBox {
        text: "Đưa hướng dẫn vào gói bài nộp"
        checked: page.settings.collect_documentation === true
        onToggled: page.editor.changePath(["settings", "collect_documentation"], checked)
    }
    Label { text: "Seed của bài"; color: Studio.Theme.textOnSurface }
    StudioTextField {
        Layout.fillWidth: true
        text: page.settings.master_seed || ""
        placeholderText: "Tùy chọn; kết hợp với mã phiên để sinh tham số"
        Accessible.name: "Seed của bài"
        maximumLength: 128
        onEditingFinished: page.editor.changePath(["settings", "master_seed"], text.trim())
    }
    Label {
        Layout.fillWidth: true
        text: "Chọn Bằng chứng, Điều kiện và Mục tiêu để cấu hình Checkwork. Chỉ các file được khai báo mới đưa vào bài nộp."
        wrapMode: Text.WordWrap
        color: Studio.Theme.textOnSurfaceVariant
        font.pixelSize: Studio.Theme.bodySmall
    }
    Label {
        Layout.fillWidth: true
        visible: !!page.settings.host_home_xfer || !!page.settings.grade_node
        text: "Bản nháp có tùy chọn thư mục trao đổi hoặc node chấm chưa được runtime hỗ trợ. Các giá trị được giữ nguyên, không tự thực thi."
        wrapMode: Text.WordWrap
        color: Studio.Theme.error
        font.pixelSize: Studio.Theme.bodySmall
    }
}
