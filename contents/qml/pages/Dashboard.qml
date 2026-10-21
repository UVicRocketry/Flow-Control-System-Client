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
            selectedLogName: fn.selectedLogName
            onModeSelected: function(mode) {
                if (mode !== "live") {
                    fn.lastHistoryMode = mode;
                    fn.selectedLogName = "";
                    fn.refreshLogs(mode);
                }
                fn.dataSourceMode = mode;
            }
        }

        contentItem: ColumnLayout {
            spacing: Kirigami.Units.mediumSpacing
            Layout.fillHeight: true
            Layout.margins: Kirigami.Units.gridUnit / 2

            RowLayout {
                id: logBrowserContent

                enabled: fn.dataSourceMode !== "live"
                opacity: enabled ? 1 : 0.42
                spacing: Kirigami.Units.largeSpacing
                Layout.fillWidth: true
                Layout.fillHeight: true

                // pass functions to helper
                LogListPanel {
                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    effectiveLogMode: fn.effectiveLogMode
                    isWebsocketConnected: fn.isWebsocketConnected
                    activeLogList: fn.activeLogList
                    selectedLogName: fn.selectedLogName
                    pendingDeleteMap: fn.pendingDeleteMap
                    onLogSelected: function(name) {
                        fn.selectedLogName = name;
                    }
                    onLogDoubleClicked: function(name) {
                        fn.selectedLogName = name;
                        fn.loadSelectedLog();
                    }
                    onRefreshRequested: fn.refreshLogs(fn.effectiveLogMode)
                    onUndoDeleteRequested: function(name) {
                        fn.undoDeletion(name);
                    }
                    onRenameRequested: function(name) {
                        fn.targetActionLog = name;
                        logDialogs.openRename(name);
                    }
                    onDeleteRequested: function(name) {
                        fn.targetActionLog = name;
                        logDialogs.openDeleteConfirm();
                    }
                }

                Kirigami.Separator {
                    Layout.fillHeight: true
                }

                // pass functions to helper
                LogActionsPanel {
                    selectedLogName: fn.selectedLogName
                    effectiveLogMode: fn.effectiveLogMode
                    isSelectedMarkedDeleted: fn.selectedLogName !== "" && fn.isMarkedForDeletion(fn.selectedLogName)
                    onShowInBrowserRequested: {
                        if (typeof backend !== "undefined" && backend !== null && backend.show_in_file_browser !== undefined)
                            backend.show_in_file_browser(fn.selectedLogName);

                    }
                    onLoadLogRequested: fn.loadSelectedLog()
                    onDeleteLogRequested: {
                        fn.targetActionLog = fn.selectedLogName;
                        logDialogs.openDeleteConfirm();
                    }
                    onUndoDeleteRequested: fn.undoDeletion(fn.selectedLogName)
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
                text: "Not connected. Connect to the server to retrieve remote log files."
                actions: [
                    Kirigami.Action {
                        text: "Connect"
                        icon.name: "network-connect"
                        onTriggered: {
                            if (typeof backend !== "undefined" && backend !== null && backend.connect !== undefined)
                                backend.connect();

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

    // 3. Log-related dialogs
    LogDialogs {
        id: logDialogs

        targetActionLog: fn.targetActionLog
        onRenameConfirmed: function(newName) {
            let next = Object.assign({
            }, fn.renamedLogsMap);
            next[fn.logKey(fn.effectiveLogMode, fn.targetActionLog)] = newName;
            fn.renamedLogsMap = next;
            if (fn.selectedLogName === fn.targetActionLog)
                fn.selectedLogName = newName;

            if (typeof backend !== "undefined" && backend !== null && backend.rename_log !== undefined)
                backend.rename_log(fn.effectiveLogMode, fn.targetActionLog, newName);

        }
        onDeleteConfirmed: {
            fn.markForDeletion(fn.targetActionLog);
        }
    }

}
