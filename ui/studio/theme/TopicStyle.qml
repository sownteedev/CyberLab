pragma Singleton

import QtQuick
import ".." as Studio

QtObject {
    readonly property var styles: ({
        "linux": ["terminal", "#ffd28a", "#493416", "#744700", "#ffebc8"],
        "scripting": ["topic-code", "#b5c8ff", "#293958", "#354e8c", "#e2eaff"],
        "networking": ["lan", "#7cdded", "#153e49", "#006377", "#cff3fa"],
        "network-services": ["topic-server", "#84e0c4", "#153f36", "#006650", "#cef5e8"],
        "network-security": ["topic-shield", "#ffb6a2", "#4e2c24", "#953c27", "#ffe2d9"],
        "system-security": ["topic-lock", "#c6baff", "#383052", "#5c458d", "#eee5ff"],
        "web-security": ["topic-web", "#ffb1cb", "#4d293c", "#943957", "#ffe1eb"],
        "databases": ["topic-database", "#9ccaff", "#243c56", "#205c91", "#dcecff"],
        "cryptography": ["topic-key", "#e2d785", "#413d1e", "#6e6000", "#f6efc2"],
        "software-security": ["topic-bug", "#ffb5b5", "#4e2a31", "#963d49", "#ffe2e5"],
        "forensics": ["search", "#c4df97", "#303f22", "#496727", "#e5f1d2"],
        "containers": ["inventory_2", "#a8c0ff", "#2c3555", "#3f5290", "#e2e7ff"]
    })

    function appearance(tag) {
        const entry = styles[tag];
        return entry ? {icon: entry[0], foreground: Studio.Theme.dark ? entry[1] : entry[3],
            background: Studio.Theme.dark ? entry[2] : entry[4]}
            : {icon: "bookmark", foreground: Studio.Theme.textOnSurfaceVariant,
                background: Studio.Theme.surfaceContainerHigh};
    }
}
