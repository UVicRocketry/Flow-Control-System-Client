import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Pill-shaped 3-dot drag handlebar used by split-view and graph-card resize handles
Rectangle {
    id: root

    property int orientation: Qt.Vertical
    property bool active: false
    property color activeColor: Kirigami.Theme.highlightColor
    property color inactiveColor: Kirigami.Theme.disabledTextColor

    implicitWidth: orientation === Qt.Vertical ? 10 : Math.min((parent ? parent.width : 240) * 0.4, 96)
    implicitHeight: orientation === Qt.Vertical ? Math.min((parent ? parent.height : 120) * 0.6, 72) : 8
    width: implicitWidth
    height: implicitHeight
    radius: Math.min(width, height) / 2
    color: root.active ? root.activeColor : root.inactiveColor

    GridLayout {
        anchors.centerIn: parent
        columns: root.orientation === Qt.Vertical ? 1 : 3
        rowSpacing: 3
        columnSpacing: 4

        Repeater {
            model: 3

            Rectangle {
                width: 4
                height: 4
                radius: 2
                color: Kirigami.Theme.backgroundColor
            }

        }

    }

}
