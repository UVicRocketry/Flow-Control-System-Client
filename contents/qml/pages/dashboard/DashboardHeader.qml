import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root

    required property string dataSourceMode
    required property string selectedLogName

    signal modeSelected(string mode)

    spacing: Kirigami.Units.smallSpacing

    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.largeSpacing

        ColumnLayout {
            spacing: Kirigami.Units.mediumSpacing

            Kirigami.Heading {
                text: "Dashboard"
                level: 3
                Layout.fillWidth: true
            }

            Item {
                Layout.fillHeight: true
            }

            Controls.Label {
                text: root.dataSourceMode === "live" ? "Viewing live telemetry. Actuation panels are accessible from the left sidebar navigation." : (root.selectedLogName !== "" ? "Viewing log:\n" + root.selectedLogName : "Select a log file below and click 'Load Log' to inspect recorded telemetry.")
                color: Kirigami.Theme.disabledTextColor
                wrapMode: Text.WordWrap
                Layout.fillWidth: true
            }

        }

        Kirigami.NavigationTabBar {
            Layout.preferredWidth: Kirigami.Units.gridUnit * 22
            actions: [
                Kirigami.Action {
                    text: "Live data"
                    icon.name: "media-record"
                    checked: root.dataSourceMode === "live"
                    onTriggered: root.modeSelected("live")
                },
                Kirigami.Action {
                    text: "Local logs"
                    icon.name: "folder"
                    checked: root.dataSourceMode === "local"
                    onTriggered: root.modeSelected("local")
                },
                Kirigami.Action {
                    text: "Remote logs"
                    icon.name: "network-wired"
                    checked: root.dataSourceMode === "remote"
                    onTriggered: root.modeSelected("remote")
                }
            ]
        }

    }

    Kirigami.Separator {
        Layout.topMargin: Kirigami.Units.smallSpacing
        Layout.fillWidth: true
    }

}
