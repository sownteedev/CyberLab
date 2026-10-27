pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

StudioSurface {
    id: card
    required property var question
    required property var service
    readonly property var outcome: service.quizResult
        ? (service.quizResult.questions || []).find(item => item.id === question.id) : null
    readonly property bool preface: question.type === "preface"
    objectName: "quizQuestion-" + question.id
    implicitHeight: questionLayout.implicitHeight + Studio.Theme.space24
    color: Studio.Theme.surfaceContainer

    ColumnLayout {
        id: questionLayout
        anchors.fill: parent
        anchors.margins: Studio.Theme.space12
        spacing: Studio.Theme.space4
        Label {
            Layout.fillWidth: true
            text: card.preface ? card.question.text : card.question.question
            textFormat: Text.PlainText
            color: Studio.Theme.textOnSurface
            wrapMode: Text.WordWrap
            font.pixelSize: card.preface ? Studio.Theme.bodyLarge : Studio.Theme.bodyMedium
        }
        Repeater {
            model: card.question.options || []
            delegate: RadioButton {
                id: optionButton
                required property string modelData
                required property int index
                objectName: "quizOption-" + card.question.id + "-" + index
                Layout.fillWidth: true
                text: modelData
                checked: card.service.answers[card.question.id] === index
                enabled: !card.service.submitting
                onClicked: card.service.setAnswer(card.question.id, index)
                contentItem: Label {
                    leftPadding: optionButton.indicator.width + optionButton.spacing
                    text: optionButton.text
                    font: optionButton.font
                    textFormat: Text.PlainText
                    color: Studio.Theme.textOnSurface
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.WordWrap
                }
            }
        }
        Label {
            Layout.fillWidth: true
            visible: !!card.outcome && !card.preface
            text: card.outcome ? card.service.statusText(card.outcome.status)
                + (card.outcome.explanation ? " · " + card.outcome.explanation : "") : ""
            textFormat: Text.PlainText
            color: card.outcome && card.outcome.status === "CORRECT"
                ? Studio.Theme.success : Studio.Theme.textOnSurfaceVariant
            wrapMode: Text.WordWrap
            font.pixelSize: Studio.Theme.bodySmall
        }
    }
}
