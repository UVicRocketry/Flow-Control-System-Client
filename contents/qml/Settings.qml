import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// modal dialog for configuring toast severity, WebSocket connection defaults, and config folder access
Kirigami.Dialog {
    id: root

    property string minLogLevel: "INFO"
    readonly property var refreshHzValues: [5, 10, 20, 30, 60]

    signal minLogLevelUpdated(string level)
    signal autoConnectToggled(bool enabled)

    title: "Settings"
    preferredWidth: Kirigami.Units.gridUnit * 24
    padding: Kirigami.Units.largeSpacing
    standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
    onOpened: {
        defaultUrlField.text = (typeof backend !== "undefined" && backend) ? backend.server_url : "ws://127.0.0.1:8080/ws";
        autoConnectCheck.checked = (typeof backend !== "undefined" && backend) ? backend.auto_reconnect : false;
        reconnectSpin.value = (typeof backend !== "undefined" && backend) ? backend.reconnect_interval_ms : 2000;
        var levels = ["INFO", "WARN", "ERR"];
        var idx = levels.indexOf(root.minLogLevel);
        logLevelCombo.currentIndex = idx >= 0 ? idx : 0;
        var currentHz = (typeof backend !== "undefined" && backend) ? backend.view_refresh_hz : 20;
        var hzIdx = root.refreshHzValues.indexOf(currentHz);
        refreshHzCombo.currentIndex = hzIdx >= 0 ? hzIdx : 2;
    }
    onAccepted: {
        var levels = ["INFO", "WARN", "ERR"];
        if (logLevelCombo.currentIndex >= 0 && logLevelCombo.currentIndex < levels.length)
            root.minLogLevelUpdated(levels[logLevelCombo.currentIndex]);

        if (typeof backend !== "undefined" && backend) {
            if (defaultUrlField.text.trim().length > 0)
                backend.set_server_url(defaultUrlField.text.trim());

            backend.set_auto_reconnect(autoConnectCheck.checked);
            backend.set_reconnect_interval_ms(reconnectSpin.value);
            if (refreshHzCombo.currentIndex >= 0 && refreshHzCombo.currentIndex < root.refreshHzValues.length)
                backend.set_view_refresh_hz(root.refreshHzValues[refreshHzCombo.currentIndex]);

        }
        root.autoConnectToggled(autoConnectCheck.checked);
    }

    ColumnLayout {
        spacing: Kirigami.Units.mediumSpacing

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Controls.Label {
                text: "Minimum Toast Severity"
                font.bold: true
            }

            Controls.ComboBox {
                id: logLevelCombo

                Layout.fillWidth: true
                model: ["INFO — All notifications", "WARN — Warnings & errors only", "ERR — Critical errors only"]
            }

        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Controls.Label {
                text: "Plot Refresh Frequency"
                font.bold: true
            }

            Controls.ComboBox {
                id: refreshHzCombo

                Layout.fillWidth: true
                model: ["5 Hz (Low CPU)", "10 Hz", "20 Hz (Default)", "30 Hz", "60 Hz"]
            }

        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Controls.Label {
                text: "Default Server WebSocket URL"
                font.bold: true
            }

            Controls.TextField {
                id: defaultUrlField

                Layout.fillWidth: true
                font.family: "monospace"
                placeholderText: "ws://127.0.0.1:8080/ws"
            }

        }

        Controls.CheckBox {
            id: autoConnectCheck

            Layout.fillWidth: true
            text: "Auto-connect to WebSocket server"
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Controls.Label {
                text: "Auto-Reconnect Interval (ms)"
                font.bold: true
            }

            Controls.SpinBox {
                id: reconnectSpin

                Layout.fillWidth: true
                from: 500
                to: 60000
                stepSize: 500
                editable: true
            }

        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 4

            Controls.Label {
                text: "Configuration Directory"
                font.bold: true
            }

            Controls.Label {
                Layout.fillWidth: true
                text: (typeof backend !== "undefined" && backend) ? backend.config_dir : ""
                font.family: "monospace"
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: Kirigami.Theme.disabledTextColor
                elide: Text.ElideMiddle
            }

            Controls.Button {
                Layout.fillWidth: true
                text: "Open Configuration Folder"
                icon.name: "folder-open"
                onClicked: {
                    if (typeof backend !== "undefined" && backend)
                        backend.show_in_file_browser(backend.config_dir);

                }
            }

        }

    }

}
