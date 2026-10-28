import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// bottom bar with settings button (left) and notification tray button + unread badge (right)
RowLayout {
    id: root

    required property int unreadNotificationCount

    signal settingsRequested()
    signal notificationsRequested()

    Layout.fillWidth: true
    Layout.leftMargin: Kirigami.Units.gridUnit / 4
    Layout.rightMargin: Kirigami.Units.gridUnit / 4
    Layout.bottomMargin: Kirigami.Units.gridUnit / 4
    spacing: Kirigami.Units.smallSpacing

    Controls.ToolButton {
        id: settingsBtn

        icon.name: "configure"
        display: Controls.AbstractButton.IconOnly
        Controls.ToolTip.visible: hovered
        Controls.ToolTip.text: "Settings"
        onClicked: root.settingsRequested()
    }

    Item {
        Layout.fillWidth: true
    }

    Controls.ToolButton {
        id: notifTrayBtn

        icon.name: "notifications"
        display: Controls.AbstractButton.IconOnly
        Controls.ToolTip.visible: hovered
        Controls.ToolTip.text: "Notifications" + (root.unreadNotificationCount > 0 ? " (" + root.unreadNotificationCount + ")" : "")
        onClicked: root.notificationsRequested()

        Rectangle {
            visible: root.unreadNotificationCount > 0
            anchors.top: parent.top
            anchors.right: parent.right
            anchors.topMargin: 4
            anchors.rightMargin: 2
            width: Math.max(14, badgeText.implicitWidth + 4)
            height: 14
            radius: 7
            color: Kirigami.Theme.negativeTextColor

            Controls.Label {
                id: badgeText

                anchors.centerIn: parent
                text: root.unreadNotificationCount > 99 ? "99+" : String(root.unreadNotificationCount)
                color: Kirigami.Theme.textColor
                font.bold: true
                font.pixelSize: 9
            }

        }

    }

}
