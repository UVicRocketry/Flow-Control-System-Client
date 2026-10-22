import QtQuick
import org.kde.kirigami as Kirigami

// popup for showing logged information
Kirigami.InlineMessage {
    id: root

    property string level: "INFO"
    property string timestamp: ""
    property int totalMs: 0
    property bool timed: false
    property bool showDismissAction: true
    property bool animateEntryExit: true
    readonly property bool isPersistent: !timed || totalMs <= 0 || level === "ERR"
    property int remainingMs: totalMs
    property bool isHovered: hoverHandler.hovered
    property string _pendingCloseReason: ""

    signal dismissed()
    signal timeout()

    function closeWithFade(reason) {
        if (!animateEntryExit) {
            if (reason === "timeout")
                root.timeout();
            else
                root.dismissed();
            return ;
        }
        if (fadeOutAnim.running)
            return ;

        countdownTimer.stop();
        _pendingCloseReason = reason;
        fadeOutAnim.start();
    }

    visible: true
    onTotalMsChanged: remainingMs = totalMs
    opacity: animateEntryExit ? 0 : 1
    Component.onCompleted: {
        remainingMs = totalMs;
        if (animateEntryExit)
            fadeInAnim.start();

    }
    type: {
        switch (level) {
        case "WARN":
            return Kirigami.MessageType.Warning;
        case "ERR":
            return Kirigami.MessageType.Error;
        case "INFO":
        default:
            return Kirigami.MessageType.Information;
        }
    }
    actions: [
        Kirigami.Action {
            visible: root.timestamp.length > 0
            text: root.timestamp
            tooltip: "Received at " + root.timestamp
            enabled: false
        },
        Kirigami.Action {
            visible: root.timed && !root.isPersistent
            text: Math.max(1, Math.ceil(root.remainingMs / 1000)) + "s"
            tooltip: "Time remaining before auto-dismiss"
            enabled: false
        },
        Kirigami.Action {
            visible: root.showDismissAction
            icon.name: "window-close"
            tooltip: "Dismiss"
            onTriggered: root.closeWithFade("dismiss")
        }
    ]

    NumberAnimation {
        id: fadeInAnim

        target: root
        property: "opacity"
        from: 0
        to: 1
        duration: Kirigami.Units.longDuration
        easing.type: Easing.OutCubic
    }

    NumberAnimation {
        id: fadeOutAnim

        target: root
        property: "opacity"
        to: 0
        duration: Kirigami.Units.shortDuration
        easing.type: Easing.InCubic
        onFinished: {
            if (root._pendingCloseReason === "timeout")
                root.timeout();
            else
                root.dismissed();
        }
    }

    Timer {
        id: countdownTimer

        interval: 100
        running: root.timed && !root.isPersistent && !root.isHovered && !fadeOutAnim.running
        repeat: true
        onTriggered: {
            root.remainingMs = Math.max(0, root.remainingMs - 100);
            if (root.remainingMs <= 0) {
                countdownTimer.stop();
                root.closeWithFade("timeout");
            }
        }
    }

    HoverHandler {
        id: hoverHandler
    }

    Item {
        id: progressBarContainer

        parent: root.background ? root.background : root
        anchors.bottom: parent.bottom
        anchors.left: parent.left
        anchors.right: parent.right
        anchors.topMargin: 2
        anchors.leftMargin: 2
        anchors.rightMargin: 2
        height: 3
        z: 10
        visible: root.timed && !root.isPersistent

        Rectangle {
            anchors.fill: parent
            color: Qt.alpha(Kirigami.Theme.textColor, 0.15)
            radius: 1.5
        }

        Rectangle {
            id: progressFill

            anchors.left: parent.left
            anchors.top: parent.top
            anchors.bottom: parent.bottom
            width: parent.width * (root.totalMs > 0 ? Math.max(0, Math.min(1, root.remainingMs / root.totalMs)) : 0)
            color: root.level === "WARN" ? Kirigami.Theme.neutralTextColor : Kirigami.Theme.highlightColor
            radius: 1.5

            Behavior on width {
                enabled: countdownTimer.running

                NumberAnimation {
                    duration: countdownTimer.interval
                    easing.type: Easing.Linear
                }

            }

        }

    }

}
