import QtMultimedia
import QtQuick
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

    function toggleStream() {
        if (isActive) {
            _userStopped = true;
            _wasStreaming = false;
            connectTimeoutTimer.stop();
            player.stop();
            player.source = "";
            if (hasBackend)
                backend.info("Camera stream disconnected.");

        } else if (hasBackend) {
            _userStopped = false;
            _wasStreaming = false;
            player.source = backend.camera_rtsp_url;
            player.play();
            connectTimeoutTimer.restart();
        }
    }

    onIsActiveChanged: {
        if (hasBackend)
            backend.set_camera_active(isActive);

    }
    Layout.fillWidth: true
    Layout.fillHeight: true

    Connections {
        function onCamera_toggle_requested() {
            videoRoot.toggleStream();
        }

        function onCamera_config_changed() {
            if (videoRoot.isActive && videoRoot.hasBackend) {
                videoRoot._userStopped = false;
                videoRoot._wasStreaming = false;
                player.stop();
                player.source = backend.camera_rtsp_url;
                player.play();
                connectTimeoutTimer.restart();
            }
        }

        target: videoRoot.hasBackend ? backend : null
    }

    Timer {
        id: connectTimeoutTimer

        interval: 8000
        repeat: false
        onTriggered: {
            if (videoRoot.isConnecting && !videoRoot._wasStreaming) {
                videoRoot._userStopped = true;
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
        playbackOptions.playbackIntent: QPlaybackOptions.LowLatencyStreaming
        onErrorOccurred: function(error, errorString) {
            connectTimeoutTimer.stop();
            videoRoot._wasStreaming = false;
            if (videoRoot.hasBackend && error !== MediaPlayer.NoError) {
                let clean = (errorString || "Connection failed").replace(/(:\/\/[^:/@\s]+:)([^@\s]+)(@)/, "$1***$3");
                backend.err("Camera stream error: " + clean);
            }
        }
        onMediaStatusChanged: function(status) {
            if (status === MediaPlayer.BufferedMedia || status === MediaPlayer.LoadedMedia) {
                connectTimeoutTimer.stop();
                if (!videoRoot._wasStreaming && videoRoot.hasBackend) {
                    videoRoot._wasStreaming = true;
                    backend.info("Camera stream connected.");
                }
            } else if (status === MediaPlayer.StalledMedia) {
                if (videoRoot.hasBackend)
                    backend.warn("Camera stream stalled.");

            } else if (status === MediaPlayer.EndOfMedia) {
                connectTimeoutTimer.stop();
                if (!videoRoot._userStopped && videoRoot.hasBackend)
                    backend.warn("Camera stream disconnected (end of stream).");

                videoRoot._wasStreaming = false;
            }
        }
        onPlaybackStateChanged: function(state) {
            if (state === MediaPlayer.StoppedState) {
                connectTimeoutTimer.stop();
                if (videoRoot._wasStreaming && !videoRoot._userStopped && !videoRoot.hasError && videoRoot.hasBackend)
                    backend.warn("Camera stream disconnected unexpectedly.");

                videoRoot._wasStreaming = false;
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

                helpfulAction: Kirigami.Action {
                    text: videoRoot.isConnecting ? "Disconnect" : "Connect"
                    icon.name: videoRoot.isConnecting ? "network-disconnect" : "network-connect"
                    onTriggered: videoRoot.toggleStream()
                }

            }

        }

    }

}
