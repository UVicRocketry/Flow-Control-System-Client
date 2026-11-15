import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Single-pane tab bar placed in the bottom row of the split-view grid:
// Left pane:  -> | (page name, centered) | X
// Right pane: <- | (page name, centered) | X
Controls.ToolBar {
    id: root

    required property string paneSide
    required property string pageTitle
    required property bool focused

    signal swapRequested()
    signal closeRequested()
    signal focusRequested()

    Layout.fillWidth: true
    Layout.preferredWidth: Kirigami.Units.gridUnit * 34
    Layout.minimumWidth: 0
    padding: Kirigami.Units.smallSpacing / 2
    leftPadding: Kirigami.Units.smallSpacing / 2
    rightPadding: Kirigami.Units.smallSpacing / 2
    topPadding: Kirigami.Units.smallSpacing / 2
    bottomPadding: Kirigami.Units.smallSpacing / 2
    leftInset: 0
    rightInset: 0
    topInset: 0
    bottomInset: 0
    Kirigami.Theme.colorSet: Kirigami.Theme.Header
    Kirigami.Theme.inherit: false

    background: Rectangle {
        color: Kirigami.Theme.backgroundColor
        radius: Kirigami.Units.smallSpacing
        border.width: root.focused ? 2 : 1
        border.color: root.focused ? Kirigami.Theme.highlightColor : Qt.alpha(Kirigami.Theme.textColor, 0.15)
    }

    contentItem: RowLayout {
        spacing: Kirigami.Units.smallSpacing / 2

        Controls.ToolButton {
            icon.name: root.paneSide === "left" ? "go-next" : "go-previous"
            text: root.paneSide === "left" ? "Move right" : "Move left"
            display: Controls.AbstractButton.IconOnly
            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text: root.paneSide === "left" ? "Move to right panel" : "Move to left panel"
            onClicked: root.swapRequested()
        }

        Kirigami.Separator {
            Layout.fillHeight: true
            Layout.topMargin: Kirigami.Units.smallSpacing
            Layout.bottomMargin: Kirigami.Units.smallSpacing
        }

        Item {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Controls.Label {
                width: parent.width
                height: parent.height
                leftPadding: Kirigami.Units.smallSpacing
                rightPadding: Kirigami.Units.smallSpacing
                text: root.pageTitle
                horizontalAlignment: Text.AlignHCenter
                verticalAlignment: Text.AlignVCenter
                elide: Text.ElideRight
                font.bold: root.focused
                color: root.focused ? Kirigami.Theme.highlightColor : Kirigami.Theme.textColor
            }

            MouseArea {
                width: parent.width
                height: parent.height
                acceptedButtons: Qt.AllButtons
                onClicked: root.focusRequested()
            }

        }

        Kirigami.Separator {
            Layout.fillHeight: true
            Layout.topMargin: Kirigami.Units.smallSpacing
            Layout.bottomMargin: Kirigami.Units.smallSpacing
        }

        Controls.ToolButton {
            icon.name: "window-close"
            text: "Close"
            display: Controls.AbstractButton.IconOnly
            Controls.ToolTip.visible: hovered
            Controls.ToolTip.text: root.paneSide === "left" ? "Close left panel" : "Close right panel"
            onClicked: root.closeRequested()
        }

    }

}
