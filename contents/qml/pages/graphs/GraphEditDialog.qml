import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// modal dialog for configuring a GraphCard's channel, labels, color, Y-axis bounds, and smoothing
Kirigami.Dialog {
    id: root

    property int targetIndex: -1
    property var availableChannels: []
    // editable fields passed to graph cards
    property string editTitle: ""
    property string editChannelKey: ""
    property string editColor: "theme:highlight"
    property string editXAxisLabel: "Time (s)"
    property string editYAxisLabel: "kPa"
    property var editAllowedUnits: ["kPa", "psi"]
    property bool editAutoScale: true
    property real editManualMinY: 0
    property real editManualMaxY: 1000
    property bool editFilterOutliers3Std: false
    property int editSmoothingWindow: 1
    property int editMaxBuckets: 300
    property bool editShowGrid: true
    property bool editShowFill: true
    property int editColSpan: 1
    readonly property GraphColorHelper
    colorHelper: GraphColorHelper {
    }

    signal settingsApplied(int index, var updatedConfig)

    function normalizeUnitLabel(unitStr) {
        var raw = String(unitStr || "").trim();
        var lower = raw.toLowerCase();
        var map = {
            "kpa": "kPa",
            "psi": "psi",
            "psig": "psi",
            "psia": "psi",
            "kg": "kg",
            "kilogram": "kg",
            "kilograms": "kg",
            "lb": "lbs",
            "lbs": "lbs",
            "pound": "lbs",
            "pounds": "lbs",
            "n": "N",
            "newton": "N",
            "newtons": "N",
            "lbf": "lbf",
            "c": "°C",
            "°c": "°C",
            "degc": "°C",
            "f": "°F",
            "°f": "°F",
            "degf": "°F",
            "k": "K",
            "kelvin": "K"
        };
        return map[lower] || raw;
    }

    function allowedUnitsForChannel(chKey) {
        for (let i = 0; i < root.availableChannels.length; ++i) {
            let ch = root.availableChannels[i];
            if (ch.key === chKey && ch.allowed_units && ch.allowed_units.length > 0)
                return ch.allowed_units;

        }
        var upper = String(chKey || "").trim().toUpperCase();
        if (upper.indexOf("M_") === 0 || upper === "L_RUN_TANK" || upper.indexOf("MASS") >= 0)
            return ["kg", "lbs"];

        if (upper.indexOf("T_") === 0)
            return ["°C", "°F", "K"];

        if (upper.indexOf("L_") === 0)
            return ["N", "lbf"];

        return ["kPa", "psi"];
    }

    function selectSwatchColor(key) {
        root.editColor = key;
        colorHexField.text = key;
    }

    function openForCard(index, cardData, channels) {
        root.targetIndex = index;
        root.availableChannels = channels || [];
        root.editTitle = cardData.title || "";
        root.editChannelKey = cardData.channelKey || "P_RUN_TANK";
        root.editAllowedUnits = root.allowedUnitsForChannel(root.editChannelKey);
        var desiredUnit = root.normalizeUnitLabel(cardData.yAxisLabel);
        if (root.editAllowedUnits.indexOf(desiredUnit) < 0)
            desiredUnit = root.editAllowedUnits[0];

        root.editYAxisLabel = desiredUnit;
        root.editColor = String(cardData.accentColor || "theme:highlight");
        root.editXAxisLabel = cardData.xAxisLabel !== undefined ? cardData.xAxisLabel : "Time (s)";
        root.editAutoScale = cardData.autoScale !== undefined ? Boolean(cardData.autoScale) : true;
        root.editManualMinY = Number(cardData.manualMinY ?? 0);
        root.editManualMaxY = Number(cardData.manualMaxY ?? 1000);
        root.editFilterOutliers3Std = Boolean(cardData.filterOutliers3Std);
        root.editSmoothingWindow = Number(cardData.smoothingWindow ?? 1);
        root.editMaxBuckets = Number(cardData.maxBuckets ?? 300);
        root.editShowGrid = cardData.showGrid !== undefined ? Boolean(cardData.showGrid) : true;
        root.editShowFill = cardData.showFill !== undefined ? Boolean(cardData.showFill) : true;
        root.editColSpan = Number(cardData.colSpan ?? 1);
        titleField.text = root.editTitle;
        colorHexField.text = root.editColor;
        xAxisField.text = root.editXAxisLabel;
        minYField.text = String(root.editManualMinY);
        maxYField.text = String(root.editManualMaxY);
        root.open();
    }

    title: root.targetIndex < 0 ? "Add Graph Card" : "Configure Graph Card"
    preferredWidth: Kirigami.Units.gridUnit * 27
    padding: Kirigami.Units.largeSpacing
    standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
    onAccepted: {
        var parsedMinY = parseFloat(minYField.text);
        var parsedMaxY = parseFloat(maxYField.text);
        if (isNaN(parsedMinY))
            parsedMinY = 0;

        if (isNaN(parsedMaxY) || parsedMaxY <= parsedMinY)
            parsedMaxY = parsedMinY + 100;

        root.settingsApplied(root.targetIndex, {
            "title": titleField.text.trim() !== "" ? titleField.text.trim() : root.editChannelKey,
            "channelKey": root.editChannelKey,
            "accentColor": colorHexField.text.trim() !== "" ? colorHexField.text.trim() : root.editColor,
            "xAxisLabel": xAxisField.text,
            "yAxisLabel": yAxisUnitCombo.currentText || root.editYAxisLabel,
            "autoScale": autoScaleCheck.checked,
            "manualMinY": parsedMinY,
            "manualMaxY": parsedMaxY,
            "filterOutliers3Std": outlier3StdCheck.checked,
            "smoothingWindow": smoothingSpin.value,
            "maxBuckets": bucketsSpin.value,
            "showGrid": showGridCheck.checked,
            "showFill": showFillCheck.checked,
            "colSpan": colSpanSpin.value
        });
    }

    ColumnLayout {
        spacing: Kirigami.Units.mediumSpacing

        Kirigami.Heading {
            text: "General & Data Source"
            level: 4
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: Kirigami.Units.mediumSpacing
            rowSpacing: Kirigami.Units.smallSpacing

            Controls.Label {
                text: "Graph Title:"
            }

            Controls.TextField {
                id: titleField

                Layout.fillWidth: true
                placeholderText: "Enter graph title..."
            }

            Controls.Label {
                text: "Data Source:"
            }

            Controls.ComboBox {
                id: channelCombo

                Layout.fillWidth: true
                model: {
                    var list = [];
                    for (let i = 0; i < root.availableChannels.length; ++i) {
                        let ch = root.availableChannels[i];
                        list.push(ch.key + (ch.title ? " — " + ch.title : ""));
                    }
                    if (list.length === 0)
                        list.push(root.editChannelKey);

                    return list;
                }
                currentIndex: {
                    for (let i = 0; i < root.availableChannels.length; ++i) {
                        if (root.availableChannels[i].key === root.editChannelKey)
                            return i;

                    }
                    return 0;
                }
                onActivated: function(idx) {
                    if (idx >= 0 && idx < root.availableChannels.length) {
                        let ch = root.availableChannels[idx];
                        root.editChannelKey = ch.key;
                        if (ch.title)
                            titleField.text = ch.title;

                        let nextAllowed = root.allowedUnitsForChannel(ch.key);
                        root.editAllowedUnits = nextAllowed;
                        let currentUnit = root.normalizeUnitLabel(root.editYAxisLabel);
                        if (nextAllowed.indexOf(currentUnit) < 0) {
                            let chUnit = root.normalizeUnitLabel(ch.unit);
                            root.editYAxisLabel = nextAllowed.indexOf(chUnit) >= 0 ? chUnit : nextAllowed[0];
                        }
                        if (ch.color)
                            root.selectSwatchColor(ch.color);

                    }
                }
            }

        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            text: "Colouration"
            level: 4
        }

        ColumnLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.smallSpacing

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Controls.Label {
                    text: "Theme:"
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    color: Kirigami.Theme.disabledTextColor
                    Layout.preferredWidth: 48
                }

                Repeater {
                    model: colorHelper.themeColorPalette

                    GraphColorSwatch {
                        required property var modelData

                        colorKey: modelData.key
                        swatchColor: colorHelper.resolve(modelData.key)
                        tooltipText: modelData.label + " (" + modelData.key + ")"
                        selected: colorHexField.text.toLowerCase() === modelData.key.toLowerCase()
                        swatchRadius: 6
                        onPicked: function(key) {
                            root.selectSwatchColor(key);
                        }
                    }

                }

                Item {
                    Layout.fillWidth: true
                }

            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Controls.Label {
                    text: "Fixed:"
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    color: Kirigami.Theme.disabledTextColor
                    Layout.preferredWidth: 48
                }

                Repeater {
                    model: colorHelper.fixedColorPalette

                    GraphColorSwatch {
                        required property string modelData

                        colorKey: modelData
                        swatchColor: modelData
                        tooltipText: modelData
                        selected: colorHexField.text.toLowerCase() === modelData.toLowerCase()
                        swatchRadius: 12
                        unselectedBorderColor: "transparent"
                        onPicked: function(key) {
                            root.selectSwatchColor(key);
                        }
                    }

                }

                Item {
                    Layout.fillWidth: true
                }

                Controls.TextField {
                    id: colorHexField

                    Layout.preferredWidth: 118
                    font.family: "monospace"
                    placeholderText: "theme:highlight"
                }

            }

        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            text: "Data Smoothing & Buckets"
            level: 4
        }

        Controls.CheckBox {
            id: outlier3StdCheck

            checked: root.editFilterOutliers3Std
            text: "Filter outliers outside 3σ (do not render spikes beyond ±3 std dev)"
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 2
            columnSpacing: Kirigami.Units.mediumSpacing
            rowSpacing: Kirigami.Units.smallSpacing

            Controls.Label {
                text: "Moving Average Window:"
            }

            Controls.SpinBox {
                id: smoothingSpin

                from: 1
                to: 25
                value: root.editSmoothingWindow
                editable: true
            }

            Controls.Label {
                text: "Max Time Buckets:"
            }

            Controls.SpinBox {
                id: bucketsSpin

                from: 50
                to: 1000
                stepSize: 50
                value: root.editMaxBuckets
                editable: true
            }

        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        Kirigami.Heading {
            text: "Axes & Scaling"
            level: 4
        }

        Controls.CheckBox {
            id: autoScaleCheck

            checked: root.editAutoScale
            text: "Autoscale Y-Axis to visible data range"
        }

        GridLayout {
            Layout.fillWidth: true
            columns: 4
            columnSpacing: Kirigami.Units.smallSpacing
            rowSpacing: Kirigami.Units.smallSpacing

            Controls.Label {
                text: "Min Y:"
                enabled: !autoScaleCheck.checked
            }

            Controls.TextField {
                id: minYField

                Layout.fillWidth: true
                enabled: !autoScaleCheck.checked
                placeholderText: "0.0"
            }

            Controls.Label {
                text: "Max Y:"
                enabled: !autoScaleCheck.checked
            }

            Controls.TextField {
                id: maxYField

                Layout.fillWidth: true
                enabled: !autoScaleCheck.checked
                placeholderText: "1000.0"
            }

            Controls.Label {
                text: "Y-Axis Unit:"
            }

            Controls.ComboBox {
                id: yAxisUnitCombo

                Layout.fillWidth: true
                model: root.editAllowedUnits
                currentIndex: {
                    var idx = root.editAllowedUnits.indexOf(root.editYAxisLabel);
                    return idx >= 0 ? idx : 0;
                }
                onActivated: function(idx) {
                    if (idx >= 0 && idx < root.editAllowedUnits.length)
                        root.editYAxisLabel = root.editAllowedUnits[idx];

                }
            }

            Controls.Label {
                text: "X-Axis Label:"
            }

            Controls.TextField {
                id: xAxisField

                Layout.fillWidth: true
                placeholderText: "Time (s)"
            }

        }

        Kirigami.Separator {
            Layout.fillWidth: true
        }

        RowLayout {
            Layout.fillWidth: true
            spacing: Kirigami.Units.largeSpacing

            Controls.CheckBox {
                id: showGridCheck

                checked: root.editShowGrid
                text: "Show Grid"
            }

            Controls.CheckBox {
                id: showFillCheck

                checked: root.editShowFill
                text: "Area Gradient Fill"
            }

            Item {
                Layout.fillWidth: true
            }

            Controls.Label {
                text: "Column Span:"
            }

            Controls.SpinBox {
                id: colSpanSpin

                from: 1
                to: 3
                value: root.editColSpan
            }

        }

    }

}
