import QtCore as Core
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtWebSockets
import org.kde.kirigami as Kirigami
import "pages"

// main application window hosting the shared WebSocket, global toolbar, sidebar drawer, and page stack
Kirigami.ApplicationWindow {
    id: root

    readonly property var actuatorsPage: actuatorsPageLoader.item ?? actuatorsPageLoader
    readonly property var graphsPage: graphsPageLoader.item ?? graphsPageLoader
    readonly property var videoPage: videoPageLoader.item ?? videoPageLoader
    // Central WebSocket connection shared by all views and components
    property alias webSocket: sharedWebSocket
    property bool userDisconnected: false

    function sendTextMessage(message) {
        if (sharedWebSocket && sharedWebSocket.status === WebSocket.Open)
            sharedWebSocket.sendTextMessage(message);

    }

    function sendJson(data) {
        sendTextMessage(JSON.stringify(data));
    }

    minimumHeight: Kirigami.Units.gridUnit * 34
    minimumWidth: Kirigami.Units.gridUnit * 45
    title: "Flow Control System"
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    pageStack.globalToolBar.showNavigationButtons: Kirigami.ApplicationHeaderStyle.NoNavigationButtons

    Core.Settings {
        id: appSettings

        property string minLogLevel: "INFO"
    }

    WebSocket {
        id: sharedWebSocket

        url: backend ? backend.server_url : "ws://127.0.0.1:8080/ws"
        active: false
        onStatusChanged: function(status) {
            if (typeof backend !== "undefined" && backend && typeof backend.on_ws_connected_changed === "function")
                backend.on_ws_connected_changed(status === WebSocket.Open);

        }
        onTextMessageReceived: function(message) {
            if (typeof backend !== "undefined" && backend && typeof backend.ingest_ws_message === "function")
                backend.ingest_ws_message(message);

        }
    }

    // Set the first page that will be loaded when the app opens
    // only use one main page to keep toolbar consistent
    pageStack.initialPage: Kirigami.Page {
        title: "Controls"
        actions: [
            Kirigami.Action {
                text: "Record data"

                displayComponent: Controls.ToolButton {
                    id: recordBtn

                    property bool isRecording: backend ? backend.recording : false

                    checkable: true
                    checked: isRecording
                    highlighted: isRecording
                    padding: Kirigami.Units.smallSpacing
                    leftPadding: Kirigami.Units.mediumSpacing
                    rightPadding: Kirigami.Units.mediumSpacing
                    onClicked: {
                        if (backend)
                            recordBtn.isRecording = backend.toggle_recording();

                    }

                    Connections {
                        function onRecording_changed(active: bool) {
                            recordBtn.isRecording = active;
                        }

                        target: backend
                    }

                    contentItem: RowLayout {
                        spacing: Kirigami.Units.smallSpacing

                        Kirigami.Icon {
                            source: "keyframe-record"
                            implicitWidth: Kirigami.Units.iconSizes.small
                            implicitHeight: Kirigami.Units.iconSizes.small
                            color: recordBtn.isRecording ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
                        }

                        Controls.Label {
                            text: recordBtn.isRecording ? "Recording..." : "Record data"
                            font.bold: recordBtn.isRecording
                            color: recordBtn.isRecording ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
                        }

                    }

                }

            },
            Kirigami.Action {
                text: "Connection"

                displayComponent: RowLayout {
                    spacing: Kirigami.Units.smallSpacing

                    Rectangle {
                        id: armedBadge

                        readonly property bool armed: backend ? backend.armed : false
                        readonly property color statusColor: armed ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.positiveTextColor

                        visible: sharedWebSocket.status === WebSocket.Open
                        Layout.preferredWidth: armedRow.implicitWidth + Kirigami.Units.largeSpacing
                        Layout.preferredHeight: armedRow.implicitHeight + Kirigami.Units.smallSpacing
                        radius: 4
                        color: Qt.rgba(statusColor.r, statusColor.g, statusColor.b, 0.15)
                        border.width: 1
                        border.color: statusColor

                        RowLayout {
                            id: armedRow

                            anchors.centerIn: parent
                            spacing: Kirigami.Units.smallSpacing

                            Rectangle {
                                Layout.preferredWidth: 8
                                Layout.preferredHeight: 8
                                radius: 4
                                color: armedBadge.statusColor
                            }

                            Controls.Label {
                                text: armedBadge.armed ? "SYSTEM ARMED" : "SYSTEM SAFE"
                                font.bold: true
                                color: armedBadge.statusColor
                            }

                        }

                    }

                    Websocket {
                        compact: true
                        Layout.rightMargin: Kirigami.Units.gridUnit / 2
                    }

                }

            }
        ]

        Item {
            anchors.fill: parent

            StackLayout {
                id: contentStack

                anchors.fill: parent
                currentIndex: 0

                // 0
                Dashboard {
                    id: dashboardPage
                }

                // 1
                Loader {
                    id: actuatorsPageLoader

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    asynchronous: true
                    active: false

                    sourceComponent: Actuators {
                        id: actuatorsPage

                        keybindsEnabled: sidebarNav.keybindsEnabled
                        isWebsocketConnected: sharedWebSocket.status === WebSocket.Open
                    }

                }

                // 2
                Loader {
                    id: graphsPageLoader

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    asynchronous: true
                    active: false

                    sourceComponent: Graphs {
                        id: graphsPage

                        windowSeconds: sidebarNav.effectiveWindowSeconds
                        global3StdFilter: sidebarNav.smoothAllActive
                        editLayoutMode: sidebarNav.editLayoutActive
                        dataSourceMode: dashboardPage.dataSourceMode
                    }

                }

                // 3
                Loader {
                    id: videoPageLoader

                    Layout.fillWidth: true
                    Layout.fillHeight: true
                    asynchronous: true
                    active: false

                    sourceComponent: Video {
                        id: videoPage
                    }

                }

            }

            Timer {
                id: warmupTimer

                interval: 400
                running: true
                repeat: false
                onTriggered: {
                    graphsPageLoader.active = true;
                    actuatorsPageLoader.active = true;
                    videoPageLoader.active = true;
                }
            }

            // Overlay toast container anchored at bottom-right, floating over page content
            LogToaster {
                id: logToaster

                objectName: "logToaster"
                anchors.bottom: parent.bottom
                anchors.right: parent.right
                anchors.margins: Kirigami.Units.gridUnit
                width: Math.min(parent.width - (Kirigami.Units.gridUnit * 2), Kirigami.Units.gridUnit * 22)
                z: 999
                minSeverity: appSettings.minLogLevel
            }

        }

        ListModel {
            id: notificationModel

            property int unreadCount: 0

            objectName: "notificationModel"
        }

        NotificationTray {
            id: notificationTray

            objectName: "notificationTray"
            notifModel: notificationModel
            onClearRequested: {
                notificationModel.clear();
                notificationModel.unreadCount = 0;
            }
            onVisibleChanged: {
                if (visible)
                    notificationModel.unreadCount = 0;

            }
        }

        Settings {
            id: settingsDialog

            minLogLevel: appSettings.minLogLevel
            onMinLogLevelUpdated: function(level) {
                appSettings.minLogLevel = level;
            }
            onAutoConnectToggled: function(enabled) {
                if (enabled) {
                    root.userDisconnected = false;
                    if (sharedWebSocket.status !== WebSocket.Open && sharedWebSocket.status !== WebSocket.Connecting) {
                        sharedWebSocket.active = false;
                        sharedWebSocket.active = true;
                    }
                }
            }
        }

        Kirigami.PromptDialog {
            id: abortConfirmDialog

            title: "Confirm Emergency Abort"
            subtitle: "Execute EMERGENCY ABORT? All fill valves will close and dump/vent valves will open."
            standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
            onAccepted: {
                if (backend)
                    backend.abort();

            }
        }

        Kirigami.PromptDialog {
            id: serverRecordingDialog

            property string recordingFilename: ""

            title: "Server Recording In Progress"
            subtitle: "The server is currently recording telemetry" + (recordingFilename ? " (\"" + recordingFilename + "\")" : "") + ".\nWould you like to pull the current recorded state into your live session, or wait for recording to stop while logging incoming data in memory?"
            standardButtons: Kirigami.Dialog.NoButton
            customFooterActions: [
                Kirigami.Action {
                    text: "Pull Recorded State"
                    icon.name: "download"
                    onTriggered: {
                        if (backend)
                            backend.pull_server_recording_state(serverRecordingDialog.recordingFilename);

                        serverRecordingDialog.close();
                    }
                },
                Kirigami.Action {
                    text: "Wait & Log in Memory"
                    icon.name: "chronometer"
                    onTriggered: {
                        if (backend)
                            backend.log_info("Waiting for server recording to finish; logging live telemetry in memory.");

                        serverRecordingDialog.close();
                    }
                }
            ]
        }

        Connections {
            function onLog_sent(level: string, msg: string) {
                let now = new Date();
                let h = String(now.getHours()).padStart(2, "0");
                let m = String(now.getMinutes()).padStart(2, "0");
                let s = String(now.getSeconds()).padStart(2, "0");
                let timeStr = h + ":" + m + ":" + s;
                // 1. Record in notification tray model
                notificationModel.insert(0, {
                    "level": level,
                    "message": msg,
                    "timestamp": timeStr,
                    "read": false
                });
                notificationModel.unreadCount++;
                // 2. Display overlay toast
                logToaster.showToast(level, msg);
            }

            function onWs_send_requested(payload: string) {
                root.sendTextMessage(payload);
            }

            function onServer_recording_active_on_connect(filename: string) {
                serverRecordingDialog.recordingFilename = filename || "";
                serverRecordingDialog.open();
            }

            target: backend
        }

    }

    globalDrawer: Kirigami.GlobalDrawer {
        id: globalDrawer

        modal: false
        collapsible: false
        collapsed: false
        // Remove internal drawer padding around the header so the toolbar touches the top/edges
        topPadding: 0
        leftPadding: 0
        rightPadding: 0

        Sidebar {
            id: sidebarNav

            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: Kirigami.Units.gridUnit / 4
            unreadNotificationCount: notificationModel.unreadCount
            // track all currently visible views so view helpers work for both single StackLayout and side-by-side multi-page layouts
            visiblePages: {
                var pages = [];
                if (dashboardPage.visible)
                    pages.push("dashboard");

                if (actuatorsPage.visible)
                    pages.push("actuators");

                if (graphsPage.visible)
                    pages.push("graphs");

                if (videoPage.visible)
                    pages.push("video");

                return pages;
            }
            onNavigateRequested: function(pageName) {
                if (pageName === "dashboard") {
                    contentStack.currentIndex = 0;
                } else if (pageName === "actuators") {
                    actuatorsPageLoader.active = true;
                    contentStack.currentIndex = 1;
                } else if (pageName === "graphs") {
                    graphsPageLoader.active = true;
                    contentStack.currentIndex = 2;
                } else if (pageName === "video") {
                    videoPageLoader.active = true;
                    contentStack.currentIndex = 3;
                }
            }
            onSettingsRequested: {
                settingsDialog.open();
            }
            onNotificationsRequested: {
                notificationTray.open();
                notificationModel.unreadCount = 0;
            }
            onAbortRequested: {
                abortConfirmDialog.open();
            }
        }

        // Match the exact color set, background, border, and height of the Page ToolBar
        header: Controls.ToolBar {
            Layout.fillWidth: true
            implicitHeight: root.pageStack.globalToolBar.preferredHeight
            Kirigami.Theme.colorSet: Kirigami.Theme.Header
            Kirigami.Theme.inherit: false

            contentItem: RowLayout {
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Heading {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.largeSpacing
                    text: "Control Panel"
                    level: 1
                    elide: Text.ElideRight
                }

            }

        }

    }

}
