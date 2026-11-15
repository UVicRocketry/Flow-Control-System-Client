import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// External popout window hosting a detached page
Controls.ApplicationWindow {
    id: root

    property string pageName: ""
    property string pageTitle: ""
    property alias hostLayout: pageHost

    signal returnRequested(string pageName)

    width: 960
    height: 680
    minimumWidth: Kirigami.Units.gridUnit * 24
    minimumHeight: Kirigami.Units.gridUnit * 18
    title: pageTitle ? (pageTitle + " — Flow Control System") : "Flow Control System"
    color: Kirigami.Theme.backgroundColor
    onClosing: function(close) {
        close.accepted = false;
        root.returnRequested(root.pageName);
    }

    ColumnLayout {
        id: pageHost

        anchors.fill: parent
        anchors.margins: Kirigami.Units.largeSpacing
        spacing: 0
    }

}
