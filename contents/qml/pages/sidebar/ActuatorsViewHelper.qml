import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// sidebar view helper for the valve actuators page
// only visible when actuatorsPage is visible in the main view container
ColumnLayout {
    id: root

    property bool keybindsEnabled: false

    signal abortRequested()
    signal keybindsToggled(bool enabled)

    Layout.fillWidth: true
    spacing: Kirigami.Units.smallSpacing

    ColumnLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        Kirigami.ListSectionHeader {
            Layout.fillWidth: true
            text: "Safety & Controls"
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            spacing: Kirigami.Units.smallSpacing

            Controls.Button {
                id: abortButton

                Layout.fillWidth: true
                text: "Emergency Abort"
                icon.name: "process-stop"
                onClicked: root.abortRequested()
            }

            Controls.CheckBox {
                id: keybindsCheckBox

                Layout.fillWidth: true
                // Layout.leftMargin: Kirigami.Units.gridUnit / 2
                text: "Enable Keybinds (1–5)"
                checked: root.keybindsEnabled
                onToggled: root.keybindsToggled(checked)
            }

        }

    }

}
