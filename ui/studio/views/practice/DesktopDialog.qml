import QtQuick
import "../.." as Studio

Item {
    id: desktop

    required property var api
    property string sessionId: ""
    property string nodeId: ""
    readonly property bool opened: confirmation.opened

    function openFor(session, node) {
        if (!session || session.state !== "RUNNING" || api.busy || !api.capabilities.includes("seamless-apps"))
            return;
        sessionId = session.id;
        nodeId = node;
        const identifier = sessionId;
        api.request(["desktop-status", identifier, node], (result, problem) => {
            if (problem || sessionId !== identifier || nodeId !== node)
                return;
            if (result && result.backend === "native-x11") {
                openViewer(identifier, node);
                return;
            }
            if (result && result.fallback_reason)
                api.notify(qsTr("Đang dùng Xpra dự phòng: ") + result.fallback_reason, true);
            if (result && result.viewer_ready === false) {
                const reason = result.host ? result.host.code : "xpra-missing";
                const messages = {
                    "xwayland-unavailable": qsTr("Phiên Wayland chưa kết nối được XWayland. Với Niri, kiểm tra xwayland-satellite; với DE/WM khác, kiểm tra XWayland. Mở lại CyberLab từ launcher sau khi chuẩn bị. Không cần đổi sang desktop X11."),
                    "x11-unavailable": qsTr("Không kết nối được màn hình X11. Mở CyberLab từ launcher bằng tài khoản desktop; không dùng sudo hoặc xhost +."),
                    "headless": qsTr("Phiên hiện tại không có màn hình đồ họa. Hãy mở CyberLab từ desktop Linux. CLI và terminal vẫn dùng được."),
                    "desktop-user-required": qsTr("Mở CyberLab bằng tài khoản desktop thông thường, không chạy bằng root."),
                    "xpra-incompatible": qsTr("Xpra trên máy thật chưa tương thích hoặc thiếu GTK3/rencodeplus. Chạy cyberlab gui-status để kiểm tra dependency.")
                };
                api.error = (messages[reason] || qsTr("Máy thật chưa có Xpra tương thích. Cần gói xpra để hiện riêng cửa sổ ứng dụng; không cần mở desktop VNC.")) + qsTr(" Phiên thực hành vẫn được giữ.");
                return;
            }
            if (result && result.ready === true)
                openViewer(identifier, node);
            else
                confirmation.open();
        });
    }
    function openViewer(identifier, node) {
        api.request(["open-desktop", identifier, node], (result, problem) => {
            if (!problem && result && result.opened)
                api.notify(qsTr("Đã bật cửa sổ ứng dụng cho máy ") + node + qsTr(". Chạy ứng dụng đã cài từ terminal của máy này; mỗi ứng dụng hiện cửa sổ riêng."), false);
        });
    }

    Studio.ConfirmDialog {
        id: confirmation

        objectName: "desktopPreparationConfirmation"
        title: qsTr("Bật ứng dụng đồ họa?")
        confirmText: qsTr("Cài trong máy lab")
        confirmEnabled: !desktop.api.busy
        message: qsTr("Cài Xpra, Xvfb và bộ hỗ trợ đồ họa vào máy Ubuntu này. Cần mạng và có thể mất vài phút; không cài ứng dụng lên máy thật.\n\nSau đó chạy ứng dụng đã cài từ terminal, ví dụ wireshark: cửa sổ sẽ hiện riêng, không mở cả desktop. File và mạng vẫn thuộc máy Lab; không chia sẻ clipboard hay màn hình host.\n\nLưu tiến độ để giữ các gói đã cài. Làm lại từ đầu sẽ xóa thay đổi này.")
        onAccepted: {
            const identifier = desktop.sessionId;
            const node = desktop.nodeId;
            desktop.api.request(["prepare-desktop", identifier, node, "--yes"], (result, problem) => {
                if (!problem && result && result.ready === true)
                    desktop.openViewer(identifier, node);
            });
        }
    }
}
