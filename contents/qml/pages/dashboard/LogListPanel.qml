import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root

    required property string effectiveLogMode
    required property bool isWebsocketConnected
    required property var activeLogList
    required property string selectedLogName
    required property var pendingDeleteMap

    signal logSelected(string name)
    signal logDoubleClicked(string name)
    signal refreshRequested()
    signal undoDeleteRequested(string name)
    signal renameRequested(string name)
    signal deleteRequested(string name)

    function isMarked(name) {
        return !!root.pendingDeleteMap[root.effectiveLogMode + ":" + name];
    }

    spacing: Kirigami.Units.smallSpacing

    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        Kirigami.SearchField {
            id: searchField

            Layout.fillWidth: true
            placeholderText: root.effectiveLogMode === "local" ? "Filter local logs..." : "Filter remote logs..."
        }

        Controls.ToolButton {
            icon.name: "view-refresh"
            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text: "Refresh log directory"
            onClicked: root.refreshRequested()
        }

    }

    Controls.Frame {
        Layout.fillWidth: true
        Layout.fillHeight: true
        padding: Kirigami.Units.gridUnit / 2
        Kirigami.Theme.colorSet: Kirigami.Theme.Complementary
        Kirigami.Theme.inherit: false

        Controls.ScrollView {
            anchors.fill: parent
            clip: true

            ListView {
                id: logListView

                spacing: 0
                model: root.activeLogList.filter(function(item) {
                    return searchField.text === "" || item.toLowerCase().indexOf(searchField.text.toLowerCase()) !== -1;
                })

                Kirigami.PlaceholderMessage {
                    anchors.centerIn: parent
                    width: parent.width - (Kirigami.Units.largeSpacing * 2)
                    visible: logListView.count === 0
                    icon.name: root.effectiveLogMode === "local" ? "folder-open" : (!root.isWebsocketConnected ? "network-disconnect" : "folder-open")
                    text: root.effectiveLogMode === "local" ? "No local logs found" : (!root.isWebsocketConnected ? "No connection" : "No remote logs found on the valve cart")
                    explanation: root.effectiveLogMode === "remote" && !root.isWebsocketConnected ? "Connect to the server to retrieve remote log files." : ""
                }

                delegate: Controls.ItemDelegate {
                    id: logDelegate

                    required property string modelData
                    required property int index
                    readonly property bool markedDeleted: root.isMarked(modelData)

                    width: ListView.view.width
                    height: Kirigami.Units.iconSizes.medium + Kirigami.Units.gridUnit
                    highlighted: root.selectedLogName === modelData && !markedDeleted
                    onClicked: root.logSelected(modelData)
                    onDoubleClicked: {
                        if (!markedDeleted)
                            root.logDoubleClicked(modelData);

                    }

                    background: Rectangle {
                        color: {
                            if (logDelegate.highlighted)
                                return Qt.alpha(Kirigami.Theme.highlightColor, 0.3);

                            if (logDelegate.hovered && !logDelegate.markedDeleted)
                                return Qt.alpha(Kirigami.Theme.hoverColor, 0.18);

                            return (logDelegate.index % 2 === 0) ? Kirigami.Theme.backgroundColor : Kirigami.Theme.alternateBackgroundColor;
                        }

                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: 1
                            visible: logDelegate.highlighted
                            color: Kirigami.Theme.highlightColor
                        }

                    }

                    // in-line actions
                    contentItem: RowLayout {
                        spacing: Kirigami.Units.smallSpacing

                        Kirigami.Icon {
                            Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                            Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                            source: root.effectiveLogMode === "local" ? "text-csv" : "network-server"
                            opacity: logDelegate.markedDeleted ? 0.38 : 1
                        }

                        Controls.Label {
                            Layout.fillWidth: true
                            text: logDelegate.modelData
                            elide: Text.ElideRight
                            font.strikeout: logDelegate.markedDeleted
                            opacity: logDelegate.markedDeleted ? 0.42 : 1
                            color: logDelegate.markedDeleted ? Kirigami.Theme.disabledTextColor : Kirigami.Theme.textColor
                        }

                        Controls.Label {
                            visible: logDelegate.markedDeleted
                            text: "Marked for deletion"
                            font.italic: true
                            font.pointSize: Kirigami.Theme.smallFont.pointSize
                            color: Kirigami.Theme.disabledTextColor
                        }

                        Controls.ToolButton {
                            visible: logDelegate.markedDeleted
                            icon.name: "edit-undo"
                            display: Controls.AbstractButton.IconOnly
                            Controls.ToolTip.visible: hovered
                            Controls.ToolTip.text: "Undo delete"
                            onClicked: root.undoDeleteRequested(logDelegate.modelData)
                        }

                        RowLayout {
                            // Show on hover OR when the item is highlighted/selected so touch/click works on Windows
                            visible: !logDelegate.markedDeleted && (logDelegate.hovered || logDelegate.highlighted)
                            spacing: Kirigami.Units.smallSpacing
                            Layout.fillHeight: true

                            Controls.ToolButton {
                                icon.name: "edit-rename"
                                display: Controls.AbstractButton.IconOnly
                                Controls.ToolTip.visible: hovered
                                Controls.ToolTip.text: "Rename log"
                                onClicked: root.renameRequested(logDelegate.modelData)
                            }

                            Controls.ToolButton {
                                icon.name: "edit-delete"
                                display: Controls.AbstractButton.IconOnly
                                Controls.ToolTip.visible: hovered
                                Controls.ToolTip.text: "Mark log for deletion"
                                onClicked: root.deleteRequested(logDelegate.modelData)
                            }

                        }

                    }

                }

            }

        }

        // the card it all goes in
        background: Rectangle {
            color: Kirigami.Theme.backgroundColor
            border.color: Kirigami.Theme.alternateBackgroundColor
            border.width: 1
            radius: Kirigami.Units.smallSpacing
        }

    }

}
