//@ pragma UseQApplication
//@ pragma AppId cyberlab-studio
//@ pragma Env QT_QPA_PLATFORMTHEME=generic
//@ pragma Env QS_NO_RELOAD_POPUP=1
//@ pragma DefaultEnv QSG_RENDER_LOOP=threaded
//@ pragma DefaultEnv QT_QUICK_CONTROLS_STYLE=Basic
//@ pragma DefaultEnv QT_QUICK_FLICKABLE_WHEEL_DECELERATION=10000
//@ pragma DefaultEnv QS_DROP_EXPENSIVE_FONTS=1

import QtQuick
import Quickshell

ShellRoot {
    id: root

    readonly property bool smoke: Quickshell.env("CYBERLAB_STUDIO_SMOKE") === "1"

    Backend {
        id: serviceApi
    }
    StudioState {
        id: studioState

        api: serviceApi
        smoke: root.smoke
    }
    StudioWindow {
        id: mainWindow
        onCloseAccepted: serviceApi.clearEditing(() => Qt.quit())

        api: serviceApi
        controller: studioState
        smoke: root.smoke
    }
    Loader {
        active: !root.smoke

        sourceComponent: Component {
            AppearanceStore {
            }
        }
    }
    StudioSmoke {
        active: root.smoke
        api: serviceApi
        appearanceLoader: mainWindow.appearanceLoader
        capture: mainWindow.capture
        controller: studioState
        editor: mainWindow.editor
        studioWindow: mainWindow

        onSettingsRequested: mainWindow.openSettings()
    }
    Timer {
        interval: 5000
        repeat: true
        running: !root.smoke

        onTriggered: if (!mainWindow.confirmationOpened)
            studioState.poll()
    }
}
