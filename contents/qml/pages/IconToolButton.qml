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
    property real contentOpacity: enabled ? 1 : 0.5
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
    property bool mirrorMnemonic: false
    property bool centerContent: false
    property string toolTipText: ""
    property bool toolTipVisible: hovered && toolTipText.length > 0
    readonly property bool hasIcon: iconName.length > 0
    readonly property bool isIconOnly: display === Controls.AbstractButton.IconOnly || labelText.length === 0
    readonly property string plainLabelText: labelText.replace(/&([A-Za-z0-9])/g, "$1")
    readonly property string mirroredRichText: {
        if (labelItem.Kirigami.MnemonicData.active)
            return labelText.replace(/&([A-Za-z0-9])/, "<u>$1</u>");

        return plainLabelText;
    }
    readonly property string badgeKeyText: {
        let m = labelItem.Kirigami.MnemonicData.mnemonicLabel.match(/&([A-Za-z0-9])/);
        if (m && m[1])
            return "<u>" + m[1].toUpperCase() + "</u>";

        let m2 = labelText.match(/&([A-Za-z0-9])/);
        return (m2 && m2[1]) ? ("<u>" + m2[1].toUpperCase() + "</u>") : "";
    }

    spacing: iconTextSpacing
    padding: Kirigami.Units.smallSpacing
    leftPadding: isIconOnly ? Kirigami.Units.smallSpacing + 2 : Kirigami.Units.mediumSpacing
    rightPadding: isIconOnly ? Kirigami.Units.smallSpacing + 2 : Kirigami.Units.mediumSpacing
    Kirigami.MnemonicData.enabled: false
    Kirigami.MnemonicData.label: ""
    Controls.ToolTip.visible: toolTipVisible
    Controls.ToolTip.text: toolTipText
    onVisibleChanged: {
        if (visible && labelText.length > 0 && !mirrorMnemonic) {
            Qt.callLater(function() {
                if (root.visible && !root.mirrorMnemonic) {
                    labelItem.Kirigami.MnemonicData.label = "";
                    labelItem.Kirigami.MnemonicData.label = root.labelText;
                }
            });
        }
    }

    // Alt-hold keycap badge for icon-only buttons with an assigned mnemonic labelText
    Rectangle {
        visible: root.isIconOnly && root.labelText.length > 0 && labelItem.Kirigami.MnemonicData.active && root.badgeKeyText.length > 0
        anchors.bottom: parent.bottom
        anchors.right: parent.right
        anchors.margins: 1
        width: Math.max(14, keycapText.implicitWidth + 6)
        height: 14
        radius: 3
        color: Kirigami.Theme.alternateBackgroundColor
        border.width: 1
        border.color: Kirigami.Theme.highlightColor
        z: 10

        Controls.Label {
            id: keycapText

            anchors.centerIn: parent
            text: root.badgeKeyText
            textFormat: Text.StyledText
            font.pixelSize: 9
            font.bold: true
            color: Kirigami.Theme.textColor
        }

    }

    contentItem: RowLayout {
        spacing: (root.isIconOnly || !root.hasIcon) ? 0 : root.iconTextSpacing
        opacity: root.contentOpacity

        Item {
            visible: root.centerContent && !root.isIconOnly
            Layout.fillWidth: true
        }

        BundledIcon {
            visible: root.hasIcon
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
            Kirigami.MnemonicData.enabled: root.enabled && root.visible && root.labelText.length > 0 && !root.mirrorMnemonic
            Kirigami.MnemonicData.controlType: root.labelText.indexOf("&") !== -1 ? Kirigami.MnemonicData.ActionElement : Kirigami.MnemonicData.SecondaryControl
            Kirigami.MnemonicData.label: root.labelText
            text: root.mirrorMnemonic ? root.mirroredRichText : labelItem.Kirigami.MnemonicData.richTextLabel
            textFormat: Text.StyledText
            font.bold: root.boldText
            color: root.textColor
            elide: Text.ElideRight

            Shortcut {
                enabled: labelItem.Kirigami.MnemonicData.enabled
                sequence: labelItem.Kirigami.MnemonicData.sequence
                onActivated: {
                    if (root.checkable)
                        root.toggle();

                    root.clicked();
                }
            }

        }

        Item {
            visible: root.centerContent && !root.isIconOnly
            Layout.fillWidth: true
        }

    }

}
