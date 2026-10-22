import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// stores system logs in the sidebar
Kirigami.Dialog {
    id: root

    required property var notificationModel

    signal clearRequested()

    title: "System Notifications"
    preferredWidth: Math.max(Kirigami.Units.gridUnit * 26, 460)
    preferredHeight: Math.min(Kirigami.Units.gridUnit * 22, 500)
    padding: Kirigami.Units.gridUnit / 2
    standardButtons: Kirigami.Dialog.Close
    customFooterActions: [
        Kirigami.Action {
            icon.name: "edit-clear"
            text: "Clear All"
            enabled: root.notificationModel && root.notificationModel.count > 0
            onTriggered: root.clearRequested()
        }
    ]

    contentItem: Item {
        implicitWidth: Math.max(Kirigami.Units.gridUnit * 24, 420)
        implicitHeight: Math.min(Kirigami.Units.gridUnit * 18, 400)

        ListView {
            id: notifListView

            // True whenever the list items are taller than the visible viewport
            readonly property bool scrollBarNeeded: contentHeight > height
            // Reserve the scrollbar width + smallSpacing breathing room when scrolling is active
            readonly property real availableDelegateWidth: width - (scrollBarNeeded ? (vScrollBar.width + Kirigami.Units.smallSpacing) : 0)

            objectName: "notifListView"
            anchors.fill: parent
            clip: true
            spacing: Kirigami.Units.smallSpacing
            // Only bind the model while the dialog is open so InlineMessage delegates
            // never recalculate their internal layout while the dialog is hidden (0x0)
            model: root.visible ? root.notificationModel : null
            header: (root.notificationModel && root.notificationModel.count > 0) ? countHeaderComponent : null

            Component {
                id: countHeaderComponent

                Controls.Label {
                    width: notifListView.availableDelegateWidth
                    text: (root.notificationModel ? root.notificationModel.count : 0) + " total messages"
                    color: Kirigami.Theme.disabledTextColor
                    bottomPadding: Kirigami.Units.smallSpacing
                }

            }

            Kirigami.PlaceholderMessage {
                anchors.centerIn: parent
                width: parent.width - (Kirigami.Units.largeSpacing * 2)
                visible: !root.notificationModel || root.notificationModel.count === 0
                icon.name: "dialog-information"
                text: "No notifications"
                explanation: "System alerts and diagnostic logs will appear here."
            }

            Controls.ScrollBar.vertical: Controls.ScrollBar {
                id: vScrollBar

                policy: Controls.ScrollBar.AsNeeded
            }

            delegate: NotificationToast {
                id: notifDelegate

                required property int index
                required property var model

                // Shrinks automatically when the scrollbar appears so it has breathing room
                width: ListView.view ? notifListView.availableDelegateWidth : parent.width
                text: model.message
                level: model.level
                timestamp: model.timestamp
                timed: false
                animateEntryExit: false
                onDismissed: {
                    if (root.notificationModel && typeof root.notificationModel.remove === "function")
                        root.notificationModel.remove(index);

                }
            }

        }

    }

}
