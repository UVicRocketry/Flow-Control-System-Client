import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// interactive drag handlebars for adjusting card colSpan and row-synced cardHeight
Item {
    id: root

    required property int cardIndex
    required property int colSpan
    required property real cardHeight
    required property real baseColumnWidth
    required property color resolvedColor
    required property bool editLayoutMode

    signal resizeRequested(int index, int newColSpan, real newHeight)

    anchors.fill: parent
    visible: root.editLayoutMode

    // right edge handlebar (adjusts colSpan 1 -> 3)
    Rectangle {
        id: rightHandlebar

        anchors.right: parent.right
        anchors.verticalCenter: parent.verticalCenter
        width: 10
        height: Math.min(parent.height * 0.6, 72)
        radius: 5
        color: rightDragArea.containsMouse || rightDragArea.pressed ? root.resolvedColor : Kirigami.Theme.disabledTextColor
        opacity: rightDragArea.containsMouse || rightDragArea.pressed ? 0.95 : 0.55

        ColumnLayout {
            anchors.centerIn: parent
            spacing: 3

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

        MouseArea {
            id: rightDragArea

            property real startX: 0
            property int startColSpan: 1

            anchors.fill: parent
            anchors.margins: -4
            hoverEnabled: true
            cursorShape: Qt.SizeHorCursor
            preventStealing: true
            onPressed: function(mouse) {
                startX = mapToGlobal(mouse.x, mouse.y).x;
                startColSpan = root.colSpan;
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return ;

                var curX = mapToGlobal(mouse.x, mouse.y).x;
                var deltaX = curX - startX;
                // use single-column base width as step threshold so dragging snaps cleanly per column
                var stepW = Math.max(160, root.baseColumnWidth);
                var spanDelta = Math.round(deltaX / (stepW * 0.65));
                var nextSpan = Math.max(1, Math.min(3, startColSpan + spanDelta));
                if (nextSpan !== root.colSpan)
                    root.resizeRequested(root.cardIndex, nextSpan, root.cardHeight);

            }
        }

    }

    // bottom edge handlebar (adjusts row height across all cards in the same row)
    Rectangle {
        id: bottomHandlebar

        anchors.bottom: parent.bottom
        anchors.horizontalCenter: parent.horizontalCenter
        width: Math.min(parent.width * 0.4, 96)
        height: 8
        radius: 4
        color: bottomDragArea.containsMouse || bottomDragArea.pressed ? root.resolvedColor : Kirigami.Theme.disabledTextColor
        opacity: bottomDragArea.containsMouse || bottomDragArea.pressed ? 0.95 : 0.55

        RowLayout {
            anchors.centerIn: parent
            spacing: 4

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

        MouseArea {
            id: bottomDragArea

            property real startY: 0
            property real startHeight: 230

            anchors.fill: parent
            anchors.margins: -4
            hoverEnabled: true
            cursorShape: Qt.SizeVerCursor
            preventStealing: true
            onPressed: function(mouse) {
                startY = mapToGlobal(mouse.x, mouse.y).y;
                startHeight = root.cardHeight;
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return ;

                var curY = mapToGlobal(mouse.x, mouse.y).y;
                var nextH = Math.max(210, Math.min(540, Math.round(startHeight + (curY - startY))));
                root.resizeRequested(root.cardIndex, root.colSpan, nextH);
            }
        }

    }

    // bottom-right corner handlebar (adjusts colSpan and row-synced height simultaneously)
    Rectangle {
        id: cornerHandlebar

        anchors.right: parent.right
        anchors.bottom: parent.bottom
        width: 16
        height: 16
        radius: 4
        color: cornerDragArea.containsMouse || cornerDragArea.pressed ? root.resolvedColor : Kirigami.Theme.disabledTextColor
        opacity: cornerDragArea.containsMouse || cornerDragArea.pressed ? 0.95 : 0.65

        Controls.Label {
            anchors.centerIn: parent
            text: "⋱"
            font.pixelSize: 11
            font.bold: true
            color: Kirigami.Theme.backgroundColor
        }

        MouseArea {
            id: cornerDragArea

            property real startX: 0
            property real startY: 0
            property int startColSpan: 1
            property real startHeight: 230

            anchors.fill: parent
            anchors.margins: -4
            hoverEnabled: true
            cursorShape: Qt.SizeFDiagCursor
            preventStealing: true
            onPressed: function(mouse) {
                var gp = mapToGlobal(mouse.x, mouse.y);
                startX = gp.x;
                startY = gp.y;
                startColSpan = root.colSpan;
                startHeight = root.cardHeight;
            }
            onPositionChanged: function(mouse) {
                if (!pressed)
                    return ;

                var gp = mapToGlobal(mouse.x, mouse.y);
                var stepW = Math.max(160, root.baseColumnWidth);
                var spanDelta = Math.round((gp.x - startX) / (stepW * 0.65));
                var nextSpan = Math.max(1, Math.min(3, startColSpan + spanDelta));
                var nextH = Math.max(210, Math.min(540, Math.round(startHeight + (gp.y - startY))));
                root.resizeRequested(root.cardIndex, nextSpan, nextH);
            }
        }

    }

}
