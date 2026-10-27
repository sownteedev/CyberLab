pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: field
    required property var parameter
    property var value
    readonly property string defaultLabel: parameter.default !== undefined && parameter.default !== null
        ? "Mặc định: " + (parameter.default === "" ? "chuỗi rỗng" : String(parameter.default)) : "Tự sinh theo phiên"
    signal valueEdited(var nextValue)
    spacing: Studio.Theme.space4

    RowLayout {
        Layout.fillWidth: true
        Label {
            Layout.fillWidth: true
            text: field.parameter.id + (field.parameter.description ? " · " + field.parameter.description : "")
            textFormat: Text.PlainText
            color: Studio.Theme.textOnSurface
            wrapMode: Text.WordWrap
        }
        StudioIconButton {
            objectName: "parameterDefault-" + field.parameter.id
            iconName: "refresh"
            description: "Bỏ giá trị riêng, dùng mặc định"
            enabled: field.value !== undefined
            onClicked: field.valueEdited(undefined)
        }
    }
    Loader {
        Layout.fillWidth: true
        sourceComponent: field.parameter.type === "choice" ? choiceEditor
            : field.parameter.type === "boolean" ? booleanEditor : textEditor
    }
    Component {
        id: textEditor
        StudioTextField {
            objectName: "parameterInput-" + field.parameter.id
            text: field.value === undefined ? "" : String(field.value)
            placeholderText: field.value === undefined ? field.defaultLabel
                : field.parameter.type === "integer" ? "Nhập số nguyên" : "Chuỗi rỗng"
            Accessible.name: field.parameter.id
            onTextEdited: field.valueEdited(text)
        }
    }
    Component {
        id: choiceEditor
        StudioComboBox {
            objectName: "parameterInput-" + field.parameter.id
            model: [field.defaultLabel].concat(field.parameter.choices || [])
            currentIndex: field.value === undefined ? 0 : (field.parameter.choices || []).indexOf(field.value) + 1
            Accessible.name: field.parameter.id
            onActivated: field.valueEdited(currentIndex === 0 ? undefined : currentText)
        }
    }
    Component {
        id: booleanEditor
        StudioComboBox {
            objectName: "parameterInput-" + field.parameter.id
            model: [field.defaultLabel, "false", "true"]
            currentIndex: field.value === undefined ? 0 : field.value === "true" ? 2 : 1
            Accessible.name: field.parameter.id
            onActivated: field.valueEdited(currentIndex === 0 ? undefined : currentText)
        }
    }
}
