import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root

    // bound to settings/config key ("INFO", "WARN", or "ERR")
    property string minSeverity: "INFO"

    function severityRank(level) {
        const ranks = {
            "INFO": 0,
            "WARN": 1,
            "ERR": 2
        };
        return ranks[level] !== undefined ? ranks[level] : 0;
    }

    function kirigamiMessageType(level) {
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

    function appendLog(level, messageText) {
        logModel.append({
            "level": level,
            "message": messageText
        });
    }

    spacing: Kirigami.Units.smallSpacing

    ListModel {
        id: logModel
    }

    Repeater {
        model: logModel

        delegate: Kirigami.InlineMessage {
            id: inlineMsg

            required property string level
            required property string message
            required property int index

            Layout.fillWidth: true
            text: message
            type: root.kirigamiMessageType(level)
            // Dynamically show/hide based on the active config threshold
            visible: root.severityRank(level) >= root.severityRank(root.minSeverity)
            // Remove from model when closed by the user
            onVisibleChanged: {
                if (!visible && root.severityRank(level) >= root.severityRank(root.minSeverity))
                    logModel.remove(index);

            }

            actions: Kirigami.Action {
                icon.name: "window-close"
                onTriggered: inlineMsg.visible = false
            }

        }

    }

}
