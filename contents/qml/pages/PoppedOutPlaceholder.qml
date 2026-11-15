import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Inline placeholder displayed when a page is popped out into an external window
Kirigami.Card {
    id: root

    required property string pageName
    required property string pageTitle
    required property string pageIcon

    signal returnRequested(string pageName)

    Layout.fillWidth: true
    Layout.fillHeight: true

    contentItem: Item {
        Kirigami.PlaceholderMessage {
            anchors.centerIn: parent
            width: Math.min(parent.width - (Kirigami.Units.largeSpacing * 2), Kirigami.Units.gridUnit * 24)
            icon.name: root.pageIcon || "window-duplicate"
            text: "Window Popped Out"
            explanation: (root.pageTitle || "This page") + " is currently open in a separate window."

            helpfulAction: Kirigami.Action {
                icon.name: "view-restore"
                text: "Return to Main Application"
                onTriggered: root.returnRequested(root.pageName)
            }

        }

    }

}
