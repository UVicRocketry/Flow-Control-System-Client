import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root

    required property string effectiveDataMode
    required property bool isWebsocketConnected
    required property var activeDataList
    property var externalDataList: []
    required property string selectedDataName
    property string loadedDataName: ""
    required property var pendingDeleteMap

    signal dataSelected(string name)
    signal dataDoubleClicked(string name)
    signal refreshRequested()
    signal undoDeleteRequested(string name)
    signal renameRequested(string name)
    signal deleteRequested(string name)

    function isMarked(name, section) {
        var mode = section || root.effectiveDataMode;
        return !!root.pendingDeleteMap[mode + ":" + name];
    }

    spacing: Kirigami.Units.smallSpacing

    RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        Kirigami.SearchField {
            id: searchField

            Layout.fillWidth: true
            placeholderText: root.effectiveDataMode === "local" ? "Filter local data..." : "Filter remote data..."
        }

        Controls.ToolButton {
            icon.name: "view-refresh"
            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text: "Refresh data directory"
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
                id: dataListView

                spacing: 0
                model: {
                    var query = searchField.text.toLowerCase();
                    var items = [];
                    if (Array.isArray(root.externalDataList)) {
                        for (var i = 0; i < root.externalDataList.length; i++) {
                            var extItem = String(root.externalDataList[i]);
                            if (query === "" || extItem.toLowerCase().indexOf(query) !== -1) {
                                items.push({
                                    "name": extItem,
                                    "section": "external"
                                });
                            }
                        }
                    }
                    if (Array.isArray(root.activeDataList)) {
                        for (var j = 0; j < root.activeDataList.length; j++) {
                            var item = String(root.activeDataList[j]);
                            if (query === "" || item.toLowerCase().indexOf(query) !== -1) {
                                items.push({
                                    "name": item,
                                    "section": root.effectiveDataMode
                                });
                            }
                        }
                    }
                    return items;
                }
                section.property: "section"
                section.delegate: Rectangle {
                    required property string section

                    width: ListView.view.width
                    height: Kirigami.Units.gridUnit * 1.4
                    color: Kirigami.Theme.alternateBackgroundColor

                    Controls.Label {
                        anchors.verticalCenter: parent.verticalCenter
                        anchors.left: parent.left
                        anchors.leftMargin: Kirigami.Units.smallSpacing
                        text: parent.section
                        font.bold: true
                        font.pointSize: Kirigami.Theme.smallFont.pointSize
                        font.capitalization: Font.AllUppercase
                        color: Kirigami.Theme.disabledTextColor
                    }

                }

                Kirigami.PlaceholderMessage {
                    anchors.centerIn: parent
                    width: parent.width - (Kirigami.Units.largeSpacing * 2)
                    visible: dataListView.count === 0
                    icon.name: root.effectiveDataMode === "local" ? "folder-open" : (!root.isWebsocketConnected ? "network-disconnect" : "folder-open")
                    text: root.effectiveDataMode === "local" ? "No local data found" : (!root.isWebsocketConnected ? "No connection" : "No remote data found on the valve cart")
                    explanation: root.effectiveDataMode === "remote" && !root.isWebsocketConnected ? "Connect to the server to retrieve remote data files." : ""
                }

                delegate: Controls.ItemDelegate {
                    id: dataDelegate

                    required property var modelData
                    required property int index
                    readonly property string itemName: modelData && modelData.name !== undefined ? String(modelData.name) : String(modelData)
                    readonly property string itemSection: modelData && modelData.section !== undefined ? String(modelData.section) : root.effectiveDataMode
                    readonly property bool markedDeleted: root.isMarked(itemName, itemSection)
                    readonly property bool isLoaded: root.loadedDataName !== "" && root.loadedDataName === itemName && !markedDeleted

                    width: ListView.view.width
                    height: Kirigami.Units.iconSizes.medium + Kirigami.Units.gridUnit
                    highlighted: root.selectedDataName === itemName && !markedDeleted
                    onClicked: root.dataSelected(itemName)
                    onDoubleClicked: {
                        if (!markedDeleted)
                            root.dataDoubleClicked(itemName);

                    }

                    background: Rectangle {
                        color: {
                            if (dataDelegate.highlighted)
                                return Qt.alpha(Kirigami.Theme.highlightColor, 0.3);

                            if (dataDelegate.hovered && !dataDelegate.markedDeleted)
                                return Qt.alpha(Kirigami.Theme.hoverColor, 0.18);

                            return (dataDelegate.index % 2 === 0) ? Kirigami.Theme.backgroundColor : Kirigami.Theme.alternateBackgroundColor;
                        }

                        Rectangle {
                            anchors.bottom: parent.bottom
                            anchors.left: parent.left
                            anchors.right: parent.right
                            height: 1
                            visible: dataDelegate.highlighted
                            color: Kirigami.Theme.highlightColor
                        }

                    }

                    // in-line actions
                    contentItem: RowLayout {
                        spacing: Kirigami.Units.smallSpacing

                        Kirigami.Icon {
                            Layout.preferredWidth: Kirigami.Units.iconSizes.smallMedium
                            Layout.preferredHeight: Kirigami.Units.iconSizes.smallMedium
                            source: dataDelegate.itemSection === "remote" ? "network-server" : "text-csv"
                            opacity: dataDelegate.markedDeleted ? 0.38 : 1
                        }

                        Controls.Label {
                            Layout.fillWidth: true
                            text: dataDelegate.itemName
                            elide: Text.ElideRight
                            font.bold: dataDelegate.isLoaded
                            font.strikeout: dataDelegate.markedDeleted
                            opacity: dataDelegate.markedDeleted ? 0.42 : 1
                            color: dataDelegate.markedDeleted ? Kirigami.Theme.disabledTextColor : Kirigami.Theme.textColor
                        }

                        Controls.Label {
                            visible: dataDelegate.isLoaded
                            text: "Loaded"
                            font.italic: true
                            font.pointSize: Kirigami.Theme.smallFont.pointSize
                            color: Kirigami.Theme.positiveTextColor
                        }

                        Controls.Label {
                            visible: dataDelegate.markedDeleted
                            text: "Marked for deletion"
                            font.italic: true
                            font.pointSize: Kirigami.Theme.smallFont.pointSize
                            color: Kirigami.Theme.disabledTextColor
                        }

                        Controls.ToolButton {
                            visible: dataDelegate.markedDeleted
                            icon.name: "edit-undo"
                            display: Controls.AbstractButton.IconOnly
                            Controls.ToolTip.visible: hovered
                            Controls.ToolTip.text: "Undo delete"
                            onClicked: root.undoDeleteRequested(dataDelegate.itemName)
                        }

                        // control buttons
                        RowLayout {
                            // Show on hover OR when the item is highlighted/selected so touch/click works on Windows
                            visible: !dataDelegate.markedDeleted && (dataDelegate.hovered || dataDelegate.highlighted)
                            spacing: Kirigami.Units.smallSpacing
                            Layout.fillHeight: true

                            Controls.ToolButton {
                                icon.name: "edit-rename"
                                display: Controls.AbstractButton.IconOnly
                                Controls.ToolTip.visible: hovered
                                Controls.ToolTip.text: "Rename data"
                                onClicked: root.renameRequested(dataDelegate.itemName)
                            }

                            Controls.ToolButton {
                                icon.name: "edit-delete"
                                display: Controls.AbstractButton.IconOnly
                                Controls.ToolTip.visible: hovered
                                Controls.ToolTip.text: "Mark data for deletion"
                                onClicked: root.deleteRequested(dataDelegate.itemName)
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
