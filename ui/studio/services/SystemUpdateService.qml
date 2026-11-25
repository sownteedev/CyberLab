import QtQuick
import QtCore
import Quickshell
import Quickshell.Io
import ".." as Studio

Item {
    id: updater
    property bool checking: false
    property bool handingOff: false
    property bool available: false
    property string installedCommit: ""
    property string latestCommit: ""
    property string problem: ""
    property bool checked: false
    property bool manualCheck: false
    property bool automatic: true
    property var prefix: [Quickshell.env("CYBERLAB_STUDIO_PYTHON") || "/usr/bin/python3", "-m", "cyberlab_cli.main"]
    signal newVersion()
    signal errorOccurred(string message)
    signal handoffReady()

    Settings {
        id: stored
        location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/cyberlab/updates.ini"
        property string lastNotified: ""
    }
    function validCommit(value) { return typeof value === "string" && /^[0-9a-f]{40}$/.test(value); }
    function acceptCheck(text, code) {
        checking = false;
        let result;
        try { result = JSON.parse(text); } catch (_) { result = null; }
        if (code !== 0 || !result || result.event !== "checked" || !validCommit(result.latest)
                || (result.installed !== null && !validCommit(result.installed)) || typeof result.available !== "boolean") {
            problem = result && result.message ? result.message : qsTr("Chưa kiểm tra được cập nhật. Kiểm tra kết nối rồi thử lại.");
            if (manualCheck) errorOccurred(problem);
            return;
        }
        checked = true;
        problem = "";
        installedCommit = result.installed || "";
        latestCommit = result.latest;
        available = validCommit(result.installed) && result.installed !== result.latest && result.available;
        if (available && stored.lastNotified !== latestCommit) {
            stored.lastNotified = latestCommit;
            stored.sync();
            newVersion();
        }
    }
    function check(manual) {
        if (checking || handingOff || checker.running || launcher.running) return;
        manualCheck = !!manual;
        problem = "";
        checking = true;
        checker.running = true;
        checkTimeout.restart();
    }
    function begin() {
        if (!available || checking || handingOff || launcher.running || !validCommit(latestCommit)) return;
        handingOff = true;
        launcher.command = prefix.concat(["update", "--window", "--commit", latestCommit,
            "--wait-pid", String(Quickshell.processId), "--theme", Studio.Theme.themeMode]);
        launcher.running = true;
        launchTimeout.restart();
    }
    Timer { interval: 7000; running: updater.automatic; onTriggered: updater.check(false) }
    Timer {
        id: checkTimeout
        interval: 60000
        onTriggered: { checker.signal(15); updater.acceptCheck("", 1); }
    }
    Timer {
        id: launchTimeout
        interval: 30000
        onTriggered: {
            launcher.signal(15);
            updater.handingOff = false;
            updater.errorOccurred(qsTr("Cửa sổ cập nhật chưa sẵn sàng. Studio vẫn mở; hãy thử lại."));
        }
    }
    Process {
        id: checker
        command: updater.prefix.concat(["update", "--check", "--json"])
        stdout: StdioCollector { id: checkOutput }
        stderr: StdioCollector {}
        onExited: (code, status) => Qt.callLater(() => {
            checkTimeout.stop();
            if (updater.checking) updater.acceptCheck(checkOutput.text, status === 0 ? code : 1);
        })
    }
    Process {
        id: launcher
        stdout: StdioCollector { id: launchOutput }
        stderr: StdioCollector {}
        onExited: (code, status) => Qt.callLater(() => {
            launchTimeout.stop();
            if (!updater.handingOff) return;
            updater.handingOff = false;
            let result;
            try { result = JSON.parse(launchOutput.text); } catch (_) { result = null; }
            if (code === 0 && status === 0 && result && result.ready === true) updater.handoffReady();
            else updater.errorOccurred(result && result.error ? result.error : qsTr("Không mở được cửa sổ cập nhật. Studio vẫn giữ nguyên."));
        })
    }
}
