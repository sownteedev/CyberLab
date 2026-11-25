//@ pragma UseQApplication
//@ pragma AppId cyberlab-updater
//@ pragma Env QT_QUICK_CONTROLS_STYLE=Basic
import QtQuick
import QtQuick.Controls.Basic
import Quickshell
import Quickshell.Io
import "." as Studio

ShellRoot {
    id: root
    readonly property string stage: Quickshell.env("CYBERLAB_UPDATE_STAGE")
    function command(action) { return ["/usr/bin/python3", "-I", "-B", stage + "/window.py", action, stage]; }
    ApplicationWindow {
        id: window
        visible: true
        title: qsTr("Cập nhật CyberLab")
        width: 580; height: 570
        minimumWidth: 360; minimumHeight: 480
        color: Studio.Theme.surface
        palette: Studio.Theme.controlPalette
        font.family: Studio.Theme.fontFamily
        onClosing: event => { if (view.running) event.accepted = false; else Qt.quit(); }
        ScrollView {
            id: updateScroll
            anchors.fill: parent
            anchors.margins: 28
            clip: true
            contentWidth: availableWidth
            Studio.UpdateProgress {
                id: view
                width: updateScroll.availableWidth
                onRestartRequested: restart.running = true
                onCloseRequested: Qt.quit()
            }
        }
        Component.onCompleted: {
            Studio.Theme.themeMode = root.stage ? Quickshell.env("CYBERLAB_UPDATE_THEME") : "system";
            ready.running = true;
        }
    }
    Process {
        id: ready
        command: root.command("ready")
        onExited: (code, status) => {
            if (code === 0 && status === 0) worker.running = true;
            else { view.problem = qsTr("Không khởi tạo được cửa sổ cập nhật."); view.finish(1); }
        }
    }
    Process {
        id: worker
        command: root.command("run")
        stdout: SplitParser {
            onRead: line => {
                try { view.acceptEvent(JSON.parse(line)); } catch (_) {}
            }
        }
        stderr: SplitParser { onRead: line => view.details = (view.details + line + "\n").slice(-16000) }
        onExited: (code, status) => Qt.callLater(() => view.finish(status === 0 ? code : 1))
    }
    Process {
        id: restart
        command: root.command("restart")
        onExited: (code, status) => {
            if (code === 0 && status === 0) Qt.quit();
            else view.problem = qsTr("Không mở lại được CyberLab. Hãy mở từ menu ứng dụng.");
        }
    }
}
