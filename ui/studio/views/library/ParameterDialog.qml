pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

Studio.StudioDialog {
    id: dialog

    property var lab: null
    property var parameters: []
    property Item returnFocus: null
    property var values: ({})

    signal parametersAccepted(var lab, var values)

    function decode(value) {
        if (Array.isArray(value))
            return value;
        try {
            return value ? JSON.parse(value) : [];
        } catch (error) {
            return [];
        }
    }
    function openFor(selectedLab) {
        lab = selectedLab;
        parameters = decode(selectedLab ? selectedLab.parameters : "");
        values = {};
        errorLabel.text = "";
        if (parameters.length > 0)
            open();
        else
            parametersAccepted(lab, values);
    }
    function setValue(identifier, value) {
        const updated = Object.assign({}, values);
        if (value === null || value === undefined)
            delete updated[identifier];
        else
            updated[identifier] = String(value);
        values = updated;
    }
    function valid() {
        for (const parameter of parameters) {
            const value = values[parameter.id];
            if (value === undefined)
                continue;
            let size = 0;
            try {
                size = encodeURIComponent(value).replace(/%[0-9A-F]{2}/gi, "x").length;
            } catch (problem) {
                size = 1025;
            }
            if (size > 1024 || value.includes("\u0000")) {
                errorLabel.text = "Tham số " + parameter.id + " phải là văn bản hợp lệ, tối đa 1024 byte.";
                return false;
            }
            if (parameter.type === "integer" && (!/^-?[0-9]+$/.test(value) || value.length > 11 || Number(value) < -2147483648 || Number(value) > 2147483647)) {
                errorLabel.text = "Tham số " + parameter.id + " phải là số nguyên 32-bit.";
                return false;
            }
            if (parameter.type === "boolean" && !["true", "false"].includes(value)) {
                errorLabel.text = "Tham số " + parameter.id + " phải là true hoặc false.";
                return false;
            }
            if (parameter.type === "choice" && !(parameter.choices || []).includes(value)) {
                errorLabel.text = "Tham số " + parameter.id + " không nằm trong danh sách lựa chọn.";
                return false;
            }
        }
        errorLabel.text = "";
        return true;
    }

    anchors.centerIn: parent
    closePolicy: Popup.CloseOnEscape
    focus: true
    height: Math.min(620, parent ? parent.height - Studio.Theme.space32 : 620)
    modal: true
    objectName: "parameterDialog"
    padding: Studio.Theme.space16
    parent: Overlay.overlay
    width: Math.min(620, parent ? parent.width - Studio.Theme.space32 : 620)

    contentItem: ColumnLayout {
        spacing: Studio.Theme.space12

        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            text: dialog.lab ? dialog.lab.name + " yêu cầu một số giá trị trước khi khởi động." : ""
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
        }
        ScrollView {
            id: parameterScroll

            Layout.fillHeight: true
            Layout.fillWidth: true
            clip: true
            contentWidth: availableWidth

            ColumnLayout {
                spacing: Studio.Theme.space12
                width: parameterScroll.availableWidth

                Repeater {
                    model: dialog.parameters

                    delegate: ParameterField {
                        id: parameterRow

                        required property var modelData

                        Layout.fillWidth: true
                        parameter: modelData
                        value: dialog.values[modelData.id]

                        onValueEdited: nextValue => dialog.setValue(modelData.id, nextValue)
                    }
                }
            }
        }
        Label {
            id: errorLabel

            Layout.fillWidth: true
            color: Studio.Theme.error
            textFormat: Text.PlainText
            visible: text.length > 0
            wrapMode: Text.WordWrap
        }
    }
    footer: RowLayout {
        spacing: Studio.Theme.space8

        Item {
            Layout.fillWidth: true
        }
        StudioButton {
            flat: true
            text: "Hủy"

            onClicked: dialog.reject()
        }
        StudioButton {
            highlighted: true
            iconName: "play_arrow"
            objectName: "startWithParametersButton"
            text: "Bắt đầu bài"

            onClicked: if (dialog.valid()) {
                dialog.parametersAccepted(dialog.lab, dialog.values);
                dialog.close();
            }
        }
    }
    header: RowLayout {
        implicitHeight: Studio.Theme.appBarHeight

        Label {
            Layout.fillWidth: true
            Layout.leftMargin: Studio.Theme.space16
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.titleMedium
            text: "Thiết lập tham số"
        }
        StudioIconButton {
            Layout.rightMargin: Studio.Theme.space8
            description: "Hủy mở bài"
            iconName: "close"

            onClicked: dialog.reject()
        }
    }
}
