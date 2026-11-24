import QtQuick
import ".." as Studio
import "../models/Messages.js" as Messages

Item {
    id: errorView

    property bool dismissible: false
    property string message: ""
    property bool notifyError: true
    readonly property string displayMessage: Messages.text(message)

    signal dismissed

    implicitHeight: 0
    visible: false
    Accessible.ignored: true

    readonly property Studio.ErrorNotifier notifier: Studio.ErrorNotifier {
        parent: null
        message: errorView.message
        active: errorView.notifyError && !!errorView.parent && errorView.parent.visible
    }
}
