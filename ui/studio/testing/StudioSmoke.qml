import QtQuick
import Quickshell
import ".." as Studio

Item {
    id: runner

    property bool active: false
    required property var api
    required property var appearanceLoader
    required property var capture
    required property var controller
    required property var editor
    property var draftSmokeDone: null
    property int screenshotStage: 0
    property int settingsStage: 0
    property int settingsWaits: 0
    property bool smokePublicationPending: false
    property string smokeSession: ""
    property bool smokeStarted: false
    required property var studioWindow
    property int terminalSettingsStage: 0
    property string terminalTestId: ""

    signal settingsRequested

    function checkSmoke(condition, message) {
        if (!condition) {
            console.error("CYBERLAB_STUDIO_SMOKE_FAIL: " + message);
            Qt.quit();
            return false;
        }
        return true;
    }
    function findSettingsItem(item, name) {
        if (item.objectName === name)
            return item;
        for (const child of item.children || []) {
            const found = findSettingsItem(child, name);
            if (found)
                return found;
        }
        return null;
    }
    function finishSmoke() {
        api.request(["stop", smokeSession], (session, error) => {
            if (!checkSmoke(!error && session.state === "STOPPED", "stop"))
                return;
            runner.runDraftSmoke(() => {
                runner.smokePublicationPending = true;
            });
        });
    }
    function runDraftSmoke(done) {
        draftSmokeDone = done;
        controller.page = 2;
        Qt.callLater(() => {
            const landing = findSettingsItem(capture, "draftLanding");
            const title = findSettingsItem(capture, "newDraftTitle");
            const identifier = findSettingsItem(capture, "newDraftId");
            const create = findSettingsItem(capture, "createDraftButton");
            if (!checkSmoke(landing && landing.visible && title && identifier && create, "Draft landing form is available"))
                return;
            title.text = "Bài tạo từ Studio";
            identifier.text = "studio-ui-check";
            if (!checkSmoke(create.enabled, "Draft landing enables valid creation"))
                return;
            const path = Quickshell.env("CYBERLAB_STUDIO_SCREENSHOT");
            if (path) {
                capture.grabToImage(result => {
                    if (checkSmoke(result.saveToFile(path + ".landing.png"), "Draft landing screenshot saved"))
                        create.clicked();
                });
            } else {
                create.clicked();
            }
        });
    }
    function populateDraftSmoke(done) {
        if (!checkSmoke(editor.document && editor.document.metadata.id === "studio-ui-check", "Draft landing creates through the shared API"))
            return;
        console.log("CYBERLAB_STUDIO_DRAFT_LANDING_PASS");
        editor.modify("networks", {
            id: "lan",
            subnet: "10.233.40.0/24"
        });
        editor.modify("nodes", {
            id: "client",
            image: "busybox:1.37.0",
            command: ["sleep", "3600"],
            networks: ["lan"],
            addresses: { lan: "10.233.40.2" },
            terminal_count: 2
        });
        editor.documentationText = "# Hướng dẫn\n\nMở terminal để thực hành.";
        editor.documentationDirty = true;
        editor.backend.request(["draft", "put-file", editor.draft.id, "-", "assets/client/message.txt", "--revision", String(editor.draft.revision)], (result, error) => {
            if (error)
                return;
            editor.adopt(result, true);
            editor.addMapping("client", "assets/client/message.txt", "message.txt");
            editor.save(() => editor.validate(() => editor.publish(done)));
        }, "studio-original\n");
    }
    Connections {
        target: runner.editor
        function onDraftChanged() {
            if (runner.active && runner.draftSmokeDone && runner.editor.draft) {
                const done = runner.draftSmokeDone;
                runner.draftSmokeDone = null;
                Qt.callLater(() => runner.populateDraftSmoke(done));
            }
        }
    }
    function runSmoke() {
        smokeStarted = true;
        if (!checkSmoke(Quickshell.appId === "cyberlab-studio", "Studio app ID matches its desktop entry"))
            return;
        const brand = findSettingsItem(studioWindow.header, "cyberlabBrand");
        if (!checkSmoke(brand && brand.status === Image.Ready, "CyberLab brand icon loads from bundled SVG"))
            return;
        const importPackage = findSettingsItem(capture, "importLabPackageButton");
        const exportPackage = findSettingsItem(capture, "exportLabPackageButton");
        if (!checkSmoke(importPackage && importPackage.iconName === "download" && exportPackage && exportPackage.iconName === "upload", "Import points into Studio; Export points out"))
            return;
        if (!checkSmoke(api.demo && controller.connected && controller.labs.length > 0, "isolated backend and library"))
            return;
        if (!verifyNotifications())
            return;
        let lab = controller.labs.find(entry => entry.id === "demo-workspace");
        if (!checkSmoke(!!lab, "workspace fixture exists"))
            return;
        controller.selectLab(lab);
        api.request(["start", lab.id, "--no-terminals"], (session, error) => {
            if (!checkSmoke(!error && session.state === "RUNNING", "start"))
                return;
            smokeSession = session.id;
            controller.selectSession(session);
            api.request(["docs", session.id, "--session", "--json"], (document, problem) => {
                if (!checkSmoke(!problem && document.content.length > 0, "session documentation"))
                    return;
                controller.manual = document.content;
                api.request(["reset", session.id], (reset, resetError) => {
                    if (!checkSmoke(!resetError && reset.id === session.id && reset.state === "RUNNING", "reset"))
                        return;
                    controller.selectedSession = reset;
                    screenshotTimer.start();
                });
            });
        });
    }
    function verifyNotifications() {
        const notifications = findSettingsItem(studioWindow.contentItem, "studioNotifications");
        if (!checkSmoke(!!notifications, "global notification overlay exists"))
            return false;
        if (!checkSmoke(Math.abs(notifications.x + notifications.width - notifications.parent.width + Studio.Theme.space16) < 1, "notifications align to the right edge"))
            return false;
        const focused = studioWindow.activeFocusItem;
        api.error = "Temporary notification regression.";
        api.notify("Temporary completion notice.", false);
        if (!checkSmoke(notifications.errorToast.shown && notifications.noticeToast.shown, "backend errors and notifications reach the local overlay in test mode"))
            return false;
        if (!checkSmoke(studioWindow.activeFocusItem === focused, "notifications do not steal editor focus"))
            return false;
        notifications.errorToast.dismiss(true);
        notifications.noticeToast.dismiss(true);
        if (!checkSmoke(api.error === "", "notification dismissal clears only the current backend error"))
            return false;
        console.log("CYBERLAB_STUDIO_NOTIFICATIONS_PASS");
        return true;
    }
    function verifySettings() {
        settingsRequested();
        settingsTimer.start();
    }
    function verifyTerminalSettings(dialog) {
        const preferences = dialog.terminals;
        if (!preferences.loaded || preferences.busy)
            return false;
        if (!checkSmoke(!preferences.error, "terminal inventory loads without daemon mutation"))
            return false;
        if (Quickshell.env("CYBERLAB_STUDIO_TERMINAL_SETTINGS_TEST") !== "1")
            return true;
        if (!checkSmoke(api.demo && Quickshell.env("XDG_CONFIG_HOME").startsWith("/tmp/cyberlab-terminal-"), "terminal settings use isolated configuration"))
            return false;
        dialog.showSection(1);
        const choice = findSettingsItem(dialog.contentItem, "terminalChoice");
        if (!choice)
            return false;
        if (!checkSmoke(choice.visible === (preferences.state.options.length > 1), "terminal selector is shown only for multiple choices"))
            return false;
        const expectedCount = Quickshell.env("CYBERLAB_STUDIO_TERMINAL_COUNT");
        if (expectedCount && !checkSmoke(preferences.state.options.length === Number(expectedCount), "terminal inventory matches isolated PATH"))
            return false;
        if (terminalSettingsStage === 0) {
            const expected = Quickshell.env("CYBERLAB_STUDIO_TERMINAL_EXPECTED");
            if (expected && !checkSmoke(preferences.state.preferred === expected, "terminal selection survives Studio restart"))
                return false;
            terminalTestId = preferences.state.options.length ? preferences.state.options[0].id : "auto";
            preferences.select(terminalTestId);
            terminalSettingsStage++;
            return false;
        }
        if (!checkSmoke(preferences.state.preferred === terminalTestId, "terminal selection is persisted"))
            return false;
        if (terminalSettingsStage === 1) {
            preferences.refresh();
            terminalSettingsStage++;
            return false;
        }
        if (terminalSettingsStage === 2 && Quickshell.env("CYBERLAB_STUDIO_SCREENSHOT")) {
            const path = Quickshell.env("CYBERLAB_STUDIO_SCREENSHOT") + ".terminal.png";
            terminalSettingsStage++;
            dialog.contentItem.grabToImage(result => {
                if (runner.checkSmoke(result.saveToFile(path), "terminal settings screenshot"))
                    runner.terminalSettingsStage++;
            });
            return false;
        }
        if (terminalSettingsStage === 3)
            return false;
        console.log("CYBERLAB_STUDIO_TERMINAL_SETTINGS_PASS");
        return true;
    }

    visible: false

    Timer {
        interval: 100
        repeat: true
        running: runner.active && runner.smokePublicationPending

        onTriggered: {
            if (api.busy || api.inFlight || api.pending.length > 0)
                return;
            runner.smokePublicationPending = false;
            if (!runner.checkSmoke(controller.labs.some(lab => lab.id === "studio-ui-check"), "published Lab appears without manual refresh"))
                return;
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
        interval: 500
        repeat: true
        running: runner.active

        onTriggered: if (!runner.smokeStarted && controller.connected && controller.labs.length && !api.busy && !api.inFlight)
            runner.runSmoke()
    }
    Timer {
        id: screenshotTimer

        interval: 600

        onTriggered: {
            let path = Quickshell.env("CYBERLAB_STUDIO_SCREENSHOT");
            if (path) {
                capture.grabToImage(result => {
                    if (!runner.checkSmoke(result.saveToFile(path), "screenshot saved"))
                        return;
                    runner.finishSmoke();
                });
            } else
                runner.finishSmoke();
        }
    }
    Timer {
        id: extraScreenshotTimer

        interval: 700

        onTriggered: {
            let path = Quickshell.env("CYBERLAB_STUDIO_SCREENSHOT") + (runner.screenshotStage === 1 ? ".library.png" : ".editor.png");
            capture.grabToImage(result => {
                if (!runner.checkSmoke(result.saveToFile(path), "additional screen saved"))
                    return;
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
            if (!runner.checkSmoke(++runner.settingsWaits < 75, "Settings verification timeout"))
                return;
            if (runner.settingsStage === 0 || runner.settingsStage === 2) {
                if (!runner.checkSmoke(runner.appearanceLoader.status === Loader.Ready && runner.appearanceLoader.item.opened, "Settings loader opens from AppBar"))
                    return;
                if (!runner.verifyTerminalSettings(runner.appearanceLoader.item))
                    return;
                runner.appearanceLoader.item.close();
            } else if (runner.settingsStage === 1) {
                if (!runner.checkSmoke(!runner.appearanceLoader.active, "Settings unloads after closing"))
                    return;
                runner.settingsRequested();
            } else {
                if (!runner.checkSmoke(!runner.appearanceLoader.active, "Settings can reopen and unload"))
                    return;
                console.log("CYBERLAB_STUDIO_SETTINGS_PASS");
                settingsTimer.stop();
                windowChecks.start();
            }
            runner.settingsStage++;
        }
    }
    Studio.StudioWindowSmoke {
        id: windowChecks

        findItem: runner.findSettingsItem
        screenshotPath: Quickshell.env("CYBERLAB_STUDIO_SCREENSHOT") ? Quickshell.env("CYBERLAB_STUDIO_SCREENSHOT") + ".window-controls.png" : ""
        studioWindow: runner.studioWindow

        onFailed: message => runner.checkSmoke(false, message)
        onFinished: {
            console.log("CYBERLAB_STUDIO_SMOKE_PASS");
            Qt.quit();
        }
    }
}
