import QtQuick
import org.kde.kirigami as Kirigami

// Renders an application icon directly from the bundled dark or light SVG theme
Kirigami.Icon {
    id: root

    property string iconName: ""
    property int iconSize: Kirigami.Units.iconSizes.small
    property bool invertTheme: false
    readonly property bool systemIsLight: Application.styleHints.colorScheme === Qt.Light || (Application.styleHints.colorScheme === Qt.Unknown && Kirigami.Theme.backgroundColor.hslLightness > 0.5)
    readonly property bool useLightVariant: invertTheme ? !systemIsLight : systemIsLight
    readonly property string themeDir: useLightVariant ? "breeze-fallback-light" : "breeze-fallback"

    source: iconName.length > 0 ? Qt.resolvedUrl("../../icons/" + themeDir + "/flat/" + iconName + ".svg") : ""
    implicitWidth: iconSize
    implicitHeight: iconSize
}
