import QtQuick
import QtQuick.Controls as Controls
import org.kde.kirigami as Kirigami

// Clickable colour swatch used in GraphEditDialog for both theme and fixed colour palettes
Rectangle {
    id: root

    required property string colorKey
    required property color swatchColor
    property string tooltipText: colorKey
    property bool selected: false
    property real swatchRadius: 6
    property color unselectedBorderColor: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.25)

    signal picked(string key)

    implicitWidth: 24
    implicitHeight: 24
    width: 24
    height: 24
    radius: swatchRadius
    color: swatchColor
    border.width: selected ? 2 : 1
    border.color: selected ? Kirigami.Theme.textColor : unselectedBorderColor
    Controls.ToolTip.visible: swatchArea.containsMouse
    Controls.ToolTip.text: tooltipText

    MouseArea {
        id: swatchArea

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.PointingHandCursor
        onClicked: root.picked(root.colorKey)
    }
}
