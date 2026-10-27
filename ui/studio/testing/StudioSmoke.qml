import QtQuick
import Quickshell

Item {
    id: runner
    required property var controller
    required property var api
    required property var editor
    required property var capture
    required property var appearanceLoader
    signal settingsRequested()
    property bool active: false
    visible: false
    property bool smokeStarted: false
    property bool smokePublicationPending: false
    property string smokeSession: ""
    property int screenshotStage: 0
    property int settingsStage: 0
    function verifySettings() {
        settingsRequested();
        settingsTimer.start();
    }
    function checkSmoke(condition, message) {
        if (!condition) {
            console.error("CYBERLAB_STUDIO_SMOKE_FAIL: " + message);
            Qt.quit();
            return false;
        }
        return true;
    }
    function runSmoke() {
        smokeStarted = true;
        if (!checkSmoke(api.demo && controller.connected && controller.labs.length > 0, "isolated backend and library")) return;
        let lab = controller.labs.find(entry => entry.id === "demo-workspace");
        if (!checkSmoke(!!lab, "workspace fixture exists")) return;
        controller.selectLab(lab);
        api.request(["start", lab.id, "--no-terminals"], (session, error) => {
            if (!checkSmoke(!error && session.state === "RUNNING", "start")) return;
            smokeSession = session.id;
            controller.selectSession(session);
            api.request(["docs", session.id, "--session", "--json"], (document, problem) => {
                if (!checkSmoke(!problem && document.content.length > 0, "session documentation")) return;
                controller.manual = document.content;
                api.request(["reset", session.id], (reset, resetError) => {
                    if (!checkSmoke(!resetError && reset.id === session.id && reset.state === "RUNNING", "reset")) return;
                    controller.selectedSession = reset;
                    screenshotTimer.start();
                });
            });
        });
    }
    function runDraftSmoke(done) {
        editor.create("studio-ui-check", "Bài tạo từ Studio", () => {
            editor.modify("networks", {id: "lan", subnet: "10.233.40.0/24"});
            editor.modify("nodes", {id: "client", image: "busybox:1.37.0", command: ["sleep", "3600"], networks: ["lan"], addresses: {lan: "10.233.40.2"}, terminal_count: 2});
            editor.documentationText = "# Hướng dẫn\n\nMở terminal để thực hành.";
            editor.documentationDirty = true;
            editor.backend.request(["draft", "put-file", editor.draft.id, "-", "assets/client/message.txt", "--revision", String(editor.draft.revision)], (result, error) => {
                if (error) return;
                editor.adopt(result, true);
                editor.addMapping("client", "assets/client/message.txt", "message.txt");
                editor.save(() => editor.validate(() => editor.publish(done)));
            }, "studio-original\n");
        });
    }
    function finishSmoke() {
        api.request(["stop", smokeSession], (session, error) => {
            if (!checkSmoke(!error && session.state === "STOPPED", "stop")) return;
            runner.runDraftSmoke(() => {
                runner.smokePublicationPending = true;
            });
        });
    }

    Timer {
        interval: 100; running: runner.active && runner.smokePublicationPending; repeat: true
        onTriggered: {
            if (api.busy || api.inFlight || api.pending.length > 0) return;
            runner.smokePublicationPending = false;
            if (!runner.checkSmoke(controller.labs.some(lab => lab.id === "studio-ui-check"), "published Lab appears without manual refresh")) return;
            console.log("CYBERLAB_STUDIO_LIBRARY_REFRESH_PASS");
            if (Quickshell.env("CYBERLAB_STUDIO_SCREENSHOT")) {
                controller.page = 0;
                controller.selectLab(controller.selectedLab);
                runner.screenshotStage = 1;
                extraScreenshotTimer.start();
            } else {
                runner.verifySettings();
            }
        }
    }
    Timer {
        interval: 500; running: runner.active; repeat: true
        onTriggered: if (!runner.smokeStarted && controller.connected && controller.labs.length && !api.busy && !api.inFlight) runner.runSmoke()
    }
    Timer {
        id: screenshotTimer
        interval: 600
        onTriggered: {
            let path = Quickshell.env("CYBERLAB_STUDIO_SCREENSHOT");
            if (path) {
                capture.grabToImage(result => {
                    if (!runner.checkSmoke(result.saveToFile(path), "screenshot saved")) return;
                    runner.finishSmoke();
                });
            } else runner.finishSmoke();
        }
    }
    Timer {
        id: extraScreenshotTimer
        interval: 700
        onTriggered: {
            let path = Quickshell.env("CYBERLAB_STUDIO_SCREENSHOT") + (runner.screenshotStage === 1 ? ".library.png" : ".editor.png");
            capture.grabToImage(result => {
                if (!runner.checkSmoke(result.saveToFile(path), "additional screen saved")) return;
                if (runner.screenshotStage === 1) {
                    runner.screenshotStage = 2;
                    controller.page = 2;
                    editor.showMachines();
                    extraScreenshotTimer.start();
                } else {
                    runner.verifySettings();
                }
            });
        }
    }
    Timer {
        id: settingsTimer
        interval: 400
        repeat: true
        onTriggered: {
            if (runner.settingsStage === 0 || runner.settingsStage === 2) {
                if (!runner.checkSmoke(runner.appearanceLoader.status === Loader.Ready && runner.appearanceLoader.item.opened, "Settings loader opens from AppBar")) return;
                runner.appearanceLoader.item.close();
            } else if (runner.settingsStage === 1) {
                if (!runner.checkSmoke(!runner.appearanceLoader.active, "Settings unloads after closing")) return;
                runner.settingsRequested();
            } else {
                if (!runner.checkSmoke(!runner.appearanceLoader.active, "Settings can reopen and unload")) return;
                console.log("CYBERLAB_STUDIO_SETTINGS_PASS");
                console.log("CYBERLAB_STUDIO_SMOKE_PASS");
                Qt.quit();
            }
            runner.settingsStage++;
        }
    }
}
