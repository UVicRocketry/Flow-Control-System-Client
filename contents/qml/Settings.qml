import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// modal dialog for configuring toast severity, WebSocket connection defaults, and config folder access
Kirigami.Dialog {
    id: root

    property string minLogLevel: "INFO"
    readonly property var logLevels: ["INFO", "WARN", "ERR"]
    readonly property var refreshHzValues: [5, 10, 20, 30, 60]
    readonly property bool hasBackend: typeof backend !== "undefined" && backend !== null

    signal minLogLevelUpdated(string level)
    signal autoConnectToggled(bool enabled)

    title: "Settings"
    preferredWidth: Kirigami.Units.gridUnit * 24
    padding: Kirigami.Units.largeSpacing
    standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
    onOpened: {
        defaultUrlField.text = root.hasBackend ? backend.server_url : "ws://127.0.0.1:8080/ws";
        autoConnectCheck.checked = root.hasBackend ? backend.auto_reconnect : false;
        reconnectSpin.value = root.hasBackend ? backend.reconnect_interval_ms : 2000;
        var idx = root.logLevels.indexOf(root.minLogLevel);
        logLevelCombo.currentIndex = idx >= 0 ? idx : 0;
        var currentHz = root.hasBackend ? backend.view_refresh_hz : 20;
        var hzIdx = root.refreshHzValues.indexOf(currentHz);
        refreshHzCombo.currentIndex = hzIdx >= 0 ? hzIdx : 2;
    }
    onAccepted: {
        if (logLevelCombo.currentIndex >= 0 && logLevelCombo.currentIndex < root.logLevels.length)
            root.minLogLevelUpdated(root.logLevels[logLevelCombo.currentIndex]);

        if (root.hasBackend) {
            if (defaultUrlField.text.trim().length > 0)
                backend.set_server_url(defaultUrlField.text.trim());

            backend.set_auto_reconnect(autoConnectCheck.checked);
            backend.set_reconnect_interval_ms(reconnectSpin.value);
            if (refreshHzCombo.currentIndex >= 0 && refreshHzCombo.currentIndex < root.refreshHzValues.length)
                backend.set_view_refresh_hz(root.refreshHzValues[refreshHzCombo.currentIndex]);

        }
        root.autoConnectToggled(autoConnectCheck.checked);
    }

    Kirigami.FormLayout {
        wideMode: false

        Controls.ComboBox {
            id: logLevelCombo

            Kirigami.FormData.label: "Minimum Toast Severity:"
            Layout.fillWidth: true
            model: ["INFO — All notifications", "WARN — Warnings & errors only", "ERR — Critical errors only"]
        }

        Controls.ComboBox {
            id: refreshHzCombo

            Kirigami.FormData.label: "Plot Refresh Frequency:"
            Layout.fillWidth: true
            model: ["5 Hz (Low CPU)", "10 Hz", "20 Hz (Default)", "30 Hz", "60 Hz"]
        }

        Controls.TextField {
            id: defaultUrlField

            Kirigami.FormData.label: "Default Server WebSocket URL:"
            Layout.fillWidth: true
            font.family: "monospace"
            placeholderText: "ws://127.0.0.1:8080/ws"
        }

        Controls.CheckBox {
            id: autoConnectCheck

            Layout.fillWidth: true
            text: "Auto-connect to WebSocket server"
        }

        Controls.SpinBox {
            id: reconnectSpin

            Kirigami.FormData.label: "Auto-Reconnect Interval (ms):"
            Layout.fillWidth: true
            from: 500
            to: 60000
            stepSize: 500
            editable: true
        }

        Kirigami.Separator {
            Kirigami.FormData.isSection: true
            Kirigami.FormData.label: "Configuration Directory"
        }

        Controls.Label {
            Layout.fillWidth: true
            text: root.hasBackend ? backend.config_dir : ""
            font.family: "monospace"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            color: Kirigami.Theme.disabledTextColor
            elide: Text.ElideMiddle
        }

        Controls.Button {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            text: "Open Configuration Folder"
            icon.name: "folder-open"
            onClicked: {
                if (root.hasBackend)
                    backend.show_in_file_browser(backend.config_dir);

            }
        }

    }

}
