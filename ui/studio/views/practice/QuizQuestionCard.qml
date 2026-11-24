pragma ComponentBehavior: Bound
import QtQuick
import QtQuick.Controls.Basic
import QtQuick.Layouts
import "../.."
import "../.." as Studio

StudioSurface {
    id: card

    readonly property var outcome: service.quizResult ? (service.quizResult.questions || []).find(item => item.id === question.id) : null
    readonly property bool preface: question.type === "preface"
    property int number: 0
    required property var question
    required property var service

    color: Studio.Theme.surfaceContainer
    implicitHeight: questionLayout.implicitHeight + Studio.Theme.space32
    objectName: "quizQuestion-" + question.id

    ColumnLayout {
        id: questionLayout

        anchors.fill: parent
        anchors.margins: Studio.Theme.space16
        spacing: Studio.Theme.space12

        RowLayout {
            Layout.fillWidth: true
            visible: !card.preface

            Label {
                Layout.fillWidth: true
                color: Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                font.weight: Font.DemiBold
                text: "Câu " + card.number
            }
            Label {
                color: card.outcome && card.outcome.status === "CORRECT" ? Studio.Theme.success
                    : card.outcome && card.outcome.status === "INCORRECT" ? Studio.Theme.error : Studio.Theme.textOnSurfaceVariant
                font.pixelSize: Studio.Theme.bodySmall
                font.weight: Font.DemiBold
                objectName: "quizQuestionStatus-" + card.question.id
                text: card.outcome ? card.service.statusText(card.outcome.status) : ""
                visible: !!card.outcome
            }
        }

        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurface
            font.pixelSize: Studio.Theme.bodyLarge
            font.weight: card.preface ? Font.Normal : Font.DemiBold
            text: card.preface ? card.question.text : card.question.question
            textFormat: Text.PlainText
            wrapMode: Text.WordWrap
        }
        Repeater {
            model: card.question.options || []

            delegate: RadioButton {
                id: optionButton

                required property int index
                required property string modelData
                readonly property bool correctAnswer: !!card.outcome && card.outcome.correct_answer === index
                readonly property bool wrongAnswer: !!card.outcome && card.outcome.status === "INCORRECT" && card.outcome.selected === index
                readonly property color answerColor: correctAnswer ? Studio.Theme.success : wrongAnswer ? Studio.Theme.error
                    : checked ? Studio.Theme.primary : Studio.Theme.textOnSurfaceVariant

                Layout.fillWidth: true
                Accessible.name: text + (correctAnswer ? ", đáp án đúng" : wrongAnswer ? ", bạn chọn sai" : "")
                checked: !!card && card.service.answers[card.question.id] === index
                enabled: !card.service.submitting
                font.pixelSize: Studio.Theme.bodyMedium
                implicitHeight: Math.max(Studio.Theme.controlHeight, contentItem.implicitHeight + topPadding + bottomPadding)
                padding: Studio.Theme.space12
                spacing: Studio.Theme.space12
                objectName: "quizOption-" + card.question.id + "-" + index
                text: modelData

                background: Rectangle {
                    radius: Studio.Theme.shapeMedium
                    color: optionButton.correctAnswer ? Studio.Theme.successContainer : optionButton.wrongAnswer ? Studio.Theme.errorContainer
                        : optionButton.checked ? Studio.Theme.primaryContainer
                        : optionButton.hovered ? Studio.Theme.surfaceContainerHigh : Studio.Theme.surface
                    border.width: optionButton.visualFocus ? Studio.Theme.focusWidth : 1
                    border.color: optionButton.visualFocus ? Studio.Theme.primary
                        : optionButton.correctAnswer || optionButton.wrongAnswer || optionButton.checked ? optionButton.answerColor : Studio.Theme.outlineVariant
                }
                indicator: Rectangle {
                    x: optionButton.leftPadding
                    y: (optionButton.height - height) / 2
                    width: Studio.Theme.iconSmall
                    height: width
                    radius: width / 2
                    color: "transparent"
                    border.width: optionButton.correctAnswer || optionButton.wrongAnswer ? 0 : 2
                    border.color: optionButton.answerColor

                    Studio.Icon {
                        anchors.centerIn: parent
                        size: Studio.Theme.iconSmall
                        name: optionButton.correctAnswer ? "check_circle" : "close"
                        color: optionButton.answerColor
                        visible: optionButton.correctAnswer || optionButton.wrongAnswer
                    }
                    Rectangle {
                        anchors.centerIn: parent
                        width: 10
                        height: width
                        radius: width / 2
                        color: optionButton.answerColor
                        visible: optionButton.checked && !optionButton.correctAnswer && !optionButton.wrongAnswer
                    }
                }
                contentItem: Label {
                    color: optionButton.correctAnswer ? Studio.Theme.success : optionButton.wrongAnswer ? Studio.Theme.error : Studio.Theme.textOnSurface
                    font.family: Studio.Theme.fontFamily
                    font.pixelSize: optionButton.font.pixelSize
                    font.strikeout: optionButton.wrongAnswer
                    leftPadding: optionButton.indicator.width + optionButton.spacing
                    text: optionButton.text
                    textFormat: Text.PlainText
                    verticalAlignment: Text.AlignVCenter
                    wrapMode: Text.Wrap
                }

                onClicked: card.service.setAnswer(card.question.id, index)
            }
        }
        Label {
            Layout.fillWidth: true
            color: Studio.Theme.textOnSurfaceVariant
            font.pixelSize: Studio.Theme.bodySmall
            lineHeight: 1.3
            text: card.outcome ? card.outcome.explanation || "" : ""
            textFormat: Text.PlainText
            visible: text.length > 0 && !card.preface
            wrapMode: Text.WordWrap
        }
    }
}
