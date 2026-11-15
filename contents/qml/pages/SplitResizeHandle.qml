import QtQuick
import org.kde.kirigami as Kirigami

// Hover-revealed resize handlebar positioned in the vertical seam between two split panes/tabs
Item {
    id: root

    required property real seamCenterX
    required property real availableWidth
    required property real leftMinWidth
    required property real rightMinWidth
    required property real leftTargetWidth
    required property real splitRatio
    readonly property bool activeOrHovered: resizeArea.containsMouse || resizeArea.pressed

    signal ratioChanged(real newRatio)

    x: root.seamCenterX - (width / 2)
    width: Math.max(parent ? 0 : 10, 10)

    Rectangle {
        anchors.horizontalCenter: parent.horizontalCenter
        width: 2
        height: parent.height
        radius: 1
        color: resizeArea.pressed ? Kirigami.Theme.highlightColor : Kirigami.Theme.disabledTextColor
        opacity: resizeArea.pressed ? 0.65 : (resizeArea.containsMouse ? 0.35 : 0)

        Behavior on opacity {
            NumberAnimation {
                duration: 120
            }

        }

    }

    DragHandlebar {
        anchors.centerIn: parent
        orientation: Qt.Vertical
        active: resizeArea.pressed
        opacity: root.activeOrHovered ? 0.95 : 0

        Behavior on opacity {
            NumberAnimation {
                duration: 120
            }

        }

    }

    MouseArea {
        id: resizeArea

        property real startGlobalX: 0
        property real startLeftWidth: 0

        anchors.fill: parent
        hoverEnabled: true
        cursorShape: Qt.SizeHorCursor
        preventStealing: true
        onPressed: function(mouse) {
            startGlobalX = mapToGlobal(mouse.x, mouse.y).x;
            startLeftWidth = root.leftTargetWidth;
        }
        onPositionChanged: function(mouse) {
            if (!pressed)
                return ;

            let curGlobalX = mapToGlobal(mouse.x, mouse.y).x;
            let deltaX = curGlobalX - startGlobalX;
            let availW = root.availableWidth;
            let maxLeft = Math.max(root.leftMinWidth, availW - root.rightMinWidth);
            let nextLeft = Math.max(root.leftMinWidth, Math.min(maxLeft, startLeftWidth + deltaX));
            root.ratioChanged(nextLeft / availW);
        }
        onDoubleClicked: {
            root.ratioChanged(0.5);
        }
    }

}
