import QtQuick
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Framed pane cell in the upper row of the split-view grid; holds an inline page or its popout placeholder
Item {
    id: root

    required property string pageName
    required property string pageTitle
    required property string pageIcon
    required property bool poppedOut
    required property bool splitViewActive
    property real minimumPaneWidth: Kirigami.Units.gridUnit * 24
    property real preferredPaneWidth: Kirigami.Units.gridUnit * 34
    readonly property alias pageHost: pageHostColumn

    signal returnRequested(string pageName)

    Layout.fillWidth: true
    Layout.fillHeight: true
    Layout.preferredWidth: root.preferredPaneWidth
    Layout.minimumWidth: root.splitViewActive ? root.minimumPaneWidth : 0

    ColumnLayout {
        width: root.width
        height: root.height
        spacing: 0

        ColumnLayout {
            id: pageHostColumn

            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.pageName !== "" && !root.poppedOut
            spacing: 0
        }

        PoppedOutPlaceholder {
            Layout.fillWidth: true
            Layout.fillHeight: true
            visible: root.pageName !== "" && root.poppedOut
            pageName: root.pageName
            pageTitle: root.pageTitle
            pageIcon: root.pageIcon
            onReturnRequested: function(returnedName) {
                root.returnRequested(returnedName);
            }
        }

    }

}
