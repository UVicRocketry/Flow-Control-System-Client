import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Card {
    id: actuators

    header: Kirigami.Heading {
        text: "Valve Actuation Panel"
        level: 2
    }

    contentItem: Controls.Label {
        text: "Valve controls and limit switch telemetry will be displayed here."
        color: Kirigami.Theme.disabledTextColor
    }

}
