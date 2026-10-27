import QtQuick
import QtCore
import ".."
import ".." as Studio

QtObject {
    id: preferences
    property bool ready: false
    readonly property url location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/cyberlab/studio.ini"
    property Settings storage: Settings {
        id: stored
        location: preferences.location
        property string themeMode: "system"
        property bool reducedMotion: false
        property int settingsVersion: 1
    }
    Component.onCompleted: {
        if (stored.settingsVersion === 1) {
            Studio.Theme.themeMode = ["system", "light", "dark"].includes(stored.themeMode) ? stored.themeMode : "system";
            Studio.Theme.reducedMotion = stored.reducedMotion;
            ready = true;
        }
    }
    property Connections observer: Connections {
        target: Studio.Theme
        function onThemeModeChanged() {
            if (!preferences.ready) return;
            stored.themeMode = Studio.Theme.themeMode;
            stored.sync();
        }
        function onReducedMotionChanged() {
            if (!preferences.ready) return;
            stored.reducedMotion = Studio.Theme.reducedMotion;
            stored.sync();
        }
    }
}
