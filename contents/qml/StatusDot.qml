import QtQuick
import QtQuick.Layouts

// Reusable circular status indicator dot with optional infinite opacity pulse animation
Rectangle {
    id: root

    property int dotSize: 8
    property bool pulsing: false
    property real minPulseOpacity: 0.25
    property int pulseDuration: 400

    implicitWidth: dotSize
    implicitHeight: dotSize
    Layout.preferredWidth: dotSize
    Layout.preferredHeight: dotSize
    radius: dotSize / 2

    SequentialAnimation on opacity {
        running: root.pulsing
        loops: Animation.Infinite
        onRunningChanged: {
            if (!running)
                root.opacity = 1;
        }

        NumberAnimation {
            to: root.minPulseOpacity
            duration: root.pulseDuration
        }

        NumberAnimation {
            to: 1
            duration: root.pulseDuration
        }
    }
}
