import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts

Rectangle {
    id: splashRoot

    // Dynamic properties updated from Python
    property string statusText: "Starting application..."
    property url iconSource: "img/icon.svg"

    // Automatically hug the layout's exact slim height
    width: 340
    height: mainLayout.implicitHeight + 32
    color: "#232629"
    border.color: "#3daee9"
    border.width: 1
    radius: 10

    ColumnLayout {
        id: mainLayout

        spacing: 4

        anchors {
            left: parent.left
            right: parent.right
            verticalCenter: parent.verticalCenter
            margins: 16
        }

        Image {
            Layout.alignment: Qt.AlignHCenter
            Layout.preferredWidth: 44
            Layout.preferredHeight: 44
            source: splashRoot.iconSource
            sourceSize: Qt.size(44, 44)
            visible: status === Image.Ready
        }

        Controls.Label {
            Layout.alignment: Qt.AlignHCenter
            text: "Flow Control System"
            color: "#eff0f1"
            font.pixelSize: 15
            font.bold: true
        }

        Controls.Label {
            Layout.alignment: Qt.AlignHCenter
            text: "UVic Rocketry"
            color: "#7f8c8d"
            font.pixelSize: 11
        }

        Item {
            Layout.preferredHeight: 6
        }

        Controls.Label {
            Layout.fillWidth: true
            text: splashRoot.statusText
            color: "#bdc3c7"
            font.pixelSize: 11
            elide: Text.ElideRight
        }

        // Slim animated gradient progress bar
        Rectangle {
            Layout.fillWidth: true
            Layout.preferredHeight: 4
            radius: 2
            color: "#1b1e20"
            border.color: "#31363b"
            border.width: 1
            clip: true

            Rectangle {
                id: barChunk

                width: parent.width * 0.4
                height: parent.height
                radius: 2

                gradient: Gradient {
                    orientation: Gradient.Horizontal

                    GradientStop {
                        position: 0
                        color: "#41D1FF"
                    }

                    GradientStop {
                        position: 1
                        color: "#BD34FE"
                    }

                }

                NumberAnimation on x {
                    from: -barChunk.width
                    to: barChunk.parent.width
                    duration: 1100
                    loops: Animation.Infinite
                    running: splashRoot.visible
                }

            }

        }

    }

}
