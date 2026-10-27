//@ pragma UseQApplication
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

    Backend { id: serviceApi }
    StudioState { id: studioState; api: serviceApi; smoke: root.smoke }
    StudioWindow { id: mainWindow; api: serviceApi; controller: studioState; smoke: root.smoke }
    Loader { active: !root.smoke; sourceComponent: Component { AppearanceStore {} } }
    StudioSmoke {
        active: root.smoke
        controller: studioState
        api: serviceApi
        editor: mainWindow.editor
        capture: mainWindow.capture
        appearanceLoader: mainWindow.appearanceLoader
        onSettingsRequested: mainWindow.openSettings()
    }
    Timer {
        interval: 5000
        running: !root.smoke
        repeat: true
        onTriggered: if (!mainWindow.confirmationOpened) studioState.poll()
    }
}
