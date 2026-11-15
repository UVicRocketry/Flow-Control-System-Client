import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// primary view navigation list at the top of the sidebar
ListView {
    id: root

    required property string activePageName
    required property var visiblePages

    signal navigateRequested(string pageName)
    signal openInLeftRequested(string pageName)
    signal openInRightRequested(string pageName)
    signal openInNewWindowRequested(string pageName)

    function isPageActive(pageName) {
        if (root.visiblePages && root.visiblePages.length > 0)
            return root.visiblePages.indexOf(pageName) !== -1;

        return root.activePageName === pageName;
    }

    Layout.fillWidth: true
    // set implicitHeight so ColumnLayout allocates enough room for all items
    implicitHeight: contentHeight
    implicitWidth: Kirigami.Units.gridUnit * 10
    clip: true
    interactive: false
    // 1. group by the model's 'category' field
    section.property: "category"
    section.criteria: ViewSection.FullString
    spacing: 0

    model: ListModel {
        ListElement {
            category: "Views"
            name: "Data sources"
            iconName: "computer"
            page: "dashboard"
        }

        ListElement {
            category: "Views"
            name: "Valve actuators"
            iconName: "network-wired"
            page: "actuators"
        }

        ListElement {
            category: "Views"
            name: "Graphs"
            iconName: "utilities-system-monitor"
            page: "graphs"
        }

        ListElement {
            category: "Views"
            name: "Video"
            iconName: "camera-video"
            page: "video"
        }

    }

    // 2. Kirigami section header delegate
    section.delegate: Kirigami.ListSectionHeader {
        width: ListView.view.width
        text: section
    }

    // 3. item delegate (highlights all currently visible views when multiple pages are open)
    delegate: Controls.ItemDelegate {
        id: navBtn

        required property string name
        required property string iconName
        required property string page
        property int lastModifiers: Qt.NoModifier

        width: ListView.view.width
        text: name
        icon.name: iconName
        icon.color: "transparent"
        icon.width: Kirigami.Units.iconSizes.smallMedium
        icon.height: Kirigami.Units.iconSizes.smallMedium
        font.bold: highlighted
        highlighted: root.isPageActive(page)
        onClicked: {
            var mods = navBtn.lastModifiers;
            navBtn.lastModifiers = Qt.NoModifier;
            if (mods & Qt.AltModifier)
                root.openInNewWindowRequested(page);
            else if (mods & Qt.ControlModifier)
                root.openInRightRequested(page);
            else if (mods & Qt.ShiftModifier)
                root.openInLeftRequested(page);
            else
                root.navigateRequested(page);
        }

        MouseArea {
            anchors.fill: parent
            acceptedButtons: Qt.LeftButton | Qt.RightButton
            onPressed: function(mouse) {
                if (mouse.button === Qt.RightButton) {
                    navContextMenu.popup();
                    mouse.accepted = true;
                } else {
                    navBtn.lastModifiers = mouse.modifiers;
                    mouse.accepted = false;
                }
            }
        }

        Controls.Menu {
            id: navContextMenu

            Controls.MenuItem {
                text: "Open in left panel (Shift+Click)"
                icon.name: "go-previous"
                onTriggered: root.openInLeftRequested(navBtn.page)
            }

            Controls.MenuItem {
                text: "Open in right panel (Ctrl+Click)"
                icon.name: "go-next"
                onTriggered: root.openInRightRequested(navBtn.page)
            }

            Controls.MenuItem {
                text: "Open in new window (Alt+Click)"
                icon.name: "window-new"
                onTriggered: root.openInNewWindowRequested(navBtn.page)
            }

        }

    }

}
