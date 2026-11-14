import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: video

    spacing: Kirigami.Units.largeSpacing
    Layout.fillWidth: true
    Layout.fillHeight: true

    Kirigami.Card {
        Layout.fillWidth: true
        Layout.fillHeight: true

        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: Math.min(parent.width - (Kirigami.Units.largeSpacing * 2), Kirigami.Units.gridUnit * 24)
            icon.name: "camera-video"
            text: "Placeholder"
            explanation: "Placeholder card for the IP camera"
        }

    }

}
