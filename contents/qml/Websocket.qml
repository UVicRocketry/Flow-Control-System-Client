import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtWebSockets
import org.kde.kirigami as Kirigami
import "pages"

// WebSocket connection status indicator, handler and controller
Item {
    id: wsRoot

    // Switch between full single-row UI and topbar compact indicator mode
    property bool compact: false
    readonly property bool hasBackend: typeof backend !== "undefined" && backend !== null
    readonly property WebSocket socket: root.webSocket
    readonly property string wsMode: hasBackend ? backend.server_mode : "auto"
    readonly property bool isAutoMode: wsMode !== "manual"
    // Track previous state so we don't spam identical auto-reconnect errors every 2s
    property bool _wasConnected: false
    property bool _timedOut: false
    property string _lastLoggedError: ""
    // Connection state convenience properties
    readonly property bool isConnected: socket ? (socket.status === WebSocket.Open) : false
    readonly property bool isConnecting: socket ? (socket.status === WebSocket.Connecting) : false
    readonly property bool isError: socket ? (socket.status === WebSocket.Error) : false
    readonly property string errorString: socket ? socket.errorString : ""
    // Server URL
    property string currentUrl: socket && socket.url && socket.url.toString().length > 0 ? socket.url.toString() : (hasBackend ? backend.server_url : "ws://127.0.0.1:8080/ws")
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

    // Methods
    // main websocket connector - can pass either a new URL or leave blank to use current
    function connectSocket(targetUrl) {
        if (!socket)
            return ;

        if (typeof root !== "undefined" && root && root.hasOwnProperty("userDisconnected"))
            root.userDisconnected = false;

        // Reset error deduplication when user manually initiates a connection
        wsRoot._lastLoggedError = "";
        var urlToUse;
        if (wsRoot.isAutoMode && wsRoot.hasBackend) {
            urlToUse = backend.refresh_server_url();
        } else {
            urlToUse = (targetUrl && targetUrl.trim().length > 0) ? targetUrl.trim() : wsRoot.currentUrl;
            urlToUse = urlToUse.trim();
            if (wsRoot.hasBackend && urlToUse.length > 0 && urlToUse !== backend.server_url)
                backend.server_url = urlToUse;

        }
        wsRoot.currentUrl = urlToUse;
        socket.url = urlToUse;
        if (socket.active)
            socket.active = false;

        socket.active = true;
    }

    function toggleMode(manualText) {
        if (!wsRoot.hasBackend)
            return ;

        if (!wsRoot.isAutoMode && manualText && manualText.trim().length > 0)
            backend.set_server_manual_url(manualText.trim());

        var nextMode = wsRoot.isAutoMode ? "manual" : "auto";
        backend.set_server_mode(nextMode);
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

    Component.onCompleted: {
        if (compact && backend && backend.auto_reconnect && socket && !socket.active) {
            var startUrl = wsRoot.isAutoMode ? backend.refresh_server_url() : socket.url.toString();
            wsRoot.currentUrl = startUrl;
            socket.url = startUrl;
            if (backend.is_ws_reachable(startUrl)) {
                backend.info("Auto-connecting to WebSocket at " + socket.url);
                socket.active = true;
            }
        }
    }
    implicitWidth: compact ? indicatorBtn.implicitWidth : fullRowLoader.implicitWidth
    implicitHeight: compact ? indicatorBtn.implicitHeight : fullRowLoader.implicitHeight

    // Abort stalled connection attempts after 5 seconds (driven by the single compact instance)
    Timer {
        id: connectTimeoutTimer

        interval: 5000
        repeat: false
        running: wsRoot.compact && wsRoot.isConnecting
        onTriggered: {
            if (wsRoot.socket && wsRoot.isConnecting) {
                var target = wsRoot.socket.url;
                wsRoot._timedOut = true;
                wsRoot.socket.active = false;
                var fullErr = "(" + target + "): Connection timed out after 5s";
                if (!wsRoot.hasBackend || !backend.auto_reconnect || fullErr !== wsRoot._lastLoggedError) {
                    wsRoot._lastLoggedError = fullErr;
                    if (wsRoot.hasBackend)
                        backend.err(fullErr);

                }
            }
        }
    }

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
            var nextUrl = socket.url.toString();
            if (wsRoot.isAutoMode && wsRoot.hasBackend) {
                nextUrl = backend.refresh_server_url();
                wsRoot.currentUrl = nextUrl;
            }
            if (wsRoot.hasBackend && !backend.is_ws_reachable(nextUrl))
                return ;

            socket.url = nextUrl;
            if (socket.active)
                socket.active = false;

            socket.active = true;
        }
    }

    Connections {
        function onConnect_requested() {
            if (compact && backend && backend.auto_reconnect && socket && !socket.active) {
                var nextUrl = wsRoot.isAutoMode ? backend.refresh_server_url() : socket.url.toString();
                wsRoot.currentUrl = nextUrl;
                socket.url = nextUrl;
                if (backend.is_ws_reachable(nextUrl)) {
                    backend.info("Activating WebSocket connection to " + socket.url);
                    socket.active = true;
                }
            }
        }

        function onServer_url_changed(newUrl) {
            wsRoot.currentUrl = newUrl;
            if (wsRoot.compact && wsRoot.socket && !wsRoot.isConnected && !wsRoot.isConnecting)
                wsRoot.socket.url = newUrl;

        }

        target: backend
    }

    Connections {
        function onStatusChanged(status) {
            // Only log from the single compact toolbar instance so events aren't duplicated
            if (!compact)
                return ;

            if (status === WebSocket.Connecting) {
                wsRoot._timedOut = false;
            } else if (status === WebSocket.Open) {
                wsRoot._timedOut = false;
                wsRoot._wasConnected = true;
                wsRoot._lastLoggedError = "";
                backend.info("WebSocket connected to " + wsRoot.socket.url);
            } else if (status === WebSocket.Error) {
                if (wsRoot._timedOut)
                    return ;

                let errDetail = wsRoot.socket.errorString && wsRoot.socket.errorString.length > 0 ? wsRoot.socket.errorString : "Connection failed";
                let fullErr = "(" + wsRoot.socket.url + "): " + errDetail;
                // Avoid flooding the global log if auto-reconnect is retrying the same dead endpoint
                if (fullErr !== wsRoot._lastLoggedError) {
                    wsRoot._lastLoggedError = fullErr;
                    backend.err(fullErr);
                }
            } else if (status === WebSocket.Closed) {
                if (wsRoot._wasConnected) {
                    wsRoot._wasConnected = false;
                    if (typeof root !== "undefined" && root && root.userDisconnected)
                        backend.info("WebSocket disconnected from " + wsRoot.socket.url);
                    else
                        backend.warn("WebSocket connection closed (" + wsRoot.socket.url + ")");
                }
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

            // status badge (shown in full view; hidden in compact popup)
            Rectangle {
                id: statusBadge

                visible: !wsRoot.compact
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

                    StatusDot {
                        color: wsRoot.statusColor
                        pulsing: wsRoot.isConnecting
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

            // mode toggle button (replaces status badge in compact popup; sits to its right in full view)
            IconToolButton {
                id: modeButton

                Layout.preferredHeight: Kirigami.Units.gridUnit * 1.8
                flat: false
                iconName: ""
                labelText: wsRoot.isAutoMode ? "&Mode: Auto" : "&Mode: Manual"
                toolTipText: "Toggle Auto / Manual WebSocket URL mode"
                mirrorMnemonic: wsRoot.compact
                onClicked: {
                    wsRoot.toggleMode(urlInput.text);
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
                enabled: !wsRoot.isAutoMode && !wsRoot.isConnected && !wsRoot.isConnecting
                opacity: wsRoot.isAutoMode ? 0.5 : 1
                color: enabled ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor
                onAccepted: {
                    if (!wsRoot.isAutoMode)
                        wsRoot.connectSocket(text);

                }
                onTextChanged: {
                    if (!wsRoot.isAutoMode && activeFocus)
                        wsRoot.currentUrl = text;

                }
                leftPadding: Kirigami.Units.mediumSpacing

                Connections {
                    function onCurrentUrlChanged() {
                        if ((!urlInput.activeFocus || wsRoot.isAutoMode) && urlInput.text !== wsRoot.currentUrl)
                            urlInput.text = wsRoot.currentUrl;

                    }

                    target: wsRoot
                }

            }

            // 3. Connect / Disconnect
            IconToolButton {
                id: actionButton

                Layout.preferredHeight: Kirigami.Units.gridUnit * 1.8
                flat: false
                labelText: wsRoot.isConnected ? "Dis&connect" : (wsRoot.isConnecting ? "Connecting" : "&Connect")
                iconName: wsRoot.isConnected ? "network-disconnect" : "network-connect"
                highlighted: !wsRoot.isConnected && !wsRoot.isConnecting
                enabled: !wsRoot.isConnecting
                mirrorMnemonic: wsRoot.compact
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
                    active: topbarPopup.visible
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

            StatusDot {
                color: wsRoot.statusColor
                pulsing: wsRoot.isConnecting
            }

            Controls.Label {
                text: wsRoot.statusLabelShort
                font.pixelSize: 12
                color: wsRoot.statusColor
            }

            BundledIcon {
                iconName: "arrow-down"
                iconSize: Math.round(Kirigami.Units.iconSizes.small / 1.6)
                opacity: 0.6
            }

        }

    }

}
