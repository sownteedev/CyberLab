pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: field

    readonly property string defaultLabel: parameter.default !== undefined && parameter.default !== null ? "Mặc định: " + (parameter.default === "" ? "chuỗi rỗng" : String(parameter.default)) : "Tự sinh theo phiên"
    required property var parameter
    property var value

    signal valueEdited(var nextValue)

    spacing: Studio.Theme.space4

    RowLayout {
        Layout.fillWidth: true

        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurface
            text: field.parameter.id + (field.parameter.description ? " · " + field.parameter.description : "")
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
        }
        StudioIconButton {
            description: "Bỏ giá trị riêng, dùng mặc định"
            enabled: field.value !== undefined
            iconName: "refresh"
            objectName: "parameterDefault-" + field.parameter.id

            onClicked: field.valueEdited(undefined)
        }
    }
    Loader {
        Layout.fillWidth: true
        sourceComponent: field.parameter.type === "choice" ? choiceEditor : field.parameter.type === "boolean" ? booleanEditor : textEditor
    }
    Component {
        id: textEditor

        StudioTextField {
            Accessible.name: field.parameter.id
            objectName: "parameterInput-" + field.parameter.id
            placeholderText: field.value === undefined ? field.defaultLabel : field.parameter.type === "integer" ? "Nhập số nguyên" : "Chuỗi rỗng"
            text: field.value === undefined ? "" : String(field.value)

            onTextEdited: field.valueEdited(text)
        }
    }
    Component {
        id: choiceEditor

        StudioComboBox {
            Accessible.name: field.parameter.id
            currentIndex: field.value === undefined ? 0 : (field.parameter.choices || []).indexOf(field.value) + 1
            model: [field.defaultLabel].concat(field.parameter.choices || [])
            objectName: "parameterInput-" + field.parameter.id

            onActivated: field.valueEdited(currentIndex === 0 ? undefined : currentText)
        }
    }
    Component {
        id: booleanEditor

        StudioComboBox {
            Accessible.name: field.parameter.id
            currentIndex: field.value === undefined ? 0 : field.value === "true" ? 2 : 1
            model: [field.defaultLabel, "false", "true"]
            objectName: "parameterInput-" + field.parameter.id

            onActivated: field.valueEdited(currentIndex === 0 ? undefined : currentText)
        }
    }
}
