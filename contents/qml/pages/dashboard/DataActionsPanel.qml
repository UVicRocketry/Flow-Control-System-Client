import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// side action panel for opening, revealing, downloading, deleting, and undoing telemetry data files
ColumnLayout {
    id: root

    required property string selectedDataName
    required property string effectiveDataMode
    required property bool isSelectedMarkedDeleted
    property bool isWebsocketConnected: false
    readonly property bool hasValidSelection: selectedDataName !== "" && !isSelectedMarkedDeleted

    signal showInBrowserRequested()
    signal openDataRequested()
    signal deleteDataRequested()
    signal undoDeleteRequested()
    signal downloadDataRequested()
    signal pushDataRequested()

    Layout.preferredWidth: implicitWidth
    Layout.maximumWidth: implicitWidth
    Layout.alignment: Qt.AlignTop
    spacing: Kirigami.Units.smallSpacing

    Kirigami.Heading {
        Layout.alignment: Qt.AlignTop
        text: "Data Actions"
        level: 4
        color: Kirigami.Theme.disabledTextColor
    }

    Item {
        Layout.fillWidth: true
        Layout.fillHeight: true
    }

    Controls.Button {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        text: "Show in file browser"
        icon.name: "folder-open"
        enabled: root.hasValidSelection && root.effectiveDataMode === "local"
        onClicked: root.showInBrowserRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        text: "Load Data from file..."
        icon.name: "document-open"
        enabled: root.effectiveDataMode === "local"
        onClicked: root.openDataRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        text: root.effectiveDataMode === "local" ? "Push to server..." : "Download data..."
        icon.name: root.effectiveDataMode === "local" ? "network-server" : "edit-download"
        enabled: root.hasValidSelection && root.isWebsocketConnected
        Controls.ToolTip.visible: hovered && !enabled && root.hasValidSelection && !root.isWebsocketConnected
        Controls.ToolTip.text: "Connect to the valve cart server to transfer data."
        onClicked: {
            if (root.effectiveDataMode === "local")
                root.pushDataRequested();
            else
                root.downloadDataRequested();
        }
    }

    Controls.Button {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        text: "Delete data..."
        icon.name: "edit-delete"
        enabled: root.hasValidSelection
        onClicked: root.deleteDataRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing
        visible: root.selectedDataName !== "" && root.isSelectedMarkedDeleted
        text: "Undo Delete"
        icon.name: "edit-undo"
        onClicked: root.undoDeleteRequested()
    }

}
