import QtQuick
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: page

    property int category: 0
    required property var editor

    spacing: Studio.Theme.space12

    Studio.StudioSegmentedTabs {
        Accessible.name: "Results, Goals và Quiz"
        Layout.fillWidth: true
        currentIndex: page.category
        entries: [{label: "Results", icon: "description"}, {label: "Goals", icon: "check_circle"}, {label: "Quiz", icon: "help"}]
        itemPrefix: "labeditTab-"
        objectName: "labeditCategory"

        onSelected: index => page.category = index
    }
    Studio.DraftFormCard {
        Layout.fillWidth: true
        Loader {
            id: content
            Layout.fillWidth: true
            objectName: "labeditContent"
            sourceComponent: [results, goals, quiz][page.category]
        }
    }
    Studio.EditorDisclosure {
        id: advanced
        title: "Nâng cao"
        objectName: "labeditAdvanced"

        StudioComboBox {
            id: advancedCategory
            Accessible.name: "Cấu hình nâng cao"
            Layout.fillWidth: true
            model: ["Thiết lập", "Tham số", "File nộp bài"]
            objectName: "labeditAdvancedCategory"
        }
        Studio.DraftFormCard {
            Layout.fillWidth: true
            Loader {
                Layout.fillWidth: true
                active: page.visible && advanced.expanded
                sourceComponent: [settings, parameters, artifacts][advancedCategory.currentIndex]
            }
        }
    }
    Component {
        id: settings

        LabeditSettings {
            editor: page.editor
        }
    }
    Component {
        id: parameters

        LabeditParameters {
            editor: page.editor
        }
    }
    Component {
        id: artifacts

        LabeditArtifacts {
            editor: page.editor
        }
    }
    Component {
        id: results

        LabeditResults {
            editor: page.editor
        }
    }
    Component {
        id: goals

        LabeditGoals {
            editor: page.editor
        }
    }
    Component {
        id: quiz

        LabeditQuiz {
            editor: page.editor
        }
    }
}
