pragma Singleton

import QtQuick

QtObject {
    property string themeMode: "system"
    property int systemColorScheme: Qt.styleHints.colorScheme
    readonly property bool effectiveDark: themeMode === "dark" || (themeMode !== "light" && systemColorScheme !== Qt.Light)
    readonly property bool dark: effectiveDark
    property bool reducedMotion: false
    readonly property color seed: "#1b62a5"
    readonly property color transparent: "transparent"
    readonly property color scrim: "#660c1017"
    readonly property FontLoader interRegular: FontLoader { source: "../assets/fonts/Inter-Regular.ttf" }
    readonly property FontLoader interMedium: FontLoader { source: "../assets/fonts/Inter-Medium.ttf" }
    readonly property FontLoader interSemibold: FontLoader { source: "../assets/fonts/Inter-SemiBold.ttf" }
    readonly property FontLoader interBold: FontLoader { source: "../assets/fonts/Inter-Bold.ttf" }
    readonly property FontLoader interItalic: FontLoader { source: "../assets/fonts/Inter-Italic.ttf" }
    readonly property FontLoader interBoldItalic: FontLoader { source: "../assets/fonts/Inter-BoldItalic.ttf" }
    readonly property string fontFamily: interRegular.status === FontLoader.Ready ? interRegular.name : "sans-serif"
    readonly property string monoFamily: Qt.fontFamilies().includes("Liga SFMono Nerd Font") ? "Liga SFMono Nerd Font" : "monospace"
    readonly property int enterDuration: reducedMotion ? 0 : 200
    readonly property int exitDuration: reducedMotion ? 0 : 120
    readonly property int stateDuration: reducedMotion ? 0 : 120
    readonly property int controlHeight: 48
    readonly property int railWidth: 80
    readonly property int appBarHeight: 64
    readonly property int appBarInset: 16
    readonly property int appBarVerticalInset: 8
    readonly property int contentInset: 12
    readonly property int contentGap: 12
    readonly property int borderWidth: 1
    readonly property int focusWidth: 2
    readonly property int displaySmall: 30
    readonly property int headlineMedium: 24
    readonly property int iconSize: 24
    readonly property int iconSmall: 20
    readonly property int iconLarge: 28
    readonly property int rowHeight: 56
    readonly property int badgeHeight: 28
    readonly property int libraryWidth: 304
    readonly property int sectionWidth: 152
    readonly property int compactBreakpoint: 880
    readonly property int editorRailBreakpoint: 960
    readonly property int settingsWidth: 720
    readonly property int settingsHeight: 560
    readonly property int dotSize: 6

    readonly property color primary: dark ? "#82b4ff" : "#1b62a5"
    readonly property color textOnPrimary: dark ? "#002d59" : "#ffffff"
    readonly property color primaryContainer: dark ? "#183e6b" : "#d2e4ff"
    readonly property color textOnPrimaryContainer: dark ? "#d2e4ff" : "#001c3b"
    readonly property color secondary: dark ? "#bdc8db" : "#526071"
    readonly property color secondaryContainer: dark ? "#283446" : "#d6e4f7"
    readonly property color textOnSecondaryContainer: dark ? "#d8e3f5" : "#0f1c2b"
    readonly property color surface: dark ? "#0c1017" : "#f8f9fc"
    readonly property color surfaceContainerLowest: dark ? "#070a0e" : "#ffffff"
    readonly property color surfaceContainerLow: dark ? "#111620" : "#f2f4f8"
    readonly property color surfaceContainer: dark ? "#161d2a" : "#eceef3"
    readonly property color surfaceContainerHigh: dark ? "#1c2535" : "#e6e8ee"
    readonly property color surfaceVariant: dark ? "#28354b" : "#dbe0e9"
    readonly property color textOnSurface: dark ? "#e6e0e9" : "#1d1b20"
    readonly property color textOnSurfaceVariant: dark ? "#c3cddb" : "#43474f"
    readonly property color outline: dark ? "#8a96a8" : "#737780"
    readonly property color outlineVariant: dark ? "#222c3d" : "#c3c7d0"
    readonly property color network: dark ? "#70d7ee" : "#00677d"
    readonly property color error: dark ? "#ffb4ab" : "#ba1a1a"
    readonly property color errorContainer: dark ? "#680007" : "#ffdad6"
    readonly property color textOnErrorContainer: dark ? "#ffdad6" : "#410002"
    readonly property color success: dark ? "#7ee787" : "#146c2e"
    readonly property color successContainer: dark ? "#003915" : "#a5f5b0"
    readonly property color textOnSuccessContainer: dark ? "#a5f5b0" : "#002109"
    readonly property color warning: dark ? "#ffb95f" : "#815500"
    readonly property color warningContainer: dark ? "#493000" : "#ffddb0"
    readonly property color textOnWarningContainer: dark ? "#ffddb0" : "#291800"

    readonly property int space4: 4
    readonly property int space8: 8
    readonly property int space12: 12
    readonly property int space16: 16
    readonly property int space24: 24
    readonly property int space32: 32

    readonly property int shapeExtraSmall: 4
    readonly property int shapeSmall: 8
    readonly property int shapeMedium: 12
    readonly property int shapeLarge: 16
    readonly property int shapeLargeIncreased: 18
    readonly property int shapeExtraLarge: 20
    readonly property int shapeFull: 999

    readonly property int titleLarge: 20
    readonly property int titleMedium: 16
    readonly property int titleSmall: 14
    readonly property int bodyLarge: 14
    readonly property int bodyMedium: 13
    readonly property int bodySmall: 12
    readonly property int labelLarge: 13
    readonly property int labelMedium: 12
    readonly property int labelSmall: 11
}
