import QtQuick
import org.kde.kirigami as Kirigami

// Renders a native theme icon on Linux/macOS with bundled dark/light SVG fallback
Kirigami.Icon {
    id: root

    property string iconName: ""
    property int iconSize: Kirigami.Units.iconSizes.small
    property bool invertTheme: false
    readonly property bool systemIsLight: Application.styleHints.colorScheme === Qt.Light || (Application.styleHints.colorScheme === Qt.Unknown && Kirigami.Theme.backgroundColor.hslLightness > 0.5)
    readonly property bool useLightVariant: invertTheme ? !systemIsLight : systemIsLight
    readonly property string themeDir: useLightVariant ? "breeze-fallback-light" : "breeze-fallback"
    readonly property string bundledPath: iconName.length > 0 ? Qt.resolvedUrl("../../icons/" + themeDir + "/flat/" + iconName + ".svg") : ""

    source: iconName.length > 0 ? (Qt.platform.os === "windows" ? bundledPath : iconName) : ""
    fallback: bundledPath
    implicitWidth: iconSize
    implicitHeight: iconSize
}
