import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Card {
    id: graphs

    header: Kirigami.Heading {
        text: "Telemetry Charts"
        level: 2
    }

    contentItem: Controls.Label {
        text: "Graphs will be here"
        color: Kirigami.Theme.disabledTextColor
    }

}
