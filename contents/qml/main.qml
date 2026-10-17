import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami
import "pages"

Kirigami.ApplicationWindow {
    id: root

    minimumHeight: Kirigami.Units.gridUnit * 20
    minimumWidth: Kirigami.Units.gridUnit * 30
    title: "Flow Control System"
    // Ensure the page stack uses a consistent toolbar style
    pageStack.globalToolBar.style: Kirigami.ApplicationHeaderStyle.ToolBar
    pageStack.globalToolBar.showNavigationButtons: Kirigami.ApplicationHeaderStyle.NoNavigationButtons

    // Set the first page that will be loaded when the app opens
    // This can also be set to an id of a Kirigami.Page
    pageStack.initialPage: Dashboard {
    }

    globalDrawer: Kirigami.GlobalDrawer {
        id: globalDrawer

        modal: false
        collapsible: false
        collapsed: false
        // Remove internal drawer padding around the header so the toolbar touches the top/edges
        topPadding: 0
        leftPadding: 0
        rightPadding: 0

        Sidebar {
            Layout.fillWidth: true
            Layout.margins: Kirigami.Units.gridUnit / 4
        }

        // Match the exact color set, background, border, and height of the Page ToolBar
        header: Controls.ToolBar {
            Layout.fillWidth: true
            implicitHeight: root.pageStack.globalToolBar.preferredHeight
            Kirigami.Theme.colorSet: Kirigami.Theme.Header
            Kirigami.Theme.inherit: false

            contentItem: RowLayout {
                spacing: Kirigami.Units.smallSpacing

                Kirigami.Heading {
                    Layout.fillWidth: true
                    Layout.leftMargin: Kirigami.Units.largeSpacing
                    text: "Control Panel"
                    level: 1
                    elide: Text.ElideRight
                }

            }

        }

    }

}
