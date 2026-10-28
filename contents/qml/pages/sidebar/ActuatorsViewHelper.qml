import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// sidebar view helper for the valve actuators page
// only visible when actuatorsPage is visible in the main view container
ColumnLayout {
    id: root

    Layout.fillWidth: true
    spacing: Kirigami.Units.smallSpacing
}
