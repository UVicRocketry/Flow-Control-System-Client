import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtWebSockets
import org.kde.kirigami as Kirigami
import "pages"

// main application window hosting the shared WebSocket, global toolbar, sidebar drawer, and page stack
Kirigami.ApplicationWindow {
    id: root

    // Central WebSocket connection shared by all views and components
    property alias webSocket: sharedWebSocket
    property bool userDisconnected: false

    function sendTextMessage(message) {
        if (sharedWebSocket && sharedWebSocket.status === WebSocket.Open)
            sharedWebSocket.sendTextMessage(message);

    }

    minimumHeight: Kirigami.Units.gridUnit * 34
    minimumWidth: Math.max(Kirigami.Units.gridUnit * 45, (root.globalDrawer ? root.globalDrawer.width : 0) + pageHelper.minimumRequiredWidth)
    title: "Flow Control System"
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    pageStack.globalToolBar.showNavigationButtons: Kirigami.ApplicationHeaderStyle.NoNavigationButtons
    onClosing: pageHelper.closeAllPopouts()

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
        padding: 0
        actions: [
            Kirigami.Action {
                text: "Record data"

                displayComponent: IconToolButton {
                    id: recordBtn

                    property bool isRecording: backend ? backend.recording : false
                    property bool serverOnline: sharedWebSocket.status === WebSocket.Open

                    iconName: "keyframe-record"
                    labelText: isRecording ? "&Recording..." : "&Record data"
                    boldText: isRecording
                    textColor: isRecording ? Kirigami.Theme.negativeTextColor : Kirigami.Theme.textColor
                    iconColor: textColor
                    invertOnChecked: false
                    contentOpacity: serverOnline || isRecording ? 1 : 0.5
                    checkable: true
                    checked: isRecording
                    highlighted: isRecording
                    toolTipVisible: hovered && !serverOnline
                    toolTipText: "Server offline — connect to record telemetry"
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

                            StatusDot {
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

            PageHelper {
                id: pageHelper

                anchors.fill: parent
                keybindsEnabled: sidebarNav.keybindsEnabled
                isWebsocketConnected: sharedWebSocket.status === WebSocket.Open
                windowSeconds: sidebarNav.effectiveWindowSeconds
                global3StdFilter: sidebarNav.smoothAllActive
                editLayoutMode: sidebarNav.editLayoutActive
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
                minSeverity: backend ? backend.min_log_level : "INFO"
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

            minLogLevel: backend ? backend.min_log_level : "INFO"
            onMinLogLevelUpdated: function(level) {
                if (backend)
                    backend.set_min_log_level(level);

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
            subtitle: "The server is currently recording telemetry" + (recordingFilename ? " (\"" + recordingFilename + "\")" : "") + ".\nWould you like to pull the current recorded state into your live session, or wait for recording to stop while logging incoming data in memory?" + (recordingFilename && backend && backend.local_data.indexOf(recordingFilename) !== -1 ? "\n\nNote: A local logfile for \"" + recordingFilename + "\" already exists and will be overwritten if you pull." : "")
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

        titleDelegate: RowLayout {
            spacing: Kirigami.Units.smallSpacing

            IconToolButton {
                iconName: "window-new"
                labelText: "Popout &Window"
                enabled: pageHelper.activeInlinePage !== "" && !pageHelper.poppedOutPages[pageHelper.activeInlinePage]
                toolTipText: pageHelper.poppedOutPages[pageHelper.activeInlinePage] ? "Active view is already popped out" : "Pop out active view into a separate window (Alt+Click in sidebar)"
                onClicked: pageHelper.openPageInNewWindow(pageHelper.activeInlinePage)
            }

            IconToolButton {
                iconName: "view-split-left-right"
                labelText: "S&plit View"
                checkable: true
                checked: pageHelper.splitViewActive
                toolTipText: pageHelper.splitViewActive ? "Close split view" : "Open side-by-side split view"
                onClicked: pageHelper.toggleSplitView()
            }

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
            activePageName: pageHelper.activeInlinePage
            unreadNotificationCount: notificationModel.unreadCount
            visiblePages: pageHelper.visiblePages
            onNavigateRequested: function(pageName) {
                pageHelper.navigateInline(pageName);
            }
            onOpenInLeftRequested: function(pageName) {
                pageHelper.openPageInLeftPanel(pageName);
            }
            onOpenInRightRequested: function(pageName) {
                pageHelper.openPageInRightPanel(pageName);
            }
            onOpenInNewWindowRequested: function(pageName) {
                pageHelper.openPageInNewWindow(pageName);
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
