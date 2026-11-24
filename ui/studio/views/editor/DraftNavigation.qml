pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.." as Studio

Control {
    id: navigation

    required property var sections
    required property var editor
    property bool compact: false

    function choose(index) {
        if (!enabled)
            return;
        editor.section = Math.max(0, Math.min(sections.length - 1, index));
        const target = destinations.itemAt(editor.section);
        if (target)
            target.forceActiveFocus(Qt.TabFocusReason);
        reveal(editor.section);
    }

    function reveal(index) {
        const target = destinations.itemAt(index);
        const flick = scroll.contentItem as Flickable;
        if (!target || !flick)
            return;
        const bounds = target.mapToItem(destinationColumn, 0, 0, target.width, target.height);
        const maximum = Math.max(0, flick.contentHeight - flick.height);
        const top = Math.min(bounds.y, Math.max(flick.contentY, bounds.y + bounds.height - flick.height));
        flick.contentY = Math.max(0, Math.min(maximum, top));
    }

    objectName: "draftSectionNavigation"
    padding: compact ? Studio.Theme.space8 : Studio.Theme.space12
    implicitHeight: 500
    implicitWidth: compact ? 72 : 216
    background: Rectangle {
        color: Studio.Theme.surfaceContainerLow
        radius: Studio.Theme.shapeExtraLarge
    }
    contentItem: ScrollView {
        id: scroll
        clip: true
        contentWidth: availableWidth
        ScrollBar.horizontal.policy: ScrollBar.AlwaysOff

        ColumnLayout {
            id: destinationColumn
            width: scroll.availableWidth
            spacing: Studio.Theme.space4

            Repeater {
                id: destinations
                model: navigation.sections

                FocusScope {
                    id: group
                    required property int index
                    required property var modelData
                    Layout.fillWidth: true
                    implicitHeight: groupContent.implicitHeight

                    ColumnLayout {
                        id: groupContent
                        anchors.fill: parent
                        spacing: Studio.Theme.space8
                        Label {
                            Layout.fillWidth: true
                            Layout.leftMargin: Studio.Theme.space12
                            Layout.topMargin: group.index === 0 ? Studio.Theme.space8 : Studio.Theme.space16
                            Layout.bottomMargin: Studio.Theme.space4
                            color: Studio.Theme.textOnSurfaceVariant
                            font.pixelSize: Studio.Theme.labelMedium
                            text: group.index === 0 ? qsTr("NỘI DUNG") : qsTr("HOÀN THIỆN")
                            visible: !navigation.compact && (group.index === 0 || group.index === 5)
                        }
                        Rectangle {
                            Layout.fillWidth: true
                            Layout.leftMargin: Studio.Theme.space8
                            Layout.rightMargin: Studio.Theme.space8
                            Layout.topMargin: Studio.Theme.space8
                            Layout.bottomMargin: Studio.Theme.space4
                            implicitHeight: Studio.Theme.borderWidth
                            color: Studio.Theme.outlineVariant
                            visible: navigation.compact && group.index === 5
                        }
                        Studio.StudioButton {
                            id: destination
                            focus: true
                            Layout.fillWidth: true
                            Layout.minimumWidth: Studio.Theme.controlHeight
                            Accessible.role: Accessible.PageTab
                            Accessible.selected: selected
                            flat: true
                            leading: !navigation.compact
                            iconName: group.modelData.icon
                            iconOnly: navigation.compact
                            iconSize: navigation.compact ? Studio.Theme.iconSize : Studio.Theme.iconSmall
                            leftPadding: navigation.compact ? 0 : Studio.Theme.space16
                            rightPadding: leftPadding
                            selected: navigation.editor.section === group.index
                            objectName: "draftSection-" + group.index
                            text: group.modelData.label
                            onClicked: navigation.editor.section = group.index
                            onActiveFocusChanged: if (activeFocus) navigation.reveal(group.index)
                            Keys.onUpPressed: navigation.choose(group.index - 1)
                            Keys.onDownPressed: navigation.choose(group.index + 1)
                            Keys.onPressed: event => {
                                if (event.key === Qt.Key_Home || event.key === Qt.Key_End) {
                                    navigation.choose(event.key === Qt.Key_Home ? 0 : navigation.sections.length - 1);
                                    event.accepted = true;
                                }
                            }
                        }
                    }
                }
            }
        }
    }
}
