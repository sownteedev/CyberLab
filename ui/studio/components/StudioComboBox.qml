pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

ComboBox {
    id: control

    Accessible.name: displayText
    focusPolicy: Qt.StrongFocus
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    implicitHeight: Studio.Theme.controlHeight
    implicitWidth: 160
    leftPadding: Studio.Theme.space16
    rightPadding: Studio.Theme.controlHeight

    background: Rectangle {
        border.color: control.visualFocus ? Studio.Theme.primary : Studio.Theme.outline
        border.width: control.visualFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
        color: Studio.Theme.surfaceContainerHigh
        radius: Studio.Theme.shapeSmall
    }
    contentItem: Text {
        color: control.enabled ? Studio.Theme.textOnSurface : Studio.Theme.textOnSurfaceVariant
        elide: Text.ElideRight
        font: control.font
        text: control.displayText
        verticalAlignment: Text.AlignVCenter
    }
    delegate: ItemDelegate {
        id: option

        required property int index
        required property var modelData

        font: control.font
        hoverEnabled: false
        highlighted: control.highlightedIndex === index
        implicitHeight: Studio.Theme.controlHeight
        leftPadding: Studio.Theme.space16
        rightPadding: Studio.Theme.space16
        text: control.textRole ? modelData[control.textRole] : String(modelData)
        width: control.popup.availableWidth

        background: Rectangle {
            color: option.highlighted ? Studio.Theme.secondaryContainer
                : pointer.hovered ? Studio.Theme.surfaceContainerHighest : Studio.Theme.transparent
            radius: Studio.Theme.shapeSmall
            Behavior on color { ColorAnimation { duration: Studio.Theme.stateDuration } }
        }
        HoverHandler { id: pointer }
        contentItem: Text {
            color: Studio.Theme.textOnSurface
            elide: Text.ElideRight
            font: control.font
            text: option.text
            verticalAlignment: Text.AlignVCenter
        }
    }
    indicator: Icon {
        color: Studio.Theme.textOnSurfaceVariant
        name: "chevron_right"
        rotation: control.popup.visible ? -90 : 90
        Behavior on rotation { NumberAnimation { duration: Studio.Theme.stateDuration; easing.type: Easing.OutCubic } }
        x: control.width - width - Studio.Theme.space16
        y: (control.height - height) / 2
    }
    popup: Popup {
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        implicitHeight: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, 280)
        padding: Studio.Theme.space8
        width: control.width
        y: control.height + Studio.Theme.space8

        background: Studio.StudioPopupSurface {
            border.color: Studio.Theme.outlineVariant
            border.width: Studio.Theme.borderWidth
            color: Studio.Theme.surfaceContainerHigh
            radius: Studio.Theme.shapeLarge
        }
        contentItem: ListView {
            clip: true
            currentIndex: control.highlightedIndex
            implicitHeight: contentHeight
            model: control.popup.visible ? control.delegateModel : null

            ScrollIndicator.vertical: ScrollIndicator {
            }
        }
        enter: Transition {
            NumberAnimation {
                duration: Studio.Theme.enterDuration
                from: 0
                property: "opacity"
                to: 1
            }
        }
        exit: Transition {
            NumberAnimation {
                duration: Studio.Theme.exitDuration
                property: "opacity"
                to: 0
            }
        }
    }
}
