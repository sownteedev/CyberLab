import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Studio.StudioDialog {
    id: dialog

    property var report: null
    readonly property var descriptions: ({
        x11: [qsTr("Ứng dụng đồ họa (X11)"), qsTr("Bài yêu cầu kết nối màn hình X11. CyberLab chưa có màn hình cách ly cho từng phiên; không cấp quyền truy cập màn hình máy thật. Không phải mọi bài Labtainer đều cần X11, nhưng chưa thể tự bỏ yêu cầu này.")],
        system_files: [qsTr("File hệ thống"), qsTr("Bài có file ngoài thư mục home, như cấu hình trong /etc. Cần chuẩn bị image đã duyệt; chép các file này vào home không tạo ra môi trường tương đương.")],
        startup_hooks: [qsTr("Script khởi tạo"), qsTr("Các script thiết lập máy hoặc chạy khi bắt đầu cần được chuyển đổi và kiểm tra. CyberLab không chạy script từ ZIP trên máy thật.")],
        grading_hooks: [qsTr("Script chấm bài"), qsTr("Cần chuyển logic chấm bài sang Checkwork được hỗ trợ. Bỏ script sẽ làm thay đổi kết quả thực hành.")],
        privileged: [qsTr("Quyền container"), qsTr("Bài yêu cầu container đặc quyền, không phù hợp chính sách cách ly hiện tại.")],
        image_build: [qsTr("Image riêng của bài"), qsTr("Có Dockerfile cần được duyệt. Nhập ZIP không tự build image hay cài công cụ bên trong máy thực hành.")],
        archive: [qsTr("Cấu trúc gói"), qsTr("Kiểm tra giới hạn gói và bảo đảm chỉ có một bài với config/start.config. Không dùng ZIP mã nguồn CyberLab hoặc ZIP chứa nhiều bài.")],
        conversion: [qsTr("Nội dung chưa chuyển đổi được"), qsTr("Còn khai báo hoặc tài nguyên không thuộc tập được hỗ trợ. Cần kiểm tra và chuyển đổi trước khi nhập; không tự bỏ dữ liệu.")]
    })

    objectName: "labtainerCompatibilityDialog"
    title: qsTr("Chưa thể nhập bài Labtainer")
    width: Math.min(640, parent ? parent.width - Studio.Theme.space32 : 640)
    height: Math.min(600, parent ? parent.height - Studio.Theme.space32 : 600)
    padding: Studio.Theme.space24
    focus: true
    closePolicy: Popup.CloseOnEscape
    onOpened: Qt.callLater(() => closeButton.forceActiveFocus(Qt.TabFocusReason))
    onClosed: report = null

    header: Studio.StudioDialogHeader {
        title: dialog.title
        subtitle: qsTr("Gói gốc được giữ nguyên. Chưa tạo bản nháp hay thay đổi Thư viện. Đây là các yêu cầu đã nhận diện, không phải danh sách đầy đủ mọi điểm khác biệt.")
        iconName: "warning"
        onCloseRequested: dialog.reject()
    }
    contentItem: ListView {
        id: issues
        clip: true
        spacing: Studio.Theme.space12
        model: dialog.report ? dialog.report.issues : []
        ScrollBar.vertical: ScrollBar { }
        delegate: Rectangle {
            id: issue
            required property var modelData
            readonly property var description: dialog.descriptions[modelData.code] || dialog.descriptions.conversion
            width: issues.width
            implicitHeight: details.implicitHeight + Studio.Theme.space24
            radius: Studio.Theme.shapeMedium
            color: Studio.Theme.surfaceContainer

            ColumnLayout {
                id: details
                anchors { left: parent.left; right: parent.right; top: parent.top; margins: Studio.Theme.space12 }
                spacing: Studio.Theme.space8
                Label {
                    Layout.fillWidth: true
                    text: issue.description[0]
                    font.weight: Font.DemiBold
                    color: Studio.Theme.textOnSurface
                    wrapMode: Text.WordWrap
                }
                Label {
                    Layout.fillWidth: true
                    text: issue.description[1]
                    color: Studio.Theme.textOnSurfaceVariant
                    wrapMode: Text.WordWrap
                }
                Label {
                    Layout.fillWidth: true
                    text: (issue.modelData.locations || []).join("\n")
                    visible: text.length > 0
                    textFormat: Text.PlainText
                    color: Studio.Theme.textOnSurfaceVariant
                    wrapMode: Text.WrapAnywhere
                }
            }
        }
    }
    footer: Studio.StudioDialogFooter {
        contentItem: RowLayout {
            Item { Layout.fillWidth: true }
            Studio.StudioButton {
                id: closeButton
                objectName: "closeLabtainerCompatibility"
                text: qsTr("Đã hiểu")
                onClicked: dialog.accept()
            }
        }
    }
}
