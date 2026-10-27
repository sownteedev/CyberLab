pragma ComponentBehavior: Bound

import QtQuick
import QtQuick.Controls.Basic
import ".."
import ".." as Studio

ComboBox {
    id: control
    implicitHeight: Studio.Theme.controlHeight
    implicitWidth: 160
    leftPadding: Studio.Theme.space16
    rightPadding: Studio.Theme.controlHeight
    font.family: Studio.Theme.fontFamily
    font.pixelSize: Studio.Theme.bodyMedium
    focusPolicy: Qt.StrongFocus
    Accessible.name: displayText
    contentItem: Text {
        text: control.displayText
        font: control.font
        color: control.enabled ? Studio.Theme.textOnSurface : Studio.Theme.textOnSurfaceVariant
        verticalAlignment: Text.AlignVCenter
        elide: Text.ElideRight
    }
    indicator: Icon {
        x: control.width - width - Studio.Theme.space16
        y: (control.height - height) / 2
        name: "chevron_right"
        rotation: control.popup.visible ? -90 : 90
        color: Studio.Theme.textOnSurfaceVariant
    }
    background: Rectangle {
        color: Studio.Theme.surfaceContainerHigh
        radius: Studio.Theme.shapeSmall
        border.color: control.visualFocus ? Studio.Theme.primary : Studio.Theme.outline
        border.width: control.visualFocus ? Studio.Theme.focusWidth : Studio.Theme.borderWidth
    }
    delegate: ItemDelegate {
        id: option
        required property int index
        required property var modelData
        width: control.popup.availableWidth
        implicitHeight: Studio.Theme.controlHeight
        highlighted: control.highlightedIndex === index
        text: control.textRole ? modelData[control.textRole] : String(modelData)
        font: control.font
        leftPadding: Studio.Theme.space16
        rightPadding: Studio.Theme.space16
        contentItem: Text {
            text: option.text
            font: control.font
            color: Studio.Theme.textOnSurface
            elide: Text.ElideRight
            verticalAlignment: Text.AlignVCenter
        }
        background: Rectangle {
            color: option.highlighted ? Studio.Theme.secondaryContainer : Studio.Theme.transparent
            radius: Studio.Theme.shapeSmall
        }
    }
    popup: Popup {
        y: control.height + Studio.Theme.space8
        width: control.width
        padding: Studio.Theme.space8
        implicitHeight: Math.min(contentItem.implicitHeight + topPadding + bottomPadding, 280)
        closePolicy: Popup.CloseOnEscape | Popup.CloseOnPressOutsideParent
        contentItem: ListView {
            implicitHeight: contentHeight
            clip: true
            model: control.popup.visible ? control.delegateModel : null
            currentIndex: control.highlightedIndex
            ScrollIndicator.vertical: ScrollIndicator {}
        }
        background: Rectangle { color: Studio.Theme.surfaceContainerHigh; radius: Studio.Theme.shapeLarge; border.color: Studio.Theme.outlineVariant; border.width: Studio.Theme.borderWidth }
        enter: Transition { NumberAnimation { property: "opacity"; from: 0; to: 1; duration: Studio.Theme.enterDuration } }
        exit: Transition { NumberAnimation { property: "opacity"; to: 0; duration: Studio.Theme.exitDuration } }
    }
}
