import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtWebSockets
import org.kde.kirigami as Kirigami

Item {
    id: wsRoot

    // Switch between full single-row UI and topbar compact indicator mode
    property bool compact: false
    readonly property WebSocket socket: root.webSocket
    // Connection state convenience properties
    readonly property bool isConnected: socket ? (socket.status === WebSocket.Open) : false
    readonly property bool isConnecting: socket ? (socket.status === WebSocket.Connecting) : false
    readonly property bool isError: socket ? (socket.status === WebSocket.Error) : false
    readonly property string errorString: socket ? socket.errorString : ""
    // Server URL
    property string currentUrl: {
        socket && socket.url && socket.url.toString().length > 0 ? socket.url.toString() : (backend ? backend.server_url : "ws://127.0.0.1:8080/ws");
    }
    readonly property color statusColor: {
        if (isConnected)
            return Kirigami.Theme.positiveTextColor;

        if (isConnecting)
            return Kirigami.Theme.neutralTextColor;

        if (isError)
            return Kirigami.Theme.negativeTextColor;

        return Kirigami.Theme.disabledTextColor;
    }
    readonly property string statusText: {
        if (isConnected)
            return "CONNECTED";

        if (isConnecting)
            return "CONNECTING";

        if (isError)
            return "ERROR";

        return "DISCONNECTED";
    }
    readonly property string statusLabelShort: {
        if (isConnected)
            return "Connected";

        if (isConnecting)
            return "Connecting...";

        if (isError)
            return "Error";

        return "Disconnected";
    }

    signal messageReceived(string message)
    signal jsonReceived(var data)

    // Methods
    // main websocket connector - can pass either a new URL or leave blank to use current
    function connectSocket(targetUrl) {
        if (!socket)
            return ;

        if (typeof root !== "undefined" && root && root.hasOwnProperty("userDisconnected"))
            root.userDisconnected = false;

        var urlToUse = (targetUrl && targetUrl.trim().length > 0) ? targetUrl.trim() : wsRoot.currentUrl;
        urlToUse = urlToUse.trim();
        wsRoot.currentUrl = urlToUse;
        if (backend && urlToUse.length > 0 && urlToUse !== backend.serverUrl)
            backend.serverUrl = urlToUse;

        socket.url = urlToUse;
        socket.active = false;
        socket.active = true;
    }

    function disconnectSocket() {
        if (!socket)
            return ;

        if (typeof root !== "undefined" && root && root.hasOwnProperty("userDisconnected"))
            root.userDisconnected = true;

        socket.active = false;
    }

    function toggleConnection(targetUrl) {
        if (isConnected || isConnecting)
            disconnectSocket();
        else
            connectSocket(targetUrl);
    }

    function sendTextMessage(message) {
        if (socket && isConnected)
            socket.sendTextMessage(message);

    }

    function sendJson(object) {
        sendTextMessage(JSON.stringify(object));
    }

    Component.onCompleted: {
        if (compact && backend && backend.auto_reconnect && socket && !socket.active) {
            console.log("[WS] Auto-connecting to " + socket.url);
            socket.active = true;
        }
    }
    implicitWidth: compact ? indicatorBtn.implicitWidth : fullRowLoader.implicitWidth
    implicitHeight: compact ? indicatorBtn.implicitHeight : fullRowLoader.implicitHeight

    // Reconnection and lifecycle timer
    Timer {
        id: autoReconnectTimer

        interval: backend ? backend.reconnect_interval_ms : 2000
        repeat: true
        running: {
            if (!compact)
                return false;

            if (!backend || !backend.auto_reconnect || (typeof root !== "undefined" && root && root.userDisconnected))
                return false;

            return socket && socket.status !== WebSocket.Open && socket.status !== WebSocket.Connecting;
        }
        onTriggered: {
            console.log("[WS] Auto-reconnecting to " + socket.url);
            socket.active = false;
            socket.active = true;
        }
    }

    Connections {
        function on_connect_requested() {
            if (compact && backend && backend.auto_reconnect && socket && !socket.active) {
                console.log("[WS] connectRequested: activating WebSocket");
                socket.active = true;
            }
        }

        target: backend
    }

    Connections {
        function onStatusChanged(status) {
            if (!compact)
                return ;

            if (status === WebSocket.Open)
                console.log("[WS] WebSocket Connected to " + wsRoot.socket.url);
            else if (status === WebSocket.Error)
                console.log("[WS] WebSocket Error: " + wsRoot.socket.errorString);
            else if (status === WebSocket.Closed)
                console.log("[WS] WebSocket Disconnected.");
        }

        function onTextMessageReceived(message) {
            wsRoot.messageReceived(message);
            try {
                let data = JSON.parse(message);
                wsRoot.jsonReceived(data);
            } catch (e) {
                console.log("[WS] Received non-JSON message: " + message);
            }
        }

        target: wsRoot.socket
    }

    // status UI
    Component {
        id: fullUiRowComponent

        RowLayout {
            id: rowLayout

            spacing: Kirigami.Units.smallSpacing

            // status badge
            Rectangle {
                id: statusBadge

                Layout.preferredHeight: Kirigami.Units.gridUnit * 1.8
                implicitWidth: badgeInner.implicitWidth + Kirigami.Units.largeSpacing
                radius: 6
                color: Kirigami.Theme.backgroundColor
                border.color: wsRoot.statusColor
                border.width: 1
                Controls.ToolTip.visible: wsRoot.isError && badgeHover.hovered
                Controls.ToolTip.text: wsRoot.errorString.length > 0 ? wsRoot.errorString : "WebSocket connection error"

                RowLayout {
                    id: badgeInner

                    anchors.centerIn: parent
                    spacing: Kirigami.Units.smallSpacing

                    Rectangle {
                        implicitWidth: 8
                        implicitHeight: 8
                        radius: 4
                        color: wsRoot.statusColor

                        SequentialAnimation on opacity {
                            running: wsRoot.isConnecting
                            loops: Animation.Infinite

                            PropertyAnimation {
                                to: 0.25
                                duration: 400
                            }

                            PropertyAnimation {
                                to: 1
                                duration: 400
                            }

                        }

                    }

                    Controls.Label {
                        text: wsRoot.statusText
                        font.bold: true
                        font.pixelSize: 11
                        color: wsRoot.statusColor
                    }

                }

                HoverHandler {
                    id: badgeHover
                }

            }

            // websocket url input field
            Controls.TextField {
                id: urlInput

                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 1.8
                Layout.minimumWidth: Kirigami.Units.gridUnit * 10
                placeholderText: wsRoot.currentUrl
                text: wsRoot.currentUrl
                font.family: "monospace"
                selectByMouse: true
                enabled: !wsRoot.isConnected && !wsRoot.isConnecting
                onAccepted: {
                    wsRoot.connectSocket(text);
                }
                onTextChanged: {
                    if (activeFocus)
                        wsRoot.currentUrl = text;

                }
                leftPadding: Kirigami.Units.mediumSpacing
                topPadding: Kirigami.Units.largeSpacing
            }

            // 3. Connect / Disconnect
            Controls.Button {
                id: actionButton

                Layout.preferredHeight: Kirigami.Units.gridUnit * 1.8
                implicitWidth: Kirigami.Units.iconSizes.medium + text.length * Kirigami.Units.gridUnit / 1.5
                text: wsRoot.isConnected ? "Disconnect" : (wsRoot.isConnecting ? "Connecting" : "Connect")
                icon.name: wsRoot.isConnected ? "network-disconnect" : "network-connect"
                highlighted: !wsRoot.isConnected && !wsRoot.isConnecting
                enabled: !wsRoot.isConnecting
                onClicked: {
                    wsRoot.toggleConnection(urlInput.text);
                }
            }

        }

    }

    Loader {
        id: fullRowLoader

        anchors.fill: parent
        active: !wsRoot.compact
        visible: !wsRoot.compact
        sourceComponent: fullUiRowComponent
    }

    // toolbar view
    Controls.ToolButton {
        id: indicatorBtn

        padding: Kirigami.Units.smallSpacing
        visible: wsRoot.compact
        anchors.fill: parent
        hoverEnabled: true
        onClicked: {
            if (topbarPopup.visible)
                topbarPopup.close();
            else
                topbarPopup.open();
        }

        Controls.Popup {
            id: topbarPopup

            y: parent.height + 6
            x: Math.min(0, parent.width - width)
            width: Math.max(Kirigami.Units.gridUnit * 25, 420)
            padding: Kirigami.Units.largeSpacing
            modal: false
            focus: true
            closePolicy: Controls.Popup.CloseOnEscape | Controls.Popup.CloseOnPressOutsideParent

            background: Rectangle {
                Kirigami.Theme.colorSet: Kirigami.Theme.Tooltip
                // Do not inherit from the parent
                Kirigami.Theme.inherit: false
                color: Kirigami.Theme.backgroundColor
                border.color: Kirigami.Theme.focusColor
                border.width: 1
                radius: 8
            }

            contentItem: ColumnLayout {
                spacing: Kirigami.Units.mediumSpacing

                Kirigami.Heading {
                    text: "Websocket Connection"
                    level: 3
                    Layout.fillWidth: true
                }

                // embed full ui in popup
                Loader {
                    Layout.fillWidth: true
                    sourceComponent: fullUiRowComponent
                }

                // error banner
                Kirigami.InlineMessage {
                    Layout.fillHeight: true
                    Layout.fillWidth: true
                    visible: wsRoot.isError && wsRoot.errorString.length > 0
                    type: Kirigami.MessageType.Error
                    text: wsRoot.errorString
                }

            }

        }

        contentItem: RowLayout {
            spacing: Kirigami.Units.smallSpacing

            // status dot
            Rectangle {
                implicitWidth: 8
                implicitHeight: 8
                radius: 4
                color: wsRoot.statusColor

                SequentialAnimation on opacity {
                    running: wsRoot.isConnecting
                    loops: Animation.Infinite

                    PropertyAnimation {
                        to: 0.25
                        duration: 400
                    }

                    PropertyAnimation {
                        to: 1
                        duration: 400
                    }

                }

            }

            Controls.Label {
                text: wsRoot.statusLabelShort
                font.pixelSize: 12
                color: wsRoot.statusColor
            }

            Kirigami.Icon {
                source: "arrow-down"
                implicitWidth: Kirigami.Units.iconSizes.small / 1.6
                implicitHeight: Kirigami.Units.iconSizes.small / 1.6
                opacity: 0.6
            }

        }

    }

}
