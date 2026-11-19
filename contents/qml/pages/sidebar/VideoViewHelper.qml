import ".."
import QtQuick
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

        IconToolButton {
            Layout.fillWidth: true
            flat: false
            centerContent: true
            iconName: root.camActive ? "network-disconnect" : "network-connect"
            labelText: root.camActive ? "Disc&onnect" : "C&onnect"
            highlighted: !root.camActive
            toolTipText: (root.camActive ? "Disconnect camera stream" : "Connect camera stream") + " (Alt+O)"
            onClicked: {
                if (root.hasBackend)
                    backend.toggle_camera();

            }
        }

        IconToolButton {
            Layout.fillWidth: true
            flat: false
            centerContent: true
            iconName: ""
            labelText: root.camMode === "manual" ? "&Mode: Manual" : "&Mode: Auto"
            toolTipText: "Toggle Auto / Manual camera IP mode (Alt+M)"
            onClicked: {
                if (root.hasBackend) {
                    let nextMode = root.camMode === "manual" ? "auto" : "manual";
                    backend.set_camera_settings(nextMode, root.camProfile, backend.camera_manual_target);
                }
            }
        }

        IconToolButton {
            Layout.fillWidth: true
            flat: false
            centerContent: true
            iconName: ""
            labelText: root.camProfile === "udp_high" ? "&Quality: High (UDP)" : "&Quality: Low (TCP)"
            toolTipText: "Toggle Low (TCP Sub) and High (UDP 5MP) stream quality (Alt+Q)"
            onClicked: {
                if (root.hasBackend) {
                    let nextProf = root.camProfile === "udp_high" ? "tcp_low" : "udp_high";
                    backend.set_camera_settings(root.camMode, nextProf, backend.camera_manual_target);
                }
            }
        }

    }

}
