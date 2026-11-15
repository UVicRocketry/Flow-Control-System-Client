import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// ToolButton helper that renders bundled dark/light SVG icons via Kirigami.Icon with consistent spacing across styles
Controls.ToolButton {
    id: root

    property string iconName: icon.name
    property int iconSize: Kirigami.Units.iconSizes.small
    property int iconTextSpacing: Kirigami.Units.smallSpacing
    property real contentOpacity: enabled ? 1.0 : 0.5
    property bool invertOnChecked: (checked || highlighted) && !flat && Qt.platform.os === "windows"
    property color textColor: {
        if (invertOnChecked) {
            var isLight = Application.styleHints.colorScheme === Qt.Light || (Application.styleHints.colorScheme === Qt.Unknown && Kirigami.Theme.backgroundColor.hslLightness > 0.5);
            return isLight ? "#ffffff" : "#000000";
        }
        return Kirigami.Theme.textColor;
    }
    property color iconColor: textColor
    property string labelText: ""
    property bool boldText: false
    property string toolTipText: ""
    property bool toolTipVisible: hovered && toolTipText.length > 0
    readonly property bool isIconOnly: display === Controls.AbstractButton.IconOnly || labelText.length === 0

    spacing: iconTextSpacing
    padding: Kirigami.Units.smallSpacing
    leftPadding: isIconOnly ? Kirigami.Units.smallSpacing + 2 : Kirigami.Units.mediumSpacing
    rightPadding: isIconOnly ? Kirigami.Units.smallSpacing + 2 : Kirigami.Units.mediumSpacing
    Kirigami.MnemonicData.enabled: false
    Kirigami.MnemonicData.label: ""
    Controls.ToolTip.visible: toolTipVisible
    Controls.ToolTip.text: toolTipText

    contentItem: RowLayout {
        spacing: root.isIconOnly ? 0 : root.iconTextSpacing
        opacity: root.contentOpacity

        BundledIcon {
            Layout.alignment: root.isIconOnly ? Qt.AlignCenter : Qt.AlignVCenter
            iconName: root.iconName
            iconSize: root.iconSize
            invertTheme: root.invertOnChecked
            color: root.iconColor
        }

        Controls.Label {
            id: labelItem

            visible: !root.isIconOnly
            Layout.alignment: Qt.AlignVCenter
            Kirigami.MnemonicData.enabled: root.enabled && root.visible && !root.isIconOnly
            Kirigami.MnemonicData.controlType: Kirigami.MnemonicData.SecondaryControl
            Kirigami.MnemonicData.label: root.labelText
            text: labelItem.Kirigami.MnemonicData.richTextLabel
            textFormat: Text.StyledText
            font.bold: root.boldText
            color: root.textColor

            Shortcut {
                enabled: labelItem.Kirigami.MnemonicData.enabled
                sequence: labelItem.Kirigami.MnemonicData.sequence
                onActivated: {
                    if (typeof root.animateClick === "function")
                        root.animateClick();
                    else
                        root.clicked();
                }
            }
        }
    }
}
