import QtQuick
import QtQuick.Controls.Basic
import QtTest
import ".." as Studio

Item {
    id: checks
    property string screenshotFolder: ""
    ApplicationWindow {
        id: window
        width: 1000
        height: 720
        visible: true
        color: Studio.Theme.surface

        QtObject {
            id: api
            property string error: ""
            signal notificationRequested(string message, bool failure)
            function notify(message, failure) { notificationRequested(message, !!failure); }
        }
        Item {
            id: scene
            anchors.fill: parent
            Studio.StudioTextField {
                id: editor
                x: 32; y: 400; width: 280
                text: "Bản nháp chưa lưu"
            }
            Studio.StudioButton {
                id: behindToast
                anchors.right: parent.right
                anchors.rightMargin: 16
                y: 16; width: 250; height: 100
                text: "Không bấm xuyên popup"
            }
            Studio.StudioButton {
                id: outside
                x: 32; y: 160
                text: "Nội dung phía sau"
            }
            Studio.StudioComboBox {
                id: choices
                x: 32; y: 300; width: 240
                model: ["Tự động", "Terminal thứ nhất", "Terminal thứ hai"]
            }
            Item {
                id: validationContext
                x: 32; y: 480; width: 280
                Studio.InlineError { id: validation; width: parent.width }
            }
            Studio.StudioNotifications {
                id: notifications
                parent: window.Overlay.overlay
                z: 1000
                anchors.right: parent.right
                anchors.top: parent.top
                anchors.margins: 16
                width: Math.min(440, parent.width - 32)
                availableHeight: parent.height - 32
                api: api
                windowActive: true
            }
        }
        Studio.ConfirmDialog {
            id: modal
            title: "Xác nhận thay đổi"
            message: "Hộp thoại nổi trên nền mờ. Bản nháp và bài làm của bạn vẫn được giữ nguyên."
            danger: true
        }
        Studio.ConfirmDialog {
            id: nested
            title: "Xác nhận tiếp theo"
            message: "Đóng hộp thoại này để trở lại hộp thoại trước."
        }
        SignalSpy { id: outsideClick; target: outside; signalName: "clicked" }
        SignalSpy { id: behindClick; target: behindToast; signalName: "clicked" }
        SignalSpy { id: dismissed; target: notifications.errorToast; signalName: "dismissed" }
        TestCase {
            name: "StudioNotifications"
            when: window.visible

            function init() {
                Studio.Theme.reducedMotion = true;
                Studio.Theme.themeMode = "dark";
                window.width = 1000;
                window.height = 720;
                api.error = "";
                validationContext.visible = true;
                notifications.lifetime = 5000;
                notifications.windowActive = true;
                notifications.errorToast.dismiss(false);
                notifications.noticeToast.dismiss(false);
                window.requestActivate();
                tryCompare(window, "active", true);
                editor.forceActiveFocus();
                tryCompare(editor, "activeFocus", true);
                mouseMove(scene, 900, 600);
                dismissed.clear();
                outsideClick.clear();
                behindClick.clear();
            }
            function cleanup() {
                choices.popup.close();
                validation.message = "";
                nested.close();
                modal.close();
                notifications.errorToast.dismiss(false);
                notifications.noticeToast.dismiss(false);
                tryCompare(notifications, "visible", false);
            }
            function test_error_does_not_steal_focus_or_move_content() {
                api.error = "FAIL: org.freedesktop.DBus.Error.InvalidArgs: Invalid request values";
                verify(notifications.errorToast.shown);
                compare(notifications.errorToast.message, api.error);
                compare(editor.y, 400);
                verify(editor.activeFocus);
                compare(editor.text, "Bản nháp chưa lưu");
                compare(notifications.x + notifications.width, scene.width - 16);
                compare(notifications.y, 16);
                verify(notifications.width <= 440);
                tryCompare(notifications.errorToast, "visible", true);
                waitForRendering(notifications);
                mouseClick(notifications.errorToast, 20, 20);
                compare(behindClick.count, 0);
                mouseClick(outside);
                compare(outsideClick.count, 1);
                verify(notifications.errorToast.shown);
            }
            function test_error_is_manually_dismissible() {
                api.error = "Dữ liệu chưa hợp lệ.";
                verify(notifications.errorToast.shown);
                const close = findChild(notifications.errorToast, "toastClose");
                verify(close.width >= 48 && close.height >= 48);
                tryCompare(notifications.errorToast, "slideOffset", 0);
                waitForRendering(close);
                mouseClick(close);
                compare(api.error, "");
                compare(dismissed.count, 1);
                verify(!notifications.errorToast.shown);
            }
            function test_both_kinds_expire_after_five_seconds() {
                compare(notifications.lifetime, 5000);
                compare(notifications.errorToast.lifetime, 5000);
                compare(notifications.noticeToast.lifetime, 5000);
                api.error = "Lỗi cần đọc.";
                api.notify("Đã lưu bản nháp.", false);
                wait(4500);
                verify(notifications.errorToast.shown && notifications.noticeToast.shown);
                tryCompare(notifications.noticeToast, "shown", false, 1500);
                tryCompare(notifications.errorToast, "shown", false, 500);
                tryCompare(notifications, "visible", false);
                compare(api.error, "Lỗi cần đọc.");
            }
            function test_reading_does_not_prevent_expiry_data() {
                return [
                    { tag: "notice-hover", failure: false, interaction: "hover" },
                    { tag: "error-hover", failure: true, interaction: "hover" },
                    { tag: "notice-focus", failure: false, interaction: "focus" },
                    { tag: "error-focus", failure: true, interaction: "focus" },
                    { tag: "notice-inactive", failure: false, interaction: "inactive" },
                    { tag: "error-inactive", failure: true, interaction: "inactive" }
                ];
            }
            function test_reading_does_not_prevent_expiry(data) {
                notifications.lifetime = 700;
                api.notify("Đang đọc thông báo.", data.failure);
                const card = data.failure ? notifications.errorToast : notifications.noticeToast;
                wait(150);
                waitForRendering(card);
                if (data.interaction === "hover") mouseMove(card, 80, 25);
                else if (data.interaction === "focus") findChild(card, "toastClose").forceActiveFocus();
                else notifications.windowActive = false;
                tryCompare(card, "reading", true);
                tryCompare(card, "shown", false, 1000);
            }
            function test_replacement_restarts_only_its_own_timer() {
                notifications.lifetime = 600;
                api.notify("Lỗi trước.", true);
                api.notify("Thông báo riêng.", false);
                wait(400);
                api.notify("Lỗi tiếp theo.", true);
                wait(300);
                verify(!notifications.noticeToast.shown);
                verify(notifications.errorToast.shown);
                compare(notifications.errorToast.message, "Lỗi tiếp theo.");
                tryCompare(notifications.errorToast, "shown", false, 1000);
            }
            function test_expiry_slides_out() {
                Studio.Theme.reducedMotion = false;
                notifications.lifetime = 800;
                api.notify("Tự đóng thông báo lỗi.", true);
                tryCompare(notifications.errorToast, "slideOffset", 0);
                tryCompare(notifications.errorToast, "shown", false, 1500);
                tryCompare(notifications.errorToast, "visible", false);
                verify(notifications.errorToast.slideOffset > notifications.errorToast.width);
            }
            function test_bursts_replace_only_same_kind() {
                api.error = "Lỗi ban đầu.";
                for (let index = 0; index < 30; index++) api.notify("Đã lưu " + index, false);
                compare(notifications.noticeToast.message, "Đã lưu 29");
                compare(notifications.errorToast.message, "Lỗi ban đầu.");
                api.error = "Lỗi mới.";
                compare(notifications.errorToast.message, "Lỗi mới.");
                api.error = "";
                verify(!notifications.errorToast.shown);
                verify(notifications.noticeToast.shown);
            }
            function test_explicit_failure_is_not_cleared_by_old_error() {
                api.error = "Lỗi API.";
                api.notify("Lỗi cần xác nhận riêng.", true);
                api.error = "";
                verify(notifications.errorToast.shown);
                compare(notifications.errorToast.message, "Lỗi cần xác nhận riêng.");
            }
            function test_keyboard_and_literal_message() {
                api.error = "<b>Không được diễn giải HTML</b>\nChi tiết lỗi gốc.";
                const body = findChild(notifications.errorToast, "toastMessage");
                compare(body.text, api.error);
                compare(body.textFormat, TextEdit.PlainText);
                const close = findChild(notifications.errorToast, "toastClose");
                close.forceActiveFocus();
                keyClick(Qt.Key_Space);
                verify(!notifications.errorToast.shown);
                compare(api.error, "");
                api.error = "Đóng bằng Escape.";
                body.forceActiveFocus();
                keyClick(Qt.Key_Escape);
                verify(!notifications.errorToast.shown);
            }
            function test_motion_and_replacement_during_exit() {
                Studio.Theme.reducedMotion = false;
                verify(notifications.errorToast.slideOffset > notifications.errorToast.width);
                api.error = "Lỗi trước.";
                tryCompare(notifications.errorToast, "opacity", 1);
                tryCompare(notifications.errorToast, "slideOffset", 0);
                notifications.errorToast.dismiss(false);
                wait(35);
                verify(notifications.errorToast.slideOffset > 0);
                api.error = "Lỗi tiếp theo.";
                tryCompare(notifications.errorToast, "opacity", 1);
                wait(160);
                compare(notifications.errorToast.message, "Lỗi tiếp theo.");
                verify(notifications.errorToast.shown && notifications.errorToast.visible);
                notifications.errorToast.dismiss(false);
                tryCompare(notifications.errorToast, "opacity", 0);
                verify(notifications.errorToast.slideOffset > notifications.errorToast.width);
            }
            function test_modal_blocks_background_and_restores_focus() {
                modal.open();
                tryCompare(modal, "opened", true);
                verify(modal.modal && modal.dim);
                compare(modal.parent, window.Overlay.overlay);
                compare(modal.x, (window.width - modal.width) / 2);
                compare(modal.y, (window.height - modal.height) / 2);
                mouseClick(outside);
                compare(outsideClick.count, 0);
                verify(modal.opened);
                keyClick(Qt.Key_Escape);
                tryCompare(modal, "visible", false);
                tryCompare(editor, "activeFocus", true);
                mouseClick(outside);
                compare(outsideClick.count, 1);
            }
            function test_nested_modal_keeps_parent_dimmed() {
                modal.open();
                tryCompare(modal, "opened", true);
                nested.open();
                tryCompare(nested, "opened", true);
                keyClick(Qt.Key_Escape);
                tryCompare(nested, "visible", false);
                verify(modal.opened && modal.dim);
                compare(window.activeFocusItem.objectName, "confirmCancelButton");
                mouseClick(outside);
                compare(outsideClick.count, 0);
                keyClick(Qt.Key_Escape);
                tryCompare(modal, "visible", false);
            }
            function test_menu_has_shadow_without_dimming() {
                waitForRendering(scene);
                const before = grabImage(window.contentItem.parent);
                mouseClick(choices);
                tryCompare(choices.popup, "opened", true);
                compare(choices.popup.background.objectName, "studioPopupSurface");
                verify(!choices.popup.modal && !choices.popup.dim);
                waitForRendering(choices.popup.background);
                const after = grabImage(window.contentItem.parent);
                compare(after.pixel(8, window.height - 8), before.pixel(8, window.height - 8));
                keyClick(Qt.Key_Escape);
                tryCompare(choices.popup, "visible", false);
            }
            function test_contextual_error_is_popup_only_without_inline_space() {
                waitForRendering(scene);
                const before = grabImage(window.contentItem.parent);
                validation.message = "nodes: Không hợp lệ";
                tryCompare(notifications.errorToast, "shown", true);
                verify(!validation.visible);
                compare(validation.implicitHeight, 0);
                compare(validation.children.length, 0);
                waitForRendering(scene);
                const after = grabImage(window.contentItem.parent);
                compare(after.pixel(300, 500), before.pixel(300, 500));
            }
            function test_validation_error_also_opens_vietnamese_popup() {
                validation.message = "Node address must be usable in its subnet and cannot equal the bridge gateway";
                tryCompare(notifications.errorToast, "shown", true);
                const body = findChild(notifications.errorToast, "toastMessage");
                verify(body.text.indexOf("IP của máy phải nằm trong dải mạng") >= 0);
                verify(body.text.indexOf("Node address") < 0);
                verify(!validation.visible);
                verify(validation.Accessible.ignored);
            }
            function test_translated_backend_error_can_be_dismissed() {
                api.error = "Draft not found";
                tryCompare(notifications.errorToast, "shown", true);
                compare(findChild(notifications.errorToast, "toastMessage").text, "Không tìm thấy bản nháp.");
                notifications.errorToast.dismiss(true);
                compare(api.error, "");
            }
            function test_repeated_backend_failure_reopens_popup() {
                api.error = "Draft not found";
                tryCompare(notifications.errorToast, "shown", true);
                notifications.errorToast.dismiss(false);
                api.errorChanged();
                tryCompare(notifications.errorToast, "shown", true);
                compare(findChild(notifications.errorToast, "toastMessage").text, "Không tìm thấy bản nháp.");
            }
            function test_hidden_validation_does_not_open_popup() {
                validationContext.visible = false;
                validation.message = "Duplicate node address on a network";
                wait(80);
                verify(!notifications.errorToast.shown);
                validationContext.visible = true;
                tryCompare(notifications.errorToast, "shown", true);
            }
            function test_simultaneous_errors_share_one_popup_without_duplicates() {
                Studio.StudioFeedback.report("Draft not found\nDraft not found");
                Studio.StudioFeedback.report("Lab subnets must not overlap");
                Studio.StudioFeedback.report("Draft not found");
                tryCompare(notifications.errorToast, "shown", true);
                compare(findChild(notifications.errorToast, "toastMessage").text,
                    "Không tìm thấy bản nháp.\nCác dải mạng trong bài lab không được chồng lấn.");
            }
            function test_unchanged_inline_error_does_not_reopen_dismissed_popup() {
                validation.message = "Draft not found";
                tryCompare(notifications.errorToast, "shown", true);
                notifications.errorToast.dismiss(true);
                validationContext.visible = false;
                validationContext.visible = true;
                wait(80);
                verify(!notifications.errorToast.shown);
                validation.message = "";
                validation.message = "Draft not found";
                tryCompare(notifications.errorToast, "shown", true);
            }
            function test_vietnamese_error_popup_visual() {
                Studio.StudioFeedback.report("Node address must be usable in its subnet and cannot equal the bridge gateway");
                tryCompare(notifications.errorToast, "shown", true);
                waitForRendering(notifications);
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/vietnamese-network-error.png");
            }
            function test_error_popup_is_visible_over_open_dialog() {
                modal.open();
                tryCompare(modal, "opened", true);
                Studio.StudioFeedback.report("Draft not found");
                tryCompare(notifications.errorToast, "shown", true);
                verify(notifications.visible && notifications.parent.visible);
                verify(notifications.z > modal.z);
                const close = findChild(notifications.errorToast, "toastClose");
                mouseClick(close, close.width / 2, close.height / 2);
                verify(!notifications.errorToast.shown);
                verify(modal.opened);
            }
            function test_modal_visual_data() {
                return [{tag: "dark", width: 1000, theme: "dark"}, {tag: "light", width: 1000, theme: "light"}, {tag: "compact", width: 380, theme: "dark"}];
            }
            function test_modal_visual(data) {
                window.width = data.width;
                Studio.Theme.themeMode = data.theme;
                waitForRendering(scene);
                const capture = window.contentItem.parent;
                const before = grabImage(capture);
                modal.open();
                tryCompare(modal, "opened", true);
                waitForRendering(modal.background);
                const after = grabImage(capture);
                if (checks.screenshotFolder)
                    after.save(checks.screenshotFolder + "/dialog-" + data.tag + ".png");
                verify(after.red(8, window.height - 8) < before.red(8, window.height - 8));
                const shadowY = Math.round(modal.y + modal.height + 8);
                verify(after.blue(window.width / 2, shadowY) < after.blue(8, shadowY));
                compare(modal.background.objectName, "studioPopupSurface");
                modal.close();
                tryCompare(modal, "visible", false);
                waitForRendering(scene);
                const restored = grabImage(capture);
                compare(restored.pixel(8, window.height - 8), before.pixel(8, window.height - 8));
            }
            function test_visual_data() {
                return [{tag: "dark", width: 1000, theme: "dark"}, {tag: "light", width: 1000, theme: "light"}, {tag: "compact", width: 380, theme: "dark"}];
            }
            function test_visual(data) {
                window.width = data.width;
                window.height = 600;
                Studio.Theme.themeMode = data.theme;
                api.error = "FAIL: org.freedesktop.DBus.Error.InvalidArgs: Invalid request values";
                api.notify("Đã lưu bản nháp. Bạn có thể tiếp tục chỉnh sửa hoặc lưu vào thư viện.", false);
                wait(120);
                verify(notifications.errorToast.height <= notifications.cardHeight + 2);
                verify(notifications.height <= notifications.availableHeight);
                verify(notifications.width <= window.width - 32);
                if (checks.screenshotFolder) {
                    grabImage(window.contentItem.parent).save(checks.screenshotFolder + "/notifications-" + data.tag + ".png");
                }
                api.error = "Chi tiết: " + "Dòng lỗi đầy đủ, không bị cắt mất. ".repeat(180);
                api.notify("Thông tin: " + "Nội dung dài. ".repeat(180), false);
                wait(100);
                verify(notifications.height <= notifications.availableHeight);
                const body = findChild(notifications.errorToast, "toastMessage");
                compare(body.text, api.error);
            }
        }
    }
}
