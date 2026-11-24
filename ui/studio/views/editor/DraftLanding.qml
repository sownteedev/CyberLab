pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

ScrollView {
    id: landing

    required property var editor
    readonly property bool wide: page.width >= Studio.Theme.compactBreakpoint
    signal resumeRequested

    function reveal(target) {
        const scroller = contentItem as Flickable;
        if (!visible || !scroller || !target)
            return;
        const bounds = target.mapToItem(scroller.contentItem, 0, 0, target.width, target.height);
        const margin = Studio.Theme.space8;
        let position = scroller.contentY;
        if (bounds.y < position + margin)
            position = bounds.y - margin;
        else if (bounds.y + bounds.height > position + scroller.height - margin)
            position = bounds.y + bounds.height - scroller.height + margin;
        scroller.contentY = Math.max(0, Math.min(position, scroller.contentHeight - scroller.height));
    }

    clip: true
    contentWidth: availableWidth
    contentHeight: page.implicitHeight + Studio.Theme.space24 * 2
    objectName: "draftLanding"
    ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

    ColumnLayout {
        id: page

        width: Math.max(0, landing.availableWidth - Studio.Theme.space24)
        x: (landing.availableWidth - width) / 2
        y: Studio.Theme.space24
        objectName: "draftLandingPage"
        spacing: Studio.Theme.space24

        Studio.StudioButton {
            enabled: !landing.editor.backend.busy
            flat: true
            iconName: "arrow_back"
            objectName: "resumeDraftButton"
            text: qsTr("Trở lại bài đang sửa")
            visible: !!landing.editor.draft
            onClicked: landing.resumeRequested()
            onActiveFocusChanged: if (activeFocus) landing.reveal(this)
        }
        ColumnLayout {
            Layout.fillWidth: true
            spacing: Studio.Theme.space8

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurface
                font.pixelSize: Studio.Theme.headlineMedium
                font.weight: Font.DemiBold
                text: qsTr("Bắt đầu một bài lab")
                wrapMode: Text.WordWrap
            }
        }
        GridLayout {
            id: sections

            Layout.fillWidth: true
            columns: landing.wide ? 2 : 1
            columnSpacing: Studio.Theme.space24
            rowSpacing: Studio.Theme.space24

            Studio.DraftCreateCard {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: 380
                Layout.minimumWidth: 0
                editor: landing.editor
                onFocusRequested: target => landing.reveal(target)
            }
            Studio.DraftListPane {
                Layout.fillWidth: true
                Layout.alignment: Qt.AlignTop
                Layout.preferredWidth: 636
                Layout.minimumWidth: 0
                editor: landing.editor
                maximumListHeight: landing.wide
                    ? Math.max(240, landing.availableHeight - page.y - sections.y - Studio.Theme.controlHeight - Studio.Theme.space24 * 4)
                    : 320
                onFocusRequested: target => landing.reveal(target)
            }
        }
    }
}
