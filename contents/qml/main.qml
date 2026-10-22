import QtCore
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtWebSockets
import org.kde.kirigami as Kirigami
import "pages"

Kirigami.ApplicationWindow {
    // signal log_sent(var type, var msg)

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
                text: "Connection"

                displayComponent: Websocket {
                    compact: true
                    Layout.rightMargin: Kirigami.Units.gridUnit / 2
                }

            }
        ]

        ColumnLayout {
            anchors.fill: parent

            StackLayout {
                id: contentStack

                Layout.fillHeight: true
                Layout.fillWidth: true
                currentIndex: 0

                // 0
                Dashboard {
                }

                // 1
                Actuators {
                }

                // 2
                Graphs {
                }

            }

            LogToaster {
                id: logToaster

                Layout.fillWidth: true
                minSeverity: appSettings.minLogLevel
            }

        }

        Connections {
            function onLog_sent(level: string, msg: string) {
                logToaster.appendLog(level, msg);
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
            Layout.margins: Kirigami.Units.gridUnit / 4
            onNavigateRequested: function(pageName) {
                if (pageName === "dashboard")
                    contentStack.currentIndex = 0;
                else if (pageName === "actuators")
                    contentStack.currentIndex = 1;
                else if (pageName === "graphs")
                    contentStack.currentIndex = 2;
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
