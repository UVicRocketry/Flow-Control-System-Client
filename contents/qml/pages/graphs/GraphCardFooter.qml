import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// footer bar displaying min, max, and average statistics
// uses equal preferredWidth weights so labels never shift as digit counts change
RowLayout {
    id: root

    required property bool hasData
    required property real statMin
    required property real statMax
    required property real statMean

    Layout.fillWidth: true
    spacing: Kirigami.Units.largeSpacing
    opacity: root.hasData ? 1 : 0.55

    Controls.Label {
        text: "Min: " + (root.hasData ? root.statMin.toFixed(1) : "--")
        font.family: "monospace"
        font.pointSize: Kirigami.Theme.smallFont.pointSize
        color: Kirigami.Theme.disabledTextColor
        elide: Text.ElideRight
        Layout.fillWidth: true
        Layout.preferredWidth: 1
    }

    Controls.Label {
        text: "Max: " + (root.hasData ? root.statMax.toFixed(1) : "--")
        font.family: "monospace"
        font.pointSize: Kirigami.Theme.smallFont.pointSize
        color: Kirigami.Theme.disabledTextColor
        horizontalAlignment: Text.AlignHCenter
        elide: Text.ElideRight
        Layout.fillWidth: true
        Layout.preferredWidth: 1
    }

    Controls.Label {
        text: "Avg: " + (root.hasData ? root.statMean.toFixed(1) : "--")
        font.family: "monospace"
        font.pointSize: Kirigami.Theme.smallFont.pointSize
        color: Kirigami.Theme.disabledTextColor
        horizontalAlignment: Text.AlignRight
        elide: Text.ElideRight
        Layout.fillWidth: true
        Layout.preferredWidth: 1
    }

}
