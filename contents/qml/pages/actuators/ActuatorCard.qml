import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Card {
    id: card

    required property var valveDef
    property string currentState: "CLOSED"
    property bool armed: false
    property bool keybindsEnabled: false
    property real baseColumnWidth: Kirigami.Units.gridUnit * 16
    readonly property string valveId: valveDef.id ?? ""
    readonly property string valveLabel: valveDef.label ?? valveId
    readonly property string valveType: valveDef.type ?? "servo"
    readonly property string normalState: valveDef.normal_state ?? "CLOSED"
    readonly property string hintText: valveDef.hint ?? ""
    readonly property string hotkey: valveDef.key ?? ""
    readonly property bool isExternal: Boolean(valveDef.external)
    readonly property bool isSingleUse: Boolean(valveDef.single_use)
    readonly property bool isExpended: isSingleUse && (currentState === "FIRED" || currentState === "DISCONNECTED")
    readonly property bool isInteractive: armed && !isExternal
    readonly property bool canActuate: isInteractive && !isExpended
    readonly property color rawStateColor: {
        if (currentState === "OPEN" || currentState === "FILL" || currentState === "CONNECTED")
            return Kirigami.Theme.positiveTextColor;

        if (currentState === "VENT" || currentState === "ACTUATING")
            return Kirigami.Theme.neutralTextColor;

        if (currentState === "FIRED" || currentState === "DISCONNECTED")
            return Kirigami.Theme.negativeTextColor;

        return Kirigami.Theme.textColor;
    }
    readonly property color stateColor: isInteractive ? rawStateColor : Kirigami.Theme.disabledTextColor
    readonly property string normalBadgeText: {
        if (isExternal)
            return "EXTERNAL";

        if (valveType === "ematch" || valveType === "solenoid_qd")
            return "1-USE";

        return normalState === "OPEN" ? "NO" : "NC";
    }

    signal actuateRequested(string valveId, string action)
    signal confirmRequested(string valveId, string action, string label)

    clip: true
    implicitWidth: baseColumnWidth
    width: baseColumnWidth
    Layout.fillWidth: false
    Layout.preferredWidth: baseColumnWidth
    Layout.minimumWidth: baseColumnWidth
    Layout.maximumWidth: baseColumnWidth
    showClickFeedback: false

    header: RowLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        Rectangle {
            visible: card.hotkey.length > 0
            Layout.preferredWidth: keyLabel.implicitWidth + Kirigami.Units.smallSpacing * 2
            Layout.preferredHeight: keyLabel.implicitHeight + 4
            Layout.alignment: Qt.AlignVCenter
            radius: 4
            color: (card.isInteractive && card.keybindsEnabled) ? Kirigami.Theme.highlightColor : Kirigami.Theme.alternateBackgroundColor
            opacity: (card.isInteractive && card.keybindsEnabled) ? 1 : 0.55

            Controls.Label {
                id: keyLabel

                anchors.centerIn: parent
                text: card.hotkey
                font.bold: true
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: (card.isInteractive && card.keybindsEnabled) ? Kirigami.Theme.highlightedTextColor : Kirigami.Theme.disabledTextColor
            }

        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: 0
            opacity: card.isInteractive ? 1 : 0.55

            Controls.Label {
                Layout.fillWidth: true
                text: card.valveLabel
                font.bold: true
                color: card.isInteractive ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor
                elide: Text.ElideRight
            }

            Controls.Label {
                visible: card.hintText.length > 0
                Layout.fillWidth: true
                text: card.hintText
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: Kirigami.Theme.disabledTextColor
                elide: Text.ElideRight
            }

        }

        Rectangle {
            Layout.preferredWidth: badgeLabel.implicitWidth + Kirigami.Units.smallSpacing * 2
            Layout.preferredHeight: badgeLabel.implicitHeight + 4
            Layout.alignment: Qt.AlignVCenter
            radius: 4
            color: Kirigami.Theme.alternateBackgroundColor
            border.width: 1
            border.color: Kirigami.Theme.disabledTextColor
            opacity: card.isInteractive ? 1 : 0.55

            Controls.Label {
                id: badgeLabel

                anchors.centerIn: parent
                text: card.normalBadgeText
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: Kirigami.Theme.disabledTextColor
            }

        }

    }

    contentItem: Item {
        clip: true
        Layout.fillWidth: true
        implicitHeight: contentCol.implicitHeight
        opacity: card.isInteractive ? 1 : 0.55

        ColumnLayout {
            id: contentCol

            width: parent.width
            spacing: Kirigami.Units.smallSpacing

            // Main state display
            Rectangle {
                Layout.fillWidth: true
                Layout.preferredHeight: Kirigami.Units.gridUnit * 1.8
                radius: 6
                color: Kirigami.Theme.alternateBackgroundColor
                border.width: 1
                border.color: Qt.rgba(card.stateColor.r, card.stateColor.g, card.stateColor.b, 0.45)

                RowLayout {
                    anchors.verticalCenter: parent.verticalCenter
                    anchors.left: parent.left
                    anchors.right: parent.right
                    anchors.leftMargin: Kirigami.Units.smallSpacing
                    anchors.rightMargin: Kirigami.Units.smallSpacing
                    spacing: Kirigami.Units.smallSpacing

                    Rectangle {
                        id: stateDot

                        Layout.preferredWidth: 8
                        Layout.preferredHeight: 8
                        radius: 4
                        color: card.stateColor

                        SequentialAnimation on opacity {
                            running: card.currentState === "ACTUATING"
                            loops: Animation.Infinite
                            onRunningChanged: {
                                if (!running)
                                    stateDot.opacity = 1;

                            }

                            NumberAnimation {
                                to: 0.2
                                duration: 350
                            }

                            NumberAnimation {
                                to: 1
                                duration: 350
                            }

                        }

                    }

                    Controls.Label {
                        Layout.fillWidth: true
                        text: card.isExternal ? "EXTERNAL / TBD" : card.currentState
                        font.bold: true
                        elide: Text.ElideRight
                        color: card.isExternal ? Kirigami.Theme.disabledTextColor : card.stateColor
                    }

                }

            }

            // Mode 1: Two-State Servo (OPEN / CLOSE)
            RowLayout {
                visible: card.valveType === "servo"
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Controls.Button {
                    Layout.fillWidth: true
                    text: "OPEN"
                    enabled: card.canActuate && card.currentState !== "OPEN"
                    onClicked: card.actuateRequested(card.valveId, "OPEN")
                }

                Controls.Button {
                    Layout.fillWidth: true
                    text: "CLOSE"
                    enabled: card.canActuate && card.currentState !== "CLOSED"
                    onClicked: card.actuateRequested(card.valveId, "CLOSE")
                }

            }

            // Mode 2a: Three-State Solenoid (FILL / CLOSED / VENT)
            RowLayout {
                visible: card.valveType === "solenoid_3way"
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Controls.Button {
                    Layout.fillWidth: true
                    text: "FILL"
                    enabled: card.canActuate && card.currentState !== "FILL"
                    onClicked: card.actuateRequested(card.valveId, "FILL")
                }

                Controls.Button {
                    Layout.fillWidth: true
                    text: "CLOSED"
                    enabled: card.canActuate && card.currentState !== "CLOSED"
                    onClicked: card.actuateRequested(card.valveId, "CLOSED")
                }

                Controls.Button {
                    Layout.fillWidth: true
                    text: "VENT"
                    enabled: card.canActuate && card.currentState !== "VENT"
                    onClicked: card.actuateRequested(card.valveId, "VENT")
                }

            }

            // Mode 2b: QD Solenoid (Disconnect only, confirmation modal)
            Controls.Button {
                visible: card.valveType === "solenoid_qd"
                Layout.fillWidth: true
                text: card.currentState === "DISCONNECTED" ? "DISCONNECTED" : "DISCONNECT QD"
                enabled: card.canActuate && card.currentState !== "DISCONNECTED"
                onClicked: card.confirmRequested(card.valveId, "DISCONNECT", card.valveLabel)
            }

            // Mode 3: Single-Use E-Match (Fire only, confirmation modal, or External/TBD)
            Controls.Button {
                visible: card.valveType === "ematch" && !card.isExternal
                Layout.fillWidth: true
                text: card.currentState === "FIRED" ? "EXPENDED (FIRED)" : "FIRE E-MATCH"
                enabled: card.canActuate && card.currentState !== "FIRED"
                onClicked: card.confirmRequested(card.valveId, "FIRE", card.valveLabel)
            }

            Controls.Label {
                visible: card.valveType === "ematch" && card.isExternal
                Layout.fillWidth: true
                text: "Controlled externally / not implemented"
                wrapMode: Text.WordWrap
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: Kirigami.Theme.disabledTextColor
            }

        }

    }

}
