import "./actuators"
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: actuators

    property bool keybindsEnabled: false
    property bool isWebsocketConnected: false
    readonly property var valveDefs: backend ? backend.valve_definitions : []
    readonly property var valveStates: backend ? backend.valves : ({
    })
    readonly property bool isArmed: backend ? backend.armed : false

    function openActionConfirm(valveId, action, label) {
        confirmDialog.pendingValveId = valveId;
        confirmDialog.pendingAction = action;
        if (action === "DISCONNECT") {
            confirmDialog.title = "Confirm QD Disconnect";
            confirmDialog.subtitle = "Disconnect " + label + "? This cannot be re-engaged remotely.";
        } else {
            confirmDialog.title = "Confirm E-Match Ignition";
            confirmDialog.subtitle = "Fire single-use E-Match \"" + label + "\"? This action is irreversible.";
        }
        confirmDialog.open();
    }

    function triggerHotkey(keyText) {
        if (!actuators.isWebsocketConnected || !actuators.keybindsEnabled || !actuators.isArmed)
            return ;

        for (let i = 0; i < actuators.valveDefs.length; ++i) {
            let def = actuators.valveDefs[i];
            if (def.key === keyText && !def.external) {
                let st = actuators.valveStates[def.id] ?? def.normal_state ?? "CLOSED";
                if (def.type === "servo") {
                    let nextAct = (st === "OPEN") ? "CLOSE" : "OPEN";
                    if (backend)
                        backend.actuate_valve(def.id, nextAct);

                } else if (def.type === "solenoid_3way") {
                    let nextSol = (st === "CLOSED") ? "FILL" : (st === "FILL" ? "VENT" : "CLOSED");
                    if (backend)
                        backend.actuate_valve(def.id, nextSol);

                } else if (def.type === "solenoid_qd" && st !== "DISCONNECTED")
                    actuators.openActionConfirm(def.id, "DISCONNECT", def.label ?? def.id);
                else if (def.type === "ematch" && st !== "FIRED")
                    actuators.openActionConfirm(def.id, "FIRE", def.label ?? def.id);
                return ;
            }
        }
    }

    spacing: Kirigami.Units.largeSpacing
    Layout.fillWidth: true
    Layout.fillHeight: true
    focus: visible && keybindsEnabled && isWebsocketConnected
    Keys.onPressed: function(event) {
        if (!actuators.visible || !actuators.keybindsEnabled || !actuators.isWebsocketConnected)
            return ;

        if (event.text >= "1" && event.text <= "9") {
            actuators.triggerHotkey(event.text);
            event.accepted = true;
        }
    }

    // Disconnected empty state placeholder (matches NotificationTray / DataListPanel style)
    Kirigami.Card {
        visible: !actuators.isWebsocketConnected
        Layout.fillWidth: true
        Layout.fillHeight: true

        contentItem: Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: Math.min(parent.width - (Kirigami.Units.largeSpacing * 2), Kirigami.Units.gridUnit * 24)
                icon.name: "network-disconnect"
                text: "No connection"
                explanation: "Connect to the valve cart server to view and control actuators."
            }

        }

    }

    // Connected scrollable grid of ActuatorCards
    Controls.ScrollView {
        id: actuatorsScroll

        visible: actuators.isWebsocketConnected
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        rightPadding: 0

        GridLayout {
            id: actuatorsGrid

            readonly property real singleColumnWidth: {
                var cols = Math.max(1, columns);
                var totalSpacing = (cols - 1) * columnSpacing;
                return Math.max(180, Math.floor((width - totalSpacing) / cols));
            }

            width: actuatorsScroll.availableWidth
            columns: width < 700 ? 1 : 2
            columnSpacing: Kirigami.Units.mediumSpacing
            rowSpacing: Kirigami.Units.mediumSpacing

            Repeater {
                model: actuators.valveDefs

                ActuatorCard {
                    required property var modelData

                    valveDef: modelData
                    baseColumnWidth: actuatorsGrid.singleColumnWidth
                    currentState: actuators.valveStates[modelData.id] ?? modelData.normal_state ?? "CLOSED"
                    armed: actuators.isArmed
                    keybindsEnabled: actuators.keybindsEnabled
                    onActuateRequested: function(valveId, action) {
                        if (backend)
                            backend.actuate_valve(valveId, action);

                    }
                    onConfirmRequested: function(valveId, action, label) {
                        actuators.openActionConfirm(valveId, action, label);
                    }
                }

            }

        }

    }

    Kirigami.PromptDialog {
        id: confirmDialog

        property string pendingValveId: ""
        property string pendingAction: ""

        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: {
            if (backend && pendingValveId.length > 0 && pendingAction.length > 0)
                backend.actuate_valve(pendingValveId, pendingAction);

            pendingValveId = "";
            pendingAction = "";
        }
        onRejected: {
            pendingValveId = "";
            pendingAction = "";
        }
    }

}
