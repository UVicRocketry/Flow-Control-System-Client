import ".."
import "./dashboard"
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: dashboard

    property bool disconnectBannerDismissed: false

    spacing: Kirigami.Units.largeSpacing
    Component.onDestruction: fn.commitPendingDeletions()
    Layout.fillHeight: true

    // helper functions
    DashboardFunctions {
        id: fn
    }

    Connections {
        function onDisconnected() {
            fn.commitPendingDeletions();
            dashboard.disconnectBannerDismissed = false;
        }

        function onWebsocketClosed() {
            fn.commitPendingDeletions();
            dashboard.disconnectBannerDismissed = false;
        }

        target: typeof backend !== "undefined" ? backend : null
        ignoreUnknownSignals: true
    }

    // 1. Websocket Card
    Kirigami.Card {
        Layout.fillWidth: true

        header: ColumnLayout {
            spacing: Kirigami.Units.largeSpacing

            Kirigami.Heading {
                text: "Websocket connection"
                level: 2
                Layout.fillWidth: true
            }

            Websocket {
                id: ws

                Layout.fillWidth: true
                compact: false
            }

        }

    }

    // 2. Main Dashboard Card
    Kirigami.Card {
        Layout.fillWidth: true
        Layout.preferredHeight: Kirigami.Units.gridUnit * 24
        Layout.minimumHeight: Kirigami.Units.gridUnit * 24
        Layout.fillHeight: true
        Layout.bottomMargin: -1 * Kirigami.Units.gridUnit / 2

        header: DashboardHeader {
            dataSourceMode: fn.dataSourceMode
            selectedDataName: fn.selectedDataName
            onModeSelected: function(mode) {
                if (mode !== "live") {
                    fn.lastHistoryMode = mode;
                    fn.selectedDataName = "";
                    fn.refreshData(mode);
                }
                fn.dataSourceMode = mode;
            }
        }

        contentItem: ColumnLayout {
            spacing: Kirigami.Units.mediumSpacing
            Layout.fillHeight: true
            Layout.margins: Kirigami.Units.gridUnit / 2

            RowLayout {
                id: dataBrowserContent

                enabled: fn.dataSourceMode !== "live"
                opacity: enabled ? 1 : 0.42
                spacing: Kirigami.Units.largeSpacing
                Layout.fillWidth: true
                Layout.fillHeight: true

                // pass functions to helper
                // for anything in the data viewing panel itself
                DataListPanel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    effectiveDataMode: fn.effectiveDataMode
                    isWebsocketConnected: fn.isWebsocketConnected
                    activeDataList: fn.activeDataList
                    selectedDataName: fn.selectedDataName
                    pendingDeleteMap: fn.pendingDeleteMap
                    onDataSelected: function(name) {
                        fn.selectedDataName = name;
                    }
                    onDataDoubleClicked: function(name) {
                        fn.selectedDataName = name;
                        fn.loadSelectedData();
                    }
                    onRefreshRequested: fn.refreshData(fn.effectiveDataMode)
                    onUndoDeleteRequested: function(name) {
                        fn.undoDeletion(name);
                    }
                    onRenameRequested: function(name) {
                        fn.targetActionData = name;
                        dataDialogs.openRename(name);
                    }
                    onDeleteRequested: function(name) {
                        fn.targetActionData = name;
                        dataDialogs.openDeleteConfirm();
                    }
                }

                Kirigami.Separator {
                    Layout.fillHeight: true
                }

                // pass functions to helper
                // for anything in the actions panel to the side
                DataActionsPanel {
                    selectedDataName: fn.selectedDataName
                    effectiveDataMode: fn.effectiveDataMode
                    isSelectedMarkedDeleted: fn.selectedDataName !== "" && fn.isMarkedForDeletion(fn.selectedDataName)
                    onShowInBrowserRequested: {
                        if (typeof backend !== "undefined" && backend !== null && backend.show_in_file_browser !== undefined)
                            backend.show_in_file_browser(fn.selectedDataName);

                    }
                    // onLoadDataRequested: fn.loadSelectedData()
                    onOpenDataRequested: fn.openSelectedData()
                    onDeleteDataRequested: {
                        fn.targetActionData = fn.selectedDataName;
                        dataDialogs.openDeleteConfirm();
                    }
                    onUndoDeleteRequested: fn.undoDeletion(fn.selectedDataName)
                }

                Behavior on opacity {
                    NumberAnimation {
                        duration: Kirigami.Units.shortDuration
                    }

                }

            }

            // warn if trying to access remote server while not connected
            Kirigami.InlineMessage {
                id: connWarn

                Layout.fillWidth: true
                type: Kirigami.MessageType.Information
                icon.name: "emblem-information"
                visible: fn.dataSourceMode === "remote" && !fn.isWebsocketConnected && !dashboard.disconnectBannerDismissed
                text: "Not connected. Connect to the server to retrieve remote data files."
                actions: [
                    Kirigami.Action {
                        text: "Connect"
                        icon.name: "network-connect"
                        onTriggered: {
                            ws.connectSocket();
                        }
                    },
                    Kirigami.Action {
                        icon.name: "window-close"
                        onTriggered: connWarn.visible = false
                    }
                ]
            }

        }

    }

    // 3. Data-related dialogs
    DataDialogs {
        id: dataDialogs

        targetActionData: fn.targetActionData
        onRenameConfirmed: function(newName) {
            let next = Object.assign({
            }, fn.renamedDataMap);
            next[fn.dataKey(fn.effectiveDataMode, fn.targetActionData)] = newName;
            fn.renamedDataMap = next;
            if (fn.selectedDataName === fn.targetActionData)
                fn.selectedDataName = newName;

            if (typeof backend !== "undefined" && backend !== null && backend.rename_data !== undefined)
                backend.rename_data(fn.effectiveDataMode, fn.targetActionData, newName);

        }
        onDeleteConfirmed: {
            fn.markForDeletion(fn.targetActionData);
        }
    }

}
