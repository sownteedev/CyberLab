import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

Studio.StudioDialog {
    id: dialog

    property Item returnFocus: null
    property int sectionIndex: 0
    required property var terminals
    property var guiPreferences: null
    property var updater: null
    readonly property var sections: [{ label: qsTr("Giao diện"), icon: "palette" }, { label: qsTr("Terminal"), icon: "terminal" }, { label: qsTr("Máy lab"), icon: "desktop_windows" }, { label: qsTr("Ứng dụng"), icon: "apps" }].concat(dialog.updater ? [{label: qsTr("Cập nhật"), icon: "download"}] : [])
    signal updateRequested()

    function focusSection() {
        if (settingsContent.item)
            settingsContent.item.focusSelection();
    }
    function showSection(index) {
        sectionIndex = index;
        Qt.callLater(focusSection);
    }

    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutside
    focus: true
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    height: Math.min(Studio.Theme.settingsHeight, parent ? parent.height - Studio.Theme.space32 : Studio.Theme.settingsHeight)
    modal: true
    objectName: "settingsDialog"
    padding: Studio.Theme.space24
    topPadding: Studio.Theme.space8
    bottomPadding: Studio.Theme.space16
    parent: Overlay.overlay
    title: qsTr("Cài đặt")
    width: Math.min(Studio.Theme.settingsWidth, parent ? parent.width - Studio.Theme.space32 : Studio.Theme.settingsWidth)

    contentItem: ColumnLayout {
        spacing: Studio.Theme.space16

        Studio.StudioSegmentedTabs {
            Layout.fillWidth: true
            visible: dialog.width >= 600
            currentIndex: dialog.sectionIndex
            entries: dialog.sections
            itemPrefix: "settingsSection-"
            objectName: "settingsSections"

            onSelected: index => dialog.sectionIndex = index
        }
        Studio.StudioComboBox {
            Layout.fillWidth: true
            visible: dialog.width < 600
            objectName: "settingsSectionPicker"
            Accessible.name: qsTr("Mục cài đặt")
            model: dialog.sections
            textRole: "label"
            currentIndex: dialog.sectionIndex
            onActivated: dialog.showSection(currentIndex)
        }
        ScrollView {
            id: settingsScroll

            Layout.fillHeight: true
            Layout.fillWidth: true
            clip: true
            contentWidth: availableWidth
            objectName: "settingsScroll"

            Loader {
                id: settingsContent

                height: item ? item.implicitHeight : 0
                sourceComponent: dialog.sectionIndex === 0 ? appearancePage : dialog.sectionIndex === 1 ? terminalPage : dialog.sectionIndex === 2 ? labAccountPage : dialog.sectionIndex === 4 && dialog.updater ? updatePage : guiPage
                width: settingsScroll.availableWidth
            }
        }
    }
    header: Studio.StudioDialogHeader {
        title: dialog.title
        iconName: "settings"
        closeDescription: qsTr("Đóng cài đặt")
        closeObjectName: "closeSettingsButton"
        onCloseRequested: dialog.close()
    }
    footer: Studio.StudioDialogFooter {
        contentItem: RowLayout {
            spacing: Studio.Theme.space16

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                text: dialog.sectionIndex === 4 ? qsTr("Chỉ cập nhật khi bạn xác nhận.") : dialog.sectionIndex === 2 ? qsTr("Username chỉ áp dụng sau khi nhấn Lưu.") : qsTr("Tự lưu thay đổi. Không ảnh hưởng bài lab.")
                wrapMode: Text.WordWrap
            }
            StudioButton {
                flat: true
                objectName: "doneSettingsButton"
                text: qsTr("Xong")

                onClicked: dialog.close()
            }
        }
    }

    onClosed: if (returnFocus)
        returnFocus.forceActiveFocus(Qt.TabFocusReason)
    onOpened: {
        terminals.refresh();
        if (guiPreferences)
            guiPreferences.refresh();
        focusSection();
    }

    Component {
        id: updatePage
        UpdateSettings { updater: dialog.updater; onUpdateRequested: dialog.updateRequested() }
    }
    Component {
        id: guiPage

        GuiSettings { preferences: dialog.guiPreferences }
    }
    Component {
        id: appearancePage

        AppearanceSettings { }
    }
    Component {
        id: labAccountPage

        LabAccountSettings { }
    }
    Component {
        id: terminalPage

        TerminalSettings {
            preferences: dialog.terminals
        }
    }
}
