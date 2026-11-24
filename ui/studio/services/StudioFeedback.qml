pragma Singleton

import QtQuick
import "../models/Messages.js" as Messages

QtObject {
    id: feedback
    property var pending: []
    signal errorRequested(string message)

    function report(message) {
        const value = Messages.text(message);
        const additions = value.split("\n").filter((entry, index, entries) => entry.trim() && entries.indexOf(entry) === index && !pending.includes(entry));
        if (!additions.length) return;
        pending = pending.concat(additions);
        flush.restart();
    }

    readonly property Timer flush: Timer {
        interval: 0
        onTriggered: {
            const messages = feedback.pending;
            feedback.pending = [];
            if (messages.length) feedback.errorRequested(messages.join("\n"));
        }
    }
}
