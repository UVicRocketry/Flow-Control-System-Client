import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Dedicated vertical scrollbar column with an optional right-edge separator for left split panes
Item {
    id: root

    required property Flickable flickable
    property bool pageVisible: true
    property bool showSeparator: false
    readonly property alias scrollBar: internalScrollBar

    visible: root.pageVisible && root.flickable.contentHeight > root.flickable.height
    Layout.fillHeight: true
    Layout.preferredWidth: Math.max(internalScrollBar.implicitWidth, Kirigami.Units.gridUnit)
    Layout.rightMargin: root.showSeparator ? 0 : -Kirigami.Units.smallSpacing

    Controls.ScrollBar {
        id: internalScrollBar

        anchors.fill: parent
        anchors.margins: 2
        anchors.rightMargin: root.showSeparator ? Kirigami.Units.mediumSpacing : 2
        orientation: Qt.Vertical
        policy: root.pageVisible ? Controls.ScrollBar.AsNeeded : Controls.ScrollBar.AlwaysOff
        enabled: root.pageVisible
    }

    Kirigami.Separator {
        visible: root.showSeparator
        anchors.right: parent.right
        anchors.top: parent.top
        anchors.bottom: parent.bottom
    }

}
