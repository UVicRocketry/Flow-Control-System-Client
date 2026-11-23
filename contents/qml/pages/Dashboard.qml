import ".."
import "./dashboard"
import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// dashboard page for WebSocket connection management and browsing local, external, and remote telemetry logs
ColumnLayout {
    id: dashboard

    property bool disconnectBannerDismissed: false
    property string dataSourceMode: fn.dataSourceMode

    spacing: Kirigami.Units.gridUnit / 2
    Component.onDestruction: fn.commitPendingDeletions()
    Layout.fillWidth: true
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

        function onData_loaded(mode, filePath, data) {
            fn.onLoad_data(mode, filePath, data);
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

        header: DashboardHeader {
            dataSourceMode: fn.dataSourceMode
            selectedDataName: fn.selectedDataName
            loadedDataName: fn.loadedDataName
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
                    externalDataList: fn.externalDataList
                    selectedDataName: fn.selectedDataName
                    loadedDataName: fn.loadedDataName
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
                    onHideRequested: function(name) {
                        fn.hideExternalData(name);
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
                    isWebsocketConnected: fn.isWebsocketConnected
                    onShowInBrowserRequested: {
                        if (typeof backend !== "undefined" && backend !== null && backend.show_in_file_browser !== undefined)
                            backend.show_in_file_browser(fn.selectedDataName);

                    }
                    onOpenDataRequested: fn.openSelectedData()
                    onDownloadDataRequested: fn.downloadSelectedData()
                    onPushDataRequested: fn.pushSelectedData()
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
                    // Keep explicit window-close Action instead of showCloseButton: true due to a close-button bug in fluentwinui3
                    Kirigami.Action {
                        icon.name: "window-close"
                        onTriggered: dashboard.disconnectBannerDismissed = true
                    }
                ]
            }

        }

    }

    // 3. Data-related dialogs (hidden Item so ColumnLayout reserves zero space/spacing below the bottom card)
    DataDialogs {
        id: dataDialogs

        visible: false
        targetActionData: fn.targetActionData
        onRenameConfirmed: function(newName) {
            fn.applyRename(fn.targetActionData, newName);
        }
        onDeleteConfirmed: {
            fn.markForDeletion(fn.targetActionData);
        }
    }

}
