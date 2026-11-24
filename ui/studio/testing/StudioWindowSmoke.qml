import QtQuick
import ".." as Studio

Item {
    id: checks

    property var closeButton: null
    required property var findItem
    property var maximizeButton: null
    property size restoredSize: Qt.size(0, 0)
    property string savedDocumentation: ""
    property string screenshotPath: ""
    property int stage: 0
    required property var studioWindow
    property int waits: 0

    signal failed(string message)
    signal finished

    function verifyPageSpacing() {
        const navigation = findItem(studioWindow.header, "studioNavigation");
        const controls = findItem(studioWindow.header, "windowControls");
        const page = findItem(studioWindow.contentItem, "studioPageLayout");
        if (!verify(navigation && controls && page, "header and page layout exist"))
            return false;
        const top = controls.mapToItem(null, 0, 0).y - studioWindow.header.mapToItem(null, 0, 0).y;
        const bottom = page.mapToItem(null, 0, 0).y - navigation.mapToItem(null, 0, navigation.height).y;
        return verify(Math.abs(top - bottom) < 1 && Math.abs(top - Studio.Theme.appBarVerticalInset * Studio.Theme.zoomFactor) < 1, "header-to-page spacing matches the top inset at current zoom");
    }
    function cancelClose() {
        const cancel = studioWindow.activeFocusItem;
        if (!verify(studioWindow.visible && cancel && cancel.objectName === "confirmCancelButton", "close confirmation focuses the safe cancel action"))
            return false;
        cancel.clicked();
        return true;
    }
    function start() {
        if (!verify(studioWindow.smoke && studioWindow.api.demo, "window checks require the isolated smoke runtime"))
            return;
        maximizeButton = findItem(studioWindow.header, "maximizeWindowButton");
        closeButton = findItem(studioWindow.header, "closeWindowButton");
        if (!verify(maximizeButton && closeButton, "window controls are present"))
            return;
        if (!verify(maximizeButton.width >= 48 && maximizeButton.height >= 48 && closeButton.width >= 48 && closeButton.height >= 48, "window controls retain 48px targets"))
            return;
        if (!verify(maximizeButton.enabled && closeButton.enabled && closeButton.Accessible.name.length > 0, "window controls remain accessible"))
            return;
        if (!verifyPageSpacing())
            return;
        restoredSize = Qt.size(studioWindow.width, studioWindow.height);
        savedDocumentation = studioWindow.editor.documentationText;
        stage = -7;
        if (screenshotPath) {
            studioWindow.header.grabToImage(result => {
                if (checks.verify(result.saveToFile(checks.screenshotPath), "window controls screenshot"))
                    steps.start();
            });
        } else
            steps.start();
    }
    function verify(condition, message) {
        if (!condition) {
            steps.stop();
            failed(message);
        }
        return condition;
    }

    visible: false

    Timer {
        id: steps

        interval: 200
        repeat: true

        onTriggered: {
            const target = checks.studioWindow;
            if (!checks.verify(++checks.waits < 75, "window controls verification timeout"))
                return;
            if (checks.stage === -7) {
                Studio.Theme.setZoomPercent(70);
                checks.stage = -6;
            } else if (checks.stage === -6 || checks.stage === -5) {
                if (!checks.verifyPageSpacing())
                    return;
                const viewport = checks.findItem(target.contentItem, "studioViewport");
                const factor = Studio.Theme.zoomFactor;
                if (!checks.verify(viewport && Math.abs(viewport.width * factor - target.width) < 1, "full Studio content follows zoom"))
                    return;
                if (!checks.verify(Math.abs(viewport.popupOverlay.width * factor - target.width) < 1 && Math.abs(viewport.popupOverlay.height * factor - target.height) < 1, "Studio popup overlay covers window at zoom"))
                    return;
                const buttonRect = checks.closeButton.mapToItem(null, 0, 0, checks.closeButton.width, checks.closeButton.height);
                if (!checks.verify(Math.abs(buttonRect.width - 48 * factor) < 1 && buttonRect.x + buttonRect.width <= target.width, "native header controls share zoom"))
                    return;
                if (checks.stage === -6) {
                    Studio.Theme.setZoomPercent(150);
                    checks.stage = -5;
                } else {
                    Studio.Theme.setZoomPercent(100);
                    checks.stage = -4;
                    console.log("CYBERLAB_STUDIO_ZOOM_PASS");
                }
            } else if (checks.stage === -4) {
                if (target.api.busy)
                    return;
                target.showPage(2);
                checks.stage = -3;
            } else if (checks.stage === -3) {
                if (target.api.busy)
                    return;
                const exportDraft = checks.findItem(target.contentItem, "draftEditActions").exportAction;
                if (!checks.verify(exportDraft && exportDraft.iconName === "upload", "Draft export uses the outward arrow"))
                    return;
                target.editor.documentationText = checks.savedDocumentation + "\nUnsaved navigation check.";
                target.editor.documentationDirty = true;
                checks.findItem(target.header, "navigationItem-0").clicked();
                checks.stage = -2;
            } else if (checks.stage === -2) {
                if (!target.confirmationOpened)
                    return;
                const navigation = checks.findItem(target.header, "studioNavigation");
                if (!checks.verify(target.controller.page === 2 && navigation.currentIndex === 2 && target.editor.dirty, "navigation waits for dirty-draft confirmation without selecting the destination"))
                    return;
                if (checks.cancelClose())
                    checks.stage = -1;
            } else if (checks.stage === -1) {
                if (target.confirmationOpened)
                    return;
                if (!checks.verify(target.controller.page === 2 && target.editor.documentationText === checks.savedDocumentation + "\nUnsaved navigation check.", "canceling navigation preserves editor text"))
                    return;
                target.editor.documentationText = checks.savedDocumentation;
                target.editor.documentationDirty = false;
                checks.findItem(target.header, "navigationItem-0").clicked();
                if (!checks.verify(target.controller.page === 0, "accepted navigation uses the existing window route"))
                    return;
                console.log("CYBERLAB_STUDIO_NAVIGATION_PASS");
                checks.stage = 0;
            } else if (checks.stage === 0) {
                checks.maximizeButton.clicked();
                checks.stage = 1;
            } else if (checks.stage === 1) {
                if (target.visibility !== Window.Maximized)
                    return;
                if (!checks.verify(checks.maximizeButton.iconName === "filter_none" && checks.maximizeButton.description === "Khôi phục cửa sổ", "maximized window exposes Restore"))
                    return;
                checks.maximizeButton.clicked();
                checks.stage = 2;
            } else if (checks.stage === 2) {
                if (target.visibility !== Window.Windowed)
                    return;
                if (!checks.verify(target.width === checks.restoredSize.width && target.height === checks.restoredSize.height && checks.maximizeButton.iconName === "crop_square", "Restore recovers the original window size"))
                    return;
                target.editor.documentationText = checks.savedDocumentation + "\nUnsaved window smoke edit.";
                target.editor.documentationDirty = true;
                checks.closeButton.clicked();
                checks.stage = 3;
            } else if (checks.stage === 3) {
                if (!target.confirmationOpened)
                    return;
                if (checks.cancelClose())
                    checks.stage = 4;
            } else if (checks.stage === 4) {
                if (target.confirmationOpened)
                    return;
                if (!checks.verify(target.visible && target.editor.dirty && target.editor.documentationText === checks.savedDocumentation + "\nUnsaved window smoke edit.", "canceling Close preserves the unsaved draft"))
                    return;
                target.editor.documentationText = checks.savedDocumentation;
                target.editor.documentationDirty = false;
                target.api.request(["draft", "list"], () => {});
                if (!checks.verify(target.api.busy && checks.closeButton.enabled, "Close stays available while the backend is busy"))
                    return;
                checks.closeButton.clicked();
                checks.stage = 5;
            } else if (checks.stage === 5) {
                if (!target.confirmationOpened)
                    return;
                if (checks.cancelClose())
                    checks.stage = 6;
            } else if (checks.stage === 6) {
                if (target.confirmationOpened || target.api.busy)
                    return;
                checks.stage = 7;
                checks.closeButton.clicked();
            }
        }
    }
    Connections {
        function onVisibleChanged() {
            if (checks.stage === 7 && !checks.studioWindow.visible) {
                steps.stop();
                checks.stage = 8;
                console.log("CYBERLAB_STUDIO_WINDOW_CONTROLS_PASS");
                checks.finished();
            }
        }

        target: checks.studioWindow
    }
}
