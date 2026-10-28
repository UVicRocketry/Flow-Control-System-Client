import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Kirigami.Dialog {
    id: root

    property int targetIndex: -1
    property var availableChannels: []
    // editable fields passed to graph cards
    property string editTitle: ""
    property string editChannelKey: ""
    property string editColor: "theme:highlight"
    property string editXAxisLabel: "Time (s)"
    property string editYAxisLabel: "PSI"
    property bool editAutoScale: true
    property real editManualMinY: 0
    property real editManualMaxY: 1000
    property bool editFilterOutliers3Std: false
    property int editSmoothingWindow: 1
    property int editMaxBuckets: 300
    property bool editShowGrid: true
    property bool editShowFill: true
    property int editColSpan: 1
    // colours
    readonly property var themeColorPalette: [{
        "key": "theme:highlight",
        "label": "Theme Highlight"
    }, {
        "key": "theme:positive",
        "label": "Theme Positive"
    }, {
        "key": "theme:neutral",
        "label": "Theme Neutral"
    }, {
        "key": "theme:negative",
        "label": "Theme Negative"
    }, {
        "key": "theme:active",
        "label": "Theme Active"
    }, {
        "key": "theme:link",
        "label": "Theme Link"
    }, {
        "key": "theme:visited",
        "label": "Theme Visited"
    }]
    readonly property var fixedColorPalette: ["#3daee9", "#2ecc71", "#e67e22", "#e74c3c", "#f39c12", "#9b59b6", "#1abc9c", "#e84393"]

    signal settingsApplied(int index, var updatedConfig)

    function resolveThemeColor(key) {
        if (key === "theme:highlight")
            return Kirigami.Theme.highlightColor;

        if (key === "theme:positive")
            return Kirigami.Theme.positiveTextColor;

        if (key === "theme:neutral")
            return Kirigami.Theme.neutralTextColor;

        if (key === "theme:negative")
            return Kirigami.Theme.negativeTextColor;

        if (key === "theme:active")
            return Kirigami.Theme.activeTextColor;

        if (key === "theme:link")
            return Kirigami.Theme.linkColor;

        if (key === "theme:visited")
            return Kirigami.Theme.visitedLinkColor;

        if (key === "theme:text")
            return Kirigami.Theme.textColor;

        return key;
    }

    function openForCard(index, cardData, channels) {
        root.targetIndex = index;
        root.availableChannels = channels || [];
        root.editTitle = cardData.title || "";
        root.editChannelKey = cardData.channelKey || "P_RUN_TANK";
        root.editColor = String(cardData.accentColor || "theme:highlight");
        root.editXAxisLabel = cardData.xAxisLabel !== undefined ? cardData.xAxisLabel : "Time (s)";
        root.editYAxisLabel = cardData.yAxisLabel !== undefined ? cardData.yAxisLabel : "PSI";
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
        yAxisField.text = root.editYAxisLabel;
        minYField.text = String(root.editManualMinY);
        maxYField.text = String(root.editManualMaxY);
        root.open();
    }

    title: "Configure Graph Card"
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
            "yAxisLabel": yAxisField.text,
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

                        if (ch.unit !== undefined)
                            yAxisField.text = ch.unit;

                        if (ch.color) {
                            root.editColor = ch.color;
                            colorHexField.text = ch.color;
                        }
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
                    model: root.themeColorPalette

                    Rectangle {
                        required property var modelData

                        width: 24
                        height: 24
                        radius: 6
                        color: root.resolveThemeColor(modelData.key)
                        border.width: colorHexField.text.toLowerCase() === modelData.key.toLowerCase() ? 2 : 1
                        border.color: colorHexField.text.toLowerCase() === modelData.key.toLowerCase() ? Kirigami.Theme.textColor : Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.25)
                        Controls.ToolTip.visible: themeSwatchArea.containsMouse
                        Controls.ToolTip.text: modelData.label + " (" + modelData.key + ")"

                        MouseArea {
                            id: themeSwatchArea

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.editColor = modelData.key;
                                colorHexField.text = modelData.key;
                            }
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
                    model: root.fixedColorPalette

                    Rectangle {
                        required property string modelData

                        width: 24
                        height: 24
                        radius: 12
                        color: modelData
                        border.width: colorHexField.text.toLowerCase() === modelData.toLowerCase() ? 2 : 1
                        border.color: colorHexField.text.toLowerCase() === modelData.toLowerCase() ? Kirigami.Theme.textColor : "transparent"
                        Controls.ToolTip.visible: fixedSwatchArea.containsMouse
                        Controls.ToolTip.text: modelData

                        MouseArea {
                            id: fixedSwatchArea

                            anchors.fill: parent
                            hoverEnabled: true
                            cursorShape: Qt.PointingHandCursor
                            onClicked: {
                                root.editColor = modelData;
                                colorHexField.text = modelData;
                            }
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
                text: "Y-Axis Label:"
            }

            Controls.TextField {
                id: yAxisField

                Layout.fillWidth: true
                placeholderText: "PSI / °C / lbf"
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
