import QtQuick
import QtQuick.Layouts
import "../.."
import "../.." as Studio

ColumnLayout {
    id: page
    required property var editor
    property int category: 0
    spacing: Studio.Theme.space12
    SectionHeader {
        Layout.fillWidth: true
        title: "Nội dung bài thực hành"
        titleSize: Studio.Theme.titleMedium
    }
    StudioComboBox {
        objectName: "labeditCategory"
        Layout.fillWidth: true
        model: ["Thiết lập", "Tham số", "Bằng chứng", "Điều kiện", "Mục tiêu", "Câu hỏi"]
        currentIndex: page.category
        Accessible.name: "Nhóm cấu hình bài"
        onActivated: page.category = currentIndex
    }
    Loader {
        id: content
        objectName: "labeditContent"
        Layout.fillWidth: true
        sourceComponent: [settings, parameters, artifacts, results, goals, quiz][page.category]
    }
    Component { id: settings; LabeditSettings { editor: page.editor } }
    Component { id: parameters; LabeditParameters { editor: page.editor } }
    Component { id: artifacts; LabeditArtifacts { editor: page.editor } }
    Component { id: results; LabeditResults { editor: page.editor } }
    Component { id: goals; LabeditGoals { editor: page.editor } }
    Component { id: quiz; LabeditQuiz { editor: page.editor } }
}
