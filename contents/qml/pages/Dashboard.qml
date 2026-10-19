import ".."
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: dashboard

    spacing: Kirigami.Units.largeSpacing

    Kirigami.Card {
        Layout.fillWidth: true

        header: ColumnLayout {
            spacing: Kirigami.Units.largeSpacing

            Kirigami.Heading {
                text: "Websocket connection"
                level: 2
                Layout.fillWidth: true
            }

            Websocket {
                Layout.fillWidth: true
                compact: false
            }

        }

    }

    // Dashboard overview placeholder
    Kirigami.Card {
        Layout.fillWidth: true
        Layout.fillHeight: true

        header: Kirigami.Heading {
            text: "Dashboard"
            level: 3
        }

        contentItem: ColumnLayout {
            spacing: Kirigami.Units.mediumSpacing

            Controls.Label {
                text: "Telemetry and actuation panels are accessible from the left sidebar navigation."
                color: Kirigami.Theme.disabledTextColor
            }

            Item {
                Layout.fillHeight: true
            }

        }

    }

}
