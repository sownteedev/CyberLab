import QtQuick
import QtCore
import ".."
import ".." as Studio

QtObject {
    id: preferences

    readonly property url location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/cyberlab/studio.ini"
    property Connections observer: Connections {
        function onThemeModeChanged() {
            if (!preferences.ready)
                return;
            stored.themeMode = Studio.Theme.themeMode;
            stored.sync();
        }
        function onZoomPercentChanged() {
            if (!preferences.ready)
                return;
            stored.zoomPercent = Studio.Theme.zoomPercent;
            stored.sync();
        }

        target: Studio.Theme
    }
    property bool ready: false
    property Settings storage: Settings {
        id: stored

        property int settingsVersion: 1
        property string themeMode: "system"
        property int zoomPercent: 100

        location: preferences.location
    }

    Component.onCompleted: {
        if (stored.settingsVersion === 1) {
            Studio.Theme.themeMode = ["system", "light", "dark"].includes(stored.themeMode) ? stored.themeMode : "system";
            Studio.Theme.setZoomPercent(stored.zoomPercent >= Studio.Theme.minimumZoom && stored.zoomPercent <= Studio.Theme.maximumZoom ? stored.zoomPercent : 100);
            ready = true;
        }
    }
}
