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

    function isPageActive(pageName) {
        if (root.visiblePages && root.visiblePages.length > 0) {
            for (let i = 0; i < root.visiblePages.length; ++i) {
                if (root.visiblePages[i] === pageName)
                    return true;
            }
            return false;
        }
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
    spacing: Kirigami.Units.smallSpacing

    model: ListModel {
        ListElement {
            category: "Views"
            name: "Data sources"
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
        text: section
    }

    // 3. item delegate (highlights all currently visible views when multiple pages are open)
    delegate: Controls.ToolButton {
        id: navBtn

        width: ListView.view.width
        highlighted: root.isPageActive(model.page)
        onClicked: root.navigateRequested(model.page)

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
