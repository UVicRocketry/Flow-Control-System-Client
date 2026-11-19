import QtMultimedia
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: videoRoot

    readonly property bool hasBackend: typeof backend !== "undefined" && backend !== null
    readonly property bool isPlaying: player.playbackState === MediaPlayer.PlayingState
    readonly property bool isConnecting: player.mediaStatus === MediaPlayer.LoadingMedia || player.mediaStatus === MediaPlayer.BufferingMedia
    readonly property bool isActive: isPlaying || isConnecting
    readonly property bool hasError: player.error !== MediaPlayer.NoError
    property bool _userStopped: false
    property bool _wasStreaming: false
    property bool _isReconfiguring: false

    function startStream() {
        if (!hasBackend)
            return ;

        _userStopped = false;
        player.source = backend.camera_rtsp_url;
        player.play();
        connectTimeoutTimer.restart();
    }

    function toggleStream() {
        if (isActive || reconnectTimer.running) {
            _userStopped = true;
            _isReconfiguring = false;
            reconnectTimer.stop();
            connectTimeoutTimer.stop();
            player.stop();
            player.source = "";
            _wasStreaming = false;
            if (hasBackend)
                backend.info("Camera stream disconnected.");

        } else {
            _wasStreaming = false;
            _isReconfiguring = false;
            startStream();
        }
    }

    Component.onCompleted: {
        if (hasBackend)
            backend.configure_camera_player(player);

    }
    onIsActiveChanged: {
        if (hasBackend)
            backend.set_camera_active(isActive || reconnectTimer.running);

    }
    Layout.fillWidth: true
    Layout.fillHeight: true

    Connections {
        function onCamera_toggle_requested() {
            videoRoot.toggleStream();
        }

        function onCamera_config_changed() {
            if ((videoRoot.isActive || reconnectTimer.running) && videoRoot.hasBackend) {
                videoRoot._userStopped = true;
                videoRoot._isReconfiguring = videoRoot._wasStreaming;
                connectTimeoutTimer.stop();
                player.stop();
                player.source = "";
                reconnectTimer.restart();
            }
        }

        target: videoRoot.hasBackend ? backend : null
    }

    Timer {
        id: reconnectTimer

        interval: 120
        repeat: false
        onTriggered: videoRoot.startStream()
    }

    Timer {
        id: connectTimeoutTimer

        interval: 8000
        repeat: false
        onTriggered: {
            if (videoRoot.isConnecting && !videoRoot._wasStreaming) {
                videoRoot._userStopped = true;
                videoRoot._isReconfiguring = false;
                player.stop();
                player.source = "";
                if (videoRoot.hasBackend)
                    backend.err("Camera connection timed out.");

            }
        }
    }

    MediaPlayer {
        id: player

        videoOutput: videoOut
        onErrorOccurred: function(error, errorString) {
            connectTimeoutTimer.stop();
            videoRoot._wasStreaming = false;
            videoRoot._isReconfiguring = false;
            if (videoRoot.hasBackend && error !== MediaPlayer.NoError) {
                let clean = (errorString || "Connection failed").replace(/(:\/\/[^:/@\s]+:)([^@\s]+)(@)/, "$1***$3");
                backend.err("Camera stream error: " + clean);
            }
        }
        onMediaStatusChanged: function(status) {
            if (status === MediaPlayer.BufferedMedia && !videoRoot._userStopped) {
                connectTimeoutTimer.stop();
                if (!videoRoot._wasStreaming && !videoRoot._isReconfiguring && videoRoot.hasBackend)
                    backend.info("Camera stream connected.");

                videoRoot._wasStreaming = true;
                videoRoot._isReconfiguring = false;
            } else if (status === MediaPlayer.StalledMedia && !videoRoot._userStopped) {
                if (videoRoot.hasBackend)
                    backend.warn("Camera stream stalled.");

            } else if (status === MediaPlayer.EndOfMedia) {
                connectTimeoutTimer.stop();
                if (!videoRoot._userStopped && videoRoot.hasBackend)
                    backend.warn("Camera stream disconnected (end of stream).");

                videoRoot._wasStreaming = false;
                videoRoot._isReconfiguring = false;
            }
        }
        onPlaybackStateChanged: function(state) {
            if (state === MediaPlayer.StoppedState) {
                connectTimeoutTimer.stop();
                if (videoRoot._wasStreaming && !videoRoot._userStopped && !videoRoot.hasError && videoRoot.hasBackend) {
                    backend.warn("Camera stream disconnected unexpectedly.");
                    videoRoot._wasStreaming = false;
                }
            }
        }
    }

    Kirigami.Card {
        Layout.fillWidth: true
        Layout.fillHeight: true

        contentItem: Item {
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            Rectangle {
                anchors.fill: parent
                radius: 4
                color: "#111317"
                visible: videoRoot.isPlaying
            }

            VideoOutput {
                id: videoOut

                anchors.fill: parent
                fillMode: VideoOutput.PreserveAspectFit
                visible: videoRoot.isPlaying
            }

            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                visible: !videoRoot.isPlaying
                width: Math.min(parent.width - (Kirigami.Units.largeSpacing * 2), Kirigami.Units.gridUnit * 24)
                icon.name: "camera-video"
                text: videoRoot.hasError ? "Camera Stream Error" : (videoRoot.isConnecting ? "Connecting..." : "IP Camera Feed")
                explanation: videoRoot.hasError ? player.errorString : "Hardware-decoded H.264 stream (configure IP & credentials in Settings)"

                Controls.Button {
                    id: placeholderConnectBtn

                    Layout.alignment: Qt.AlignHCenter
                    Layout.topMargin: Kirigami.Units.gridUnit
                    text: videoRoot.isConnecting ? "Disconnect" : "Connect"
                    icon.name: videoRoot.isConnecting ? "network-disconnect" : "network-connect"
                    Kirigami.MnemonicData.enabled: false
                    onClicked: videoRoot.toggleStream()
                    Component.onCompleted: {
                        if (background && ("text" in background))
                            background.text = Qt.binding(function() {
                                return placeholderConnectBtn.Kirigami.MnemonicData.active ? ("&" + placeholderConnectBtn.text) : placeholderConnectBtn.text;
                            });

                    }
                }

            }

        }

    }

}
