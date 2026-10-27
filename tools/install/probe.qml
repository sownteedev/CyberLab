import QtCore
import QtQuick
import QtQuick.Controls
import QtQuick.Controls.Basic as Basic
import QtQuick.Controls.Material
import QtQuick.Controls.impl
import QtQuick.Dialogs
import QtQuick.Layouts
import Quickshell
import Quickshell.Io

ShellRoot {
    Item {
        Basic.Button { text: "Native runtime check" }
        Button { text: "Material runtime check" }
        FileDialog { }
        RowLayout { }
        Image {
            id: svgProbe
            source: "data:image/svg+xml," + encodeURIComponent("<svg xmlns='http://www.w3.org/2000/svg' width='24' height='24'><rect width='24' height='24'/></svg>")
            sourceSize.width: 24
            sourceSize.height: 24
        }
    }

    Timer {
        interval: 100
        running: true
        repeat: false
        onTriggered: {
            if (svgProbe.status !== Image.Ready) {
                console.warn("SVG decoding failed; install the native Qt SVG image plugin");
                Qt.quit();
                return;
            }
            console.warn("CYBERLAB_NATIVE_QML_OK");
            Qt.quit();
        }
    }
}
