import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// sidebar view helper for the graphs page (time scale presets & global graph controls)
// only visible when graphsPage is visible in the main view container
ColumnLayout {
    id: root

    required property string timeScalePreset
    required property int customWindowSeconds
    required property real effectiveWindowSeconds
    required property bool smoothAllActive
    required property bool editLayoutActive

    signal presetSelected(string preset)
    signal customSecondsModified(int seconds)
    signal smoothAllToggled(bool active)
    signal editLayoutToggled(bool active)

    Layout.fillWidth: true
    spacing: Kirigami.Units.smallSpacing

    // time scaling presets (30s, 1m, 3m, custom -> most recent)
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        Kirigami.ListSectionHeader {
            Layout.fillWidth: true
            text: "Time Scale"
        }

        GridLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            columns: 2
            columnSpacing: Kirigami.Units.smallSpacing
            rowSpacing: Kirigami.Units.smallSpacing

            Controls.Button {
                Layout.fillWidth: true
                text: "30s"
                checkable: true
                checked: root.timeScalePreset === "30s"
                highlighted: checked
                onClicked: root.presetSelected("30s")
            }

            Controls.Button {
                Layout.fillWidth: true
                text: "1m"
                checkable: true
                checked: root.timeScalePreset === "1m"
                highlighted: checked
                onClicked: root.presetSelected("1m")
            }

            Controls.Button {
                Layout.fillWidth: true
                text: "3m"
                checkable: true
                checked: root.timeScalePreset === "3m"
                highlighted: checked
                onClicked: root.presetSelected("3m")
            }

            Controls.Button {
                Layout.fillWidth: true
                text: "Custom"
                checkable: true
                checked: root.timeScalePreset === "custom"
                highlighted: checked
                onClicked: root.presetSelected("custom")
            }

        }

        // custom recent window input (visible when "custom" preset is selected)
        ColumnLayout {
            visible: root.timeScalePreset === "custom"
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            spacing: 2

            Controls.Label {
                text: "Most recent (seconds):"
                font.pointSize: Kirigami.Theme.smallFont.pointSize
                color: Kirigami.Theme.disabledTextColor
            }

            Controls.SpinBox {
                id: customSecSpin

                Layout.fillWidth: true
                from: 5
                to: 7200
                stepSize: 5
                editable: true
                value: root.customWindowSeconds
                onValueModified: root.customSecondsModified(value)
            }

        }

    }

    // graph controls (smooth all & edit layout)
    ColumnLayout {
        Layout.fillWidth: true
        spacing: Kirigami.Units.smallSpacing

        Kirigami.ListSectionHeader {
            Layout.fillWidth: true
            text: "Graph Controls"
        }

        ColumnLayout {
            Layout.fillWidth: true
            Layout.leftMargin: Kirigami.Units.smallSpacing
            Layout.rightMargin: Kirigami.Units.smallSpacing
            spacing: Kirigami.Units.smallSpacing

            Controls.Button {
                Layout.fillWidth: true
                text: "3σ Smooth All"
                icon.name: "view-filter"
                checkable: true
                checked: root.smoothAllActive
                highlighted: checked
                Controls.ToolTip.visible: hovered
                Controls.ToolTip.text: "Toggle 3-standard-deviation outlier smoothing on all graphs"
                onToggled: root.smoothAllToggled(checked)
            }

            Controls.Button {
                Layout.fillWidth: true
                text: root.editLayoutActive ? "Done Editing" : "Edit Layout"
                icon.name: "edit-rename"
                checkable: true
                checked: root.editLayoutActive
                highlighted: checked
                Controls.ToolTip.visible: hovered
                Controls.ToolTip.text: "Toggle graph edit buttons and resize handlebars"
                onToggled: root.editLayoutToggled(checked)
            }

        }

    }

}
