import QtCore
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtWebSockets
import org.kde.kirigami as Kirigami
import "pages"

Kirigami.ApplicationWindow {
    id: root

    // Central WebSocket connection shared by all views and components
    property alias webSocket: sharedWebSocket
    property bool userDisconnected: false

    signal webSocketMessageReceived(var data)

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

    Settings {
        id: appSettings

        property string minLogLevel: "INFO"
    }

    WebSocket {
        id: sharedWebSocket

        url: backend ? backend.server_url : "ws://127.0.0.1:8080/ws"
        active: false
        onTextMessageReceived: function(message) {
            if (typeof backend !== "undefined" && backend && typeof backend.ingest_ws_message === "function")
                backend.ingest_ws_message(message);

            try {
                let data = JSON.parse(message);
                root.webSocketMessageReceived(data);
            } catch (e) {
            }
        }
    }

    // Set the first page that will be loaded when the app opens
    // only use one main page to keep toolbar consistent
    pageStack.initialPage: Kirigami.Page {
        title: "Controls"
        actions: [
            Kirigami.Action {

                displayComponent: RowLayout {
                    Controls.Label {
                        text: "Auto-connect"
                    }

                    Controls.CheckBox {
                        checked: backend ? backend.auto_reconnect : false
                        onToggled: {
                            if (backend)
                                backend.auto_reconnect = checked;

                            if (checked) {
                                root.userDisconnected = false;
                                if (sharedWebSocket.status !== WebSocket.Open && sharedWebSocket.status !== WebSocket.Connecting) {
                                    sharedWebSocket.active = false;
                                    sharedWebSocket.active = true;
                                }
                            }
                        }
                    }

                }

            },
            Kirigami.Action {
                text: "Record data"
                icon.name: "keyframe-record"
            },
            Kirigami.Action {
                text: "Connection"

                displayComponent: Websocket {
                    compact: true
                    Layout.rightMargin: Kirigami.Units.gridUnit / 2
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
                Actuators {
                    id: actuatorsPage
                }

                // 2
                Graphs {
                    id: graphsPage

                    windowSeconds: sidebarNav.effectiveWindowSeconds
                    global3StdFilter: sidebarNav.smoothAllActive
                    editLayoutMode: sidebarNav.editLayoutActive
                    dataSourceMode: dashboardPage.dataSourceMode
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

        Kirigami.PromptDialog {
            id: settingsDialog

            title: "Settings"
            subtitle: "Application configuration and settings will be available here."
            standardButtons: Kirigami.Dialog.Close
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

                return pages;
            }
            onNavigateRequested: function(pageName) {
                if (pageName === "dashboard")
                    contentStack.currentIndex = 0;
                else if (pageName === "actuators")
                    contentStack.currentIndex = 1;
                else if (pageName === "graphs")
                    contentStack.currentIndex = 2;
            }
            onSettingsRequested: {
                settingsDialog.open();
            }
            onNotificationsRequested: {
                notificationTray.open();
                notificationModel.unreadCount = 0;
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
