import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import QtTest
import ".." as Studio

Item {
    id: checks
    property string screenshotFolder: ""

    ApplicationWindow {
        id: window
        width: 840
        height: 680
        visible: true
        color: Studio.Theme.surface
        palette: Studio.Theme.controlPalette

        ColumnLayout {
            anchors.fill: parent
            anchors.margins: 32
            spacing: 16
            Label {
                text: "Bộ điều khiển CyberLab"
                font.pixelSize: Studio.Theme.headlineMedium
                font.weight: Font.DemiBold
                color: Studio.Theme.textOnSurface
            }
            RowLayout {
                Studio.StudioButton { id: primary; text: "Bắt đầu"; iconName: "play_arrow"; highlighted: true }
                Studio.StudioButton { text: "Lưu bản nháp"; iconName: "save" }
                Studio.StudioButton { id: outlined; text: "Nhập bài"; outlined: true }
                Studio.StudioIconButton { id: tooltipButton; description: "Bản nháp / Tạo mới"; iconName: "add" }
                Studio.StudioButton { text: "Xóa"; danger: true; iconName: "delete" }
            }
            Studio.StudioToggle { id: toggle; Layout.fillWidth: true; text: "Cho phép kết nối Internet" }
            Studio.StudioCheckBox { id: checkbox; Layout.fillWidth: true; text: "Thu thập bằng chứng thực hành" }
            Studio.StudioTextField { id: input; Layout.fillWidth: true; placeholderText: "Tên bài thực hành" }
            Studio.StudioTextField { Layout.fillWidth: true; placeholderText: "Địa chỉ IP không hợp lệ"; error: true }
            Studio.StudioComboBox { Layout.fillWidth: true; model: ["Chuẩn bị trước thực hành", "Ôn tập sau thực hành"] }
            Studio.StudioSurface {
                Layout.fillWidth: true
                implicitHeight: 100
                Label {
                    anchors.centerIn: parent
                    text: "Nội dung và trạng thái luôn rõ ràng"
                    color: Studio.Theme.textOnSurface
                }
            }
            Item { Layout.fillHeight: true }
        }
        SignalSpy { id: clicks; target: primary; signalName: "clicked" }
        TestCase {
            name: "StudioComponents"
            when: window.visible
            function init() {
                Studio.Theme.themeMode = "dark";
                Studio.Theme.reducedMotion = true;
                toggle.checked = false;
                primary.busy = false;
                checkbox.enabled = true;
                checkbox.tristate = false;
                checkbox.checked = false;
                toggle.enabled = true;
                toggle.text = "Cho phép kết nối Internet";
                clicks.clear();
                window.requestActivate();
                tryCompare(window, "active", true);
                waitForRendering(window.contentItem);
            }
            function cleanup() { mouseRelease(primary); }
            function test_tooltip_follows_theme() {
                const tooltip = tooltipButton.ToolTip.toolTip;
                tooltipButton.ToolTip.timeout = -1;
                tooltipButton.ToolTip.show(tooltipButton.description);
                try {
                    tryCompare(tooltip, "opened", true);
                    for (const mode of ["dark", "light", "dark"]) {
                        Studio.Theme.themeMode = mode;
                        tryCompare(tooltip.background, "color", Studio.Theme.surfaceContainerHigh);
                        compare(tooltip.contentItem.color, Studio.Theme.textOnSurface);
                        compare(tooltip.background.border.color, Studio.Theme.outlineVariant);
                        verify(contrast(tooltip.contentItem.color, tooltip.background.color) >= 4.5);
                        if (checks.screenshotFolder) {
                            wait(50);
                            grabImage(window.contentItem).save(checks.screenshotFolder + "/tooltip-" + mode + ".png");
                        }
                    }
                } finally {
                    tooltipButton.ToolTip.hide();
                    tooltipButton.ToolTip.timeout = 4000;
                }
            }
            function luminance(color) {
                const values = [color.r, color.g, color.b].map(value => value <= 0.04045 ? value / 12.92 : Math.pow((value + 0.055) / 1.055, 2.4));
                return values[0] * 0.2126 + values[1] * 0.7152 + values[2] * 0.0722;
            }
            function contrast(first, second) {
                const firstValue = luminance(first);
                const secondValue = luminance(second);
                return (Math.max(firstValue, secondValue) + 0.05) / (Math.min(firstValue, secondValue) + 0.05);
            }
            function test_outline_is_not_filled() {
                compare(outlined.background.color.a, 0);
                compare(outlined.foreground, Studio.Theme.primary);
            }
            function test_flat_selection_keeps_fill() {
                outlined.flat = true;
                outlined.selected = true;
                compare(outlined.background.color, Studio.Theme.primaryContainer);
                outlined.selected = false;
                outlined.flat = false;
            }
            function test_toggle_reduced_motion() {
                const handle = findChild(toggle, "toggleHandle");
                verify(handle !== undefined);
                toggle.checked = true;
                wait(0);
                const start = handle.x;
                wait(150);
                compare(handle.x, start, "Reduced motion must snap immediately");
            }
            function test_button_shape_response() {
                mousePress(primary);
                wait(180);
                verify(primary.background.radius < primary.background.height / 2);
                mouseRelease(primary);
                compare(clicks.count, 1);
            }
            function test_focus_and_keyboard() {
                input.forceActiveFocus(Qt.TabFocusReason);
                primary.forceActiveFocus(Qt.TabFocusReason);
                verify(primary.visualFocus);
                keyClick(Qt.Key_Space);
                compare(clicks.count, 1);
                tryCompare(primary.background.border, "width", Studio.Theme.focusWidth);
            }
            function test_busy_and_disabled_buttons_do_not_activate() {
                primary.busy = true;
                verify(!primary.enabled);
                mouseClick(primary);
                keyClick(Qt.Key_Space);
                compare(clicks.count, 0);
                primary.busy = false;
                verify(primary.enabled);
            }
            function test_checkbox_keyboard_partial_and_disabled() {
                input.forceActiveFocus(Qt.TabFocusReason);
                checkbox.forceActiveFocus(Qt.TabFocusReason);
                verify(checkbox.visualFocus);
                compare(checkbox.background.border.width, Studio.Theme.focusWidth);
                keyClick(Qt.Key_Space);
                verify(checkbox.checked);
                checkbox.tristate = true;
                checkbox.checkState = Qt.PartiallyChecked;
                compare(checkbox.indicator.color, Studio.Theme.primary);
                keyClick(Qt.Key_Space);
                compare(checkbox.checkState, Qt.Checked);
                checkbox.enabled = false;
                mouseClick(checkbox);
                keyClick(Qt.Key_Space);
                compare(checkbox.checkState, Qt.Checked);
            }
            function test_toggle_long_label_hover_and_keyboard() {
                toggle.text = "Cho phép các máy trong mạng thực hành kết nối Internet để cài phần mềm và tải các tài liệu cần thiết cho bài thực hành";
                input.forceActiveFocus(Qt.TabFocusReason);
                toggle.forceActiveFocus(Qt.TabFocusReason);
                keyClick(Qt.Key_Space);
                verify(toggle.checked);
                mouseMove(toggle, 10, toggle.height / 2);
                verify(toggle.hovered);
                verify(toggle.background.color.a > 0);
                verify(toggle.contentItem.height >= toggle.contentItem.contentHeight);
                toggle.enabled = false;
                mouseClick(toggle);
                verify(toggle.checked);
            }
            function test_text_and_control_contrast_data() {
                return [{tag: "dark", mode: "dark"}, {tag: "light", mode: "light"}];
            }
            function test_text_and_control_contrast(data) {
                Studio.Theme.themeMode = data.mode;
                for (const background of [Studio.Theme.surface, Studio.Theme.surfaceContainer, Studio.Theme.surfaceContainerHigh, Studio.Theme.surfaceContainerHighest]) {
                    verify(contrast(Studio.Theme.textOnSurface, background) >= 4.5);
                    verify(contrast(Studio.Theme.textOnSurfaceVariant, background) >= 4.5);
                }
                for (const pair of [[Studio.Theme.primary, Studio.Theme.textOnPrimary], [Studio.Theme.primaryContainer, Studio.Theme.textOnPrimaryContainer], [Studio.Theme.errorContainer, Studio.Theme.textOnErrorContainer], [Studio.Theme.successContainer, Studio.Theme.textOnSuccessContainer]])
                    verify(contrast(pair[0], pair[1]) >= 4.5);
                verify(contrast(input.background.border.color, input.background.color) >= 3, "Input boundary must be visible");
                waitForRendering(window.contentItem);
                if (checks.screenshotFolder)
                    grabImage(window.contentItem).save(checks.screenshotFolder + "/components-" + data.mode + ".png");
            }
        }
    }
}
