import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

RowLayout {
    id: root

    required property int cardIndex
    required property int totalCards
    required property string title
    required property string channelKey
    required property string yAxisLabel
    required property color resolvedColor
    required property bool filterOutliers3Std
    required property int smoothingWindow
    required property bool hasData
    required property real currentValue
    required property bool editLayoutMode

    signal editRequested(int index)
    signal removeRequested(int index)
    signal moveRequested(int fromIndex, int toIndex)

    Layout.fillWidth: true
    spacing: Kirigami.Units.smallSpacing

    // channel colour indicator dot (greyed out when graph has no associated data)
    Rectangle {
        Layout.preferredWidth: 10
        Layout.preferredHeight: 10
        radius: 5
        color: root.hasData ? root.resolvedColor : Kirigami.Theme.disabledTextColor
        opacity: root.hasData ? 1 : 0.55
        Layout.alignment: Qt.AlignVCenter
    }

    // title and active filter/smoothing subtitle
    ColumnLayout {
        Layout.fillWidth: true
        spacing: 0
        opacity: root.hasData ? 1 : 0.55

        Controls.Label {
            text: root.title
            font.bold: true
            color: root.hasData ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor
            elide: Text.ElideRight
            Layout.fillWidth: true
        }

        Controls.Label {
            text: root.channelKey + (root.filterOutliers3Std ? " • 3σ Filtered" : "") + (root.smoothingWindow > 1 ? " • Smooth(" + root.smoothingWindow + ")" : "")
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            color: Kirigami.Theme.disabledTextColor
            elide: Text.ElideRight
            Layout.fillWidth: true
        }

    }

    // live / latest value readout
    Controls.Label {
        text: (root.hasData ? root.currentValue.toFixed(2) : "--") + (root.yAxisLabel !== "" ? " " + root.yAxisLabel : "")
        font.bold: true
        font.family: "monospace"
        color: root.hasData ? root.resolvedColor : Kirigami.Theme.disabledTextColor
        opacity: root.hasData ? 1 : 0.55
        Layout.alignment: Qt.AlignVCenter
    }

    // edit layout controls (visible when editLayoutMode is active)
    RowLayout {
        visible: root.editLayoutMode
        spacing: 2

        Controls.ToolButton {
            icon.name: "go-previous"
            display: Controls.AbstractButton.IconOnly
            enabled: root.cardIndex > 0
            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text: "Move card earlier"
            onClicked: root.moveRequested(root.cardIndex, root.cardIndex - 1)
        }

        Controls.ToolButton {
            icon.name: "go-next"
            display: Controls.AbstractButton.IconOnly
            enabled: root.cardIndex < root.totalCards - 1
            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text: "Move card later"
            onClicked: root.moveRequested(root.cardIndex, root.cardIndex + 1)
        }

        Controls.ToolButton {
            icon.name: "edit-rename"
            display: Controls.AbstractButton.IconOnly
            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text: "Configure graph (Title, Source, Color, 3σ Smoothing, Axes)"
            onClicked: root.editRequested(root.cardIndex)
        }

        Controls.ToolButton {
            icon.name: "edit-delete"
            display: Controls.AbstractButton.IconOnly
            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text: "Remove graph card"
            onClicked: root.removeRequested(root.cardIndex)
        }

    }

}
