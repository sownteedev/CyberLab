pragma Singleton

import QtQuick
import QtCore
import "../models/NodeDefaults.js" as Defaults

QtObject {
    id: preferences

    readonly property string username: Defaults.validUsername(stored.username) ? stored.username : "student"
    readonly property bool invalidStoredValue: !Defaults.validUsername(stored.username)
    property Settings storage: Settings {
        id: stored

        location: StandardPaths.writableLocation(StandardPaths.ConfigLocation) + "/cyberlab/lab-defaults.ini"
        property string username: "student"
    }

    function setUsername(value) {
        if (!Defaults.validUsername(value))
            return false;
        stored.username = value;
        stored.sync();
        return true;
    }
}
