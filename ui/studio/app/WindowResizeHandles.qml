import QtQuick

Item {
    id: handles

    readonly property int edgeSize: 6
    readonly property int cornerSize: 12
    signal resizeRequested(int edges)

    Repeater {
        model: [Qt.LeftEdge, Qt.RightEdge, Qt.TopEdge, Qt.BottomEdge,
            Qt.TopEdge | Qt.LeftEdge, Qt.TopEdge | Qt.RightEdge,
            Qt.BottomEdge | Qt.LeftEdge, Qt.BottomEdge | Qt.RightEdge]

        MouseArea {
            required property int modelData
            readonly property bool atLeft: (modelData & Qt.LeftEdge) !== 0
            readonly property bool atRight: (modelData & Qt.RightEdge) !== 0
            readonly property bool atTop: (modelData & Qt.TopEdge) !== 0
            readonly property bool atBottom: (modelData & Qt.BottomEdge) !== 0
            readonly property bool corner: (atLeft || atRight) && (atTop || atBottom)

            x: atLeft ? 0 : atRight ? handles.width - width : handles.cornerSize
            y: atTop ? 0 : atBottom ? handles.height - height : handles.cornerSize
            width: corner ? handles.cornerSize : atLeft || atRight ? handles.edgeSize : Math.max(0, handles.width - 2 * handles.cornerSize)
            height: corner ? handles.cornerSize : atTop || atBottom ? handles.edgeSize : Math.max(0, handles.height - 2 * handles.cornerSize)
            acceptedButtons: Qt.LeftButton
            hoverEnabled: true
            cursorShape: corner ? (atLeft === atTop ? Qt.SizeFDiagCursor : Qt.SizeBDiagCursor) : atLeft || atRight ? Qt.SizeHorCursor : Qt.SizeVerCursor
            onPressed: handles.resizeRequested(modelData)
        }
    }
}
