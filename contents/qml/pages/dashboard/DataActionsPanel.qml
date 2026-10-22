import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root

    required property string selectedDataName
    required property string effectiveDataMode
    required property bool isSelectedMarkedDeleted
    readonly property bool hasValidSelection: selectedDataName !== "" && !isSelectedMarkedDeleted

    signal showInBrowserRequested()
    signal openDataRequested()
    signal deleteDataRequested()
    signal undoDeleteRequested()
    signal downloadDataRequested()

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
        text: "Show in file browser"
        icon.name: "folder-open"
        enabled: root.hasValidSelection && root.effectiveDataMode === "local"
        onClicked: root.showInBrowserRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        text: "Load Data from file..."
        icon.name: "document-open"
        enabled: root.effectiveDataMode === "local"
        onClicked: root.openDataRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        text: "Download data..."
        icon.name: "edit-download"
        enabled: root.hasValidSelection && root.effectiveDataMode === "remote"
        onClicked: root.downloadDataRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        text: "Delete data..."
        icon.name: "edit-delete"
        enabled: root.hasValidSelection
        onClicked: root.deleteDataRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        visible: root.selectedDataName !== "" && root.isSelectedMarkedDeleted
        text: "Undo Delete"
        icon.name: "edit-undo"
        onClicked: root.undoDeleteRequested()
    }

}
