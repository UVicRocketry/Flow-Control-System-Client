import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root

    required property string selectedLogName
    required property string effectiveLogMode
    required property bool isSelectedMarkedDeleted
    readonly property bool hasValidSelection: selectedLogName !== "" && !isSelectedMarkedDeleted

    signal showInBrowserRequested()
    signal loadLogRequested()
    signal deleteLogRequested()
    signal undoDeleteRequested()

    Layout.preferredWidth: implicitWidth
    Layout.maximumWidth: implicitWidth
    Layout.alignment: Qt.AlignTop
    spacing: Kirigami.Units.smallSpacing

    Kirigami.Heading {
        Layout.alignment: Qt.AlignTop
        text: "Log Actions"
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
        enabled: root.hasValidSelection && root.effectiveLogMode === "local"
        onClicked: root.showInBrowserRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        text: "Load Log from file..."
        icon.name: "document-open"
        enabled: root.hasValidSelection
        onClicked: root.loadLogRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        text: "Download log..."
        icon.name: "edit-download"
        enabled: root.hasValidSelection && root.effectiveLogMode === "remote"
        onClicked: root.deleteLogRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        text: "Delete log..."
        icon.name: "edit-delete"
        enabled: root.hasValidSelection
        onClicked: root.deleteLogRequested()
    }

    Controls.Button {
        Layout.fillWidth: true
        visible: root.selectedLogName !== "" && root.isSelectedMarkedDeleted
        text: "Undo Delete"
        icon.name: "edit-undo"
        onClicked: root.undoDeleteRequested()
    }

}
