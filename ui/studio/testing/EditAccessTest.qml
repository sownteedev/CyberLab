import QtQuick
import QtQuick.Controls.Basic
import QtTest
import "../views/editor" as Editor
import ".." as Studio

Item {
    id: checks
    property string screenshotFolder: ""
    QtObject {
        id: api
        property var callback: null
        property int cancelled: 0
        property var request: null
        function unlockEditing(password, completed) { callback = completed; }
        function setEditPassword(resource, current, replacement, completed) {
            request = {current: current, replacement: replacement};
            callback = completed;
        }
        function cancelEditUnlock() { cancelled++; }
    }
    ApplicationWindow {
        id: window
        visible: true
        width: 800
        height: 700
        color: Studio.Theme.surface
        Editor.EditPasswordDialog { id: dialog; api: api }
        TestCase {
            name: "EditAccess"
            when: windowShown
            function init() {
                window.width = 800;
                window.height = 700;
                Studio.Theme.themeMode = "dark";
                api.request = null;
                window.requestActivate();
                tryCompare(window, "active", true);
                api.cancelled = 0;
                dialog.showUnlock("draft", "fixture", "");
                tryCompare(dialog, "opened", true);
            }
            function cleanup() { dialog.close(); wait(250); }
            function test_wrong_password_keeps_dialog_and_focus() {
                const password = findChild(dialog, "editCurrentPassword");
                password.text = "wrong";
                dialog.submit();
                api.callback(null, "Mật khẩu không đúng.");
                compare(dialog.opened, true);
                compare(password.text, "");
                tryCompare(password, "activeFocus", true);
                verify(dialog.problem.length > 0);
            }
            function test_close_cancels_pending_unlock_and_wipes_fields() {
                const password = findChild(dialog, "editCurrentPassword");
                password.text = "private";
                dialog.reject();
                tryCompare(dialog, "visible", false);
                compare(password.text, "");
                compare(api.cancelled, 1);
            }
            function test_initial_unlock_is_not_an_error() {
                dialog.showUnlock("draft", "fixture", "Bài đã khóa chỉnh sửa. Hãy nhập mật khẩu.");
                compare(dialog.problem, "");
            }
            function test_settings_validation_and_removal() {
                dialog.showSettings("draft", "fixture", true);
                const current = findChild(dialog, "editCurrentPassword");
                const replacement = findChild(dialog, "editNewPassword");
                const confirm = findChild(dialog, "editConfirmPassword");
                current.text = "old";
                replacement.text = "new";
                confirm.text = "different";
                dialog.submit();
                verify(dialog.problem.length > 0);
                compare(api.request, null);
                confirm.text = "new";
                dialog.submit();
                compare(api.request.replacement, "new");
                api.callback(null, "Mật khẩu không đúng.");
                compare(dialog.opened, true);
                current.text = "old";
                dialog.removing = true;
                dialog.submit();
                compare(api.request.replacement, "");
                api.callback({edit_protected: false}, "");
                tryCompare(dialog, "visible", false);
            }
            function test_layout_data() {
                return [
                    {tag: "unlock-dark", settings: false, protectedValue: false, theme: "dark", width: 800, height: 700},
                    {tag: "settings-dark", settings: true, protectedValue: true, theme: "dark", width: 800, height: 800},
                    {tag: "new-light", settings: true, protectedValue: false, theme: "light", width: 800, height: 700},
                    {tag: "settings-compact", settings: true, protectedValue: true, theme: "light", width: 380, height: 540}
                ];
            }
            function test_layout(data) {
                window.width = data.width;
                window.height = data.height;
                Studio.Theme.themeMode = data.theme;
                if (data.settings) dialog.showSettings("draft", "fixture", data.protectedValue);
                wait(300);
                const field = findChild(dialog, data.settings && !data.protectedValue ? "editNewPassword" : "editCurrentPassword");
                const point = field.mapToItem(dialog.contentItem, 0, 0);
                verify(field.width > 200, "Input must have a usable width");
                verify(point.x >= 24, "Input must have a left inset");
                verify(point.x + field.width <= dialog.contentItem.width - 23, "Input must have a right inset");
                verify(dialog.height <= window.height - 31, "Dialog must fit a short window");
                verify(Number.isFinite(dialog.contentItem.implicitHeight));
                if (checks.screenshotFolder) grabImage(window.contentItem).save(checks.screenshotFolder + "/" + data.tag + ".png");
            }
        }
    }
}
