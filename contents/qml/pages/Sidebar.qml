import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root

    property string activePageName: "dashboard"
    property int unreadNotificationCount: 0

    signal navigateRequested(string pageName)
    signal settingsRequested()
    signal notificationsRequested()

    spacing: Kirigami.Units.smallSpacing
    Layout.fillWidth: true
    Layout.fillHeight: true

    ListView {
        id: navList

        Layout.fillWidth: true
        // Set implicitHeight so ColumnLayout allocates enough room for all items
        implicitHeight: contentHeight
        implicitWidth: Kirigami.Units.gridUnit * 10
        clip: true
        interactive: false // If you don't need independent scrolling inside the sidebar
        // 1. Group by the model's 'category' field
        section.property: "category"
        section.criteria: ViewSection.FullString
        spacing: Kirigami.Units.smallSpacing

        model: ListModel {
            // Section 1: Views
            ListElement {
                category: "Views"
                name: "Dashboard"
                icon: "computer"
                page: "dashboard"
            }

            ListElement {
                category: "Views"
                name: "Valve actuators"
                icon: "network-wired"
                page: "actuators"
            }

            ListElement {
                category: "Views"
                name: "Graphs"
                icon: "utilities-system-monitor"
                page: "graphs"
            }

        }

        // 2. Kirigami section header delegate
        section.delegate: Kirigami.ListSectionHeader {
            width: ListView.view.width
            // 'section' is an attached property provided by ListView containing the category string
            text: section
        }

        // 3. Item delegate
        delegate: Controls.ToolButton {
            id: navBtn

            width: ListView.view.width
            onClicked: {
                root.activePageName = model.page;
                root.navigateRequested(model.page);
            }
            highlighted: root.activePageName === model.page

            RowLayout {
                spacing: Kirigami.Units.largeSpacing
                anchors.verticalCenter: parent.verticalCenter
                anchors.left: parent.left
                anchors.leftMargin: Kirigami.Units.gridUnit / 2

                Kirigami.Icon {
                    source: model.icon
                    implicitWidth: Kirigami.Units.iconSizes.smallMedium
                    implicitHeight: Kirigami.Units.iconSizes.smallMedium
                    Layout.alignment: Qt.AlignVCenter
                }

                Controls.Label {
                    elide: Text.ElideRight
                    text: model.name
                    font.bold: navBtn.highlighted
                    Layout.fillWidth: true
                    Layout.alignment: Qt.AlignVCenter
                }

            }

        }

    }

    // Bottom Spacer
    Item {
        Layout.fillHeight: true
    }

    // Bottom Bar: Settings (bottom-left) and Notification Tray (bottom-right)
    RowLayout {
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

}
