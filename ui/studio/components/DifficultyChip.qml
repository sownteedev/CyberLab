import QtQuick
import ".." as Studio

Studio.StatusBadge {
    property string difficulty: ""

    text: difficulty === "easy" ? qsTr("Dễ") : difficulty === "medium" ? qsTr("Trung bình")
        : difficulty === "hard" ? qsTr("Khó") : qsTr("Chưa phân loại")
    description: qsTr("Độ khó: %1").arg(text)
    iconName: "science"
    textColor: difficulty === "easy" ? Studio.Theme.textOnSuccessContainer
        : difficulty === "medium" ? Studio.Theme.textOnWarningContainer
        : difficulty === "hard" ? Studio.Theme.textOnErrorContainer : Studio.Theme.textOnSurfaceVariant
    bgColor: difficulty === "easy" ? Studio.Theme.successContainer
        : difficulty === "medium" ? Studio.Theme.warningContainer
        : difficulty === "hard" ? Studio.Theme.errorContainer : Studio.Theme.surfaceContainerHigh
    dotColor: textColor
}
