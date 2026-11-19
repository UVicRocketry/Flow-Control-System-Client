import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// sidebar view helper for the IP camera video page
ColumnLayout {
    id: root

    readonly property bool hasBackend: typeof backend !== "undefined" && backend !== null
    readonly property string camMode: hasBackend ? backend.camera_mode : "auto"
    readonly property string camProfile: hasBackend ? backend.camera_profile : "tcp_low"
    readonly property bool camActive: hasBackend ? backend.camera_active : false

    Layout.fillWidth: true
    spacing: Kirigami.Units.smallSpacing

    Kirigami.ListSectionHeader {
        Layout.fillWidth: true
        text: "Camera Stream"
    }

    ColumnLayout {
        Layout.fillWidth: true
        Layout.leftMargin: Kirigami.Units.smallSpacing
        Layout.rightMargin: Kirigami.Units.smallSpacing
        spacing: Kirigami.Units.smallSpacing

        Controls.Button {
            id: sidebarConnectBtn

            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing
            text: root.camActive ? "Disconnect" : "Connect"
            icon.name: root.camActive ? "network-disconnect" : "network-connect"
            highlighted: !root.camActive
            onClicked: {
                if (root.hasBackend)
                    backend.toggle_camera();

            }
            Component.onCompleted: {
                if (background && ("text" in background))
                    background.text = Qt.binding(function() {
                        return sidebarConnectBtn.Kirigami.MnemonicData.active ? ("&" + sidebarConnectBtn.text) : sidebarConnectBtn.text;
                    });

            }
        }

        Controls.ComboBox {
            Layout.fillWidth: true
            model: ["Mode: Auto", "Mode: Manual"]
            currentIndex: root.camMode === "manual" ? 1 : 0
            onActivated: function(idx) {
                if (root.hasBackend)
                    backend.set_camera_settings(idx === 1 ? "manual" : "auto", root.camProfile, backend.camera_manual_target);

            }
        }

        Controls.ComboBox {
            Layout.fillWidth: true
            model: ["TCP / Low (Sub)", "UDP / High (5MP)"]
            currentIndex: root.camProfile === "udp_high" ? 1 : 0
            onActivated: function(idx) {
                if (root.hasBackend)
                    backend.set_camera_settings(root.camMode, idx === 1 ? "udp_high" : "tcp_low", backend.camera_manual_target);

            }
        }

    }

}
