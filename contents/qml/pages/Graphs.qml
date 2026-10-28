import "./graphs"
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: graphsRoot

    // bound from main.qml / dashboard
    property string dataSourceMode: "live"
    property real windowSeconds: 30
    property bool editLayoutMode: false
    property bool global3StdFilter: false
    // works as loaded file metadata & range slider state
    property string loadedFileName: ""
    property int loadedSampleCount: 0
    property real datasetMinTime: 0
    property real datasetMaxTime: 180
    property bool customSpanActive: false
    property real rangeStart: 0
    property real rangeEnd: 180
    property real placeholderRowHeight: 230
    property var availableChannels: (typeof backend !== "undefined" && backend && backend.available_channels) ? backend.available_channels : []

    function syncLoadedMeta() {
        if (typeof backend === "undefined" || backend === null || !backend.loaded_meta)
            return ;

        var m = backend.loaded_meta;
        graphsRoot.loadedFileName = m.name || "";
        graphsRoot.loadedSampleCount = Number(m.count ?? 0);
        var minT = Number(m.minTime ?? 0);
        var maxT = Number(m.maxTime ?? 180);
        if (maxT <= minT)
            maxT = minT + 30;

        graphsRoot.datasetMinTime = minT;
        graphsRoot.datasetMaxTime = maxT;
        var startT = graphsRoot.windowSeconds >= 99999 ? minT : Math.max(minT, maxT - graphsRoot.windowSeconds);
        graphsRoot.rangeStart = startT;
        graphsRoot.rangeEnd = maxT;
        graphsRoot.customSpanActive = graphsRoot.loadedSampleCount > 0 && graphsRoot.dataSourceMode !== "live";
        timespanSlider.setValues(startT, maxT);
        if (backend.available_channels)
            graphsRoot.availableChannels = backend.available_channels;

    }

    // checks if the loaded log has channels with no corresponding GraphCard and emits an info toast
    function notifyUnshownLoadedData(metaObj) {
        if (typeof backend === "undefined" || !backend || typeof backend.info !== "function")
            return ;

        var m = metaObj || backend.loaded_meta;
        if (!m)
            return ;

        var cols = m.columns || [];
        var count = Number(m.count ?? 0);
        if (count === 0 || cols.length === 0) {
            backend.info("Loaded log has no telemetry data to display.");
            return ;
        }
        var shownChannels = {
        };
        for (let i = 0; i < graphsModel.count; ++i) {
            let ck = String(graphsModel.get(i).channelKey || "");
            if (ck !== "")
                shownChannels[ck] = true;

        }
        var unshown = [];
        var shownCount = 0;
        for (let j = 0; j < cols.length; ++j) {
            let colName = String(cols[j]);
            if (shownChannels[colName])
                shownCount += 1;
            else
                unshown.push(colName);
        }
        if (shownCount === 0)
            backend.info("No present graphs match the loaded log data (" + cols.join(", ") + ").");
        else if (unshown.length > 0)
            backend.info("Loaded log contains unshown data with no present graph: " + unshown.join(", "));
    }

    // computes which row each card belongs to in graphsGrid and syncs cardHeight across every card in the same row
    function syncRowHeights(priorityIndex, explicitHeight) {
        var cols = Math.max(1, graphsGrid.columns);
        var n = graphsModel.count;
        if (n === 0) {
            graphsRoot.placeholderRowHeight = 230;
            return ;
        }
        var rowOfCard = [];
        var cardsInRow = {
        };
        var curRow = 0;
        var curCol = 0;
        for (let i = 0; i < n; ++i) {
            let item = graphsModel.get(i);
            let span = Math.max(1, Math.min(cols, Number(item.colSpan ?? 1)));
            if (curCol + span > cols) {
                curRow += 1;
                curCol = 0;
            }
            rowOfCard.push(curRow);
            if (!cardsInRow[curRow])
                cardsInRow[curRow] = [];

            cardsInRow[curRow].push(i);
            curCol += span;
            if (curCol >= cols) {
                curRow += 1;
                curCol = 0;
            }
        }
        var targetRow = (priorityIndex !== undefined && priorityIndex >= 0 && priorityIndex < n) ? rowOfCard[priorityIndex] : -1;
        for (let rKey in cardsInRow) {
            let indices = cardsInRow[rKey];
            if (!indices || indices.length === 0)
                continue;

            let rowH = 230;
            if (Number(rKey) === targetRow && explicitHeight !== undefined && explicitHeight > 0)
                rowH = explicitHeight;
            else
                rowH = Number(graphsModel.get(indices[0]).cardHeight ?? 230);
            rowH = Math.max(210, rowH);
            for (let k = 0; k < indices.length; ++k) {
                let cIdx = indices[k];
                if (graphsModel.get(cIdx).cardHeight !== rowH)
                    graphsModel.setProperty(cIdx, "cardHeight", rowH);

            }
        }
        // If the Add Graph placeholder card sits on the same row as the last graph card(s), match that row's height
        if (curCol > 0 && curCol < cols && cardsInRow[curRow] && cardsInRow[curRow].length > 0) {
            let lastRowCardIdx = cardsInRow[curRow][0];
            graphsRoot.placeholderRowHeight = Number(graphsModel.get(lastRowCardIdx).cardHeight ?? 230);
        } else {
            graphsRoot.placeholderRowHeight = 230;
        }
    }

    function loadDefaultGraphs() {
        graphsModel.clear();
        var defaults = (typeof backend !== "undefined" && backend && backend.default_graph_cards) ? backend.default_graph_cards : [];
        for (let i = 0; i < defaults.length; ++i) {
            let d = defaults[i];
            graphsModel.append({
                "title": String(d.title ?? d.channelKey ?? "Graph"),
                "channelKey": String(d.channelKey ?? ""),
                "xAxisLabel": String(d.xAxisLabel ?? "Time (s)"),
                "yAxisLabel": String(d.yAxisLabel ?? ""),
                "accentColor": String(d.accentColor ?? "theme:highlight"),
                "autoScale": d.autoScale !== undefined ? Boolean(d.autoScale) : true,
                "manualMinY": Number(d.manualMinY ?? 0),
                "manualMaxY": Number(d.manualMaxY ?? 1000),
                "minYRange": Number(d.minYRange ?? 10),
                "filterOutliers3Std": graphsRoot.global3StdFilter || Boolean(d.filterOutliers3Std ?? false),
                "smoothingWindow": Number(d.smoothingWindow ?? 1),
                "maxBuckets": Number(d.maxBuckets ?? 300),
                "showGrid": d.showGrid !== undefined ? Boolean(d.showGrid) : true,
                "showFill": d.showFill !== undefined ? Boolean(d.showFill) : true,
                "colSpan": Number(d.colSpan ?? 1),
                "cardHeight": Math.max(210, Number(d.cardHeight ?? 230))
            });
        }
        syncRowHeights(-1, 0);
    }

    function addNewGraphCard() {
        var ch = graphsRoot.availableChannels.length > 0 ? graphsRoot.availableChannels[graphsModel.count % graphsRoot.availableChannels.length] : {
            "key": "P_RUN_TANK",
            "title": "New Telemetry Graph",
            "unit": "PSI",
            "color": "theme:highlight"
        };
        graphsModel.append({
            "title": ch.title || ch.key,
            "channelKey": ch.key,
            "xAxisLabel": "Time (s)",
            "yAxisLabel": ch.unit || "PSI",
            "accentColor": ch.color || "theme:highlight",
            "autoScale": true,
            "manualMinY": 0,
            "manualMaxY": 1000,
            "minYRange": 10,
            "filterOutliers3Std": graphsRoot.global3StdFilter,
            "smoothingWindow": 1,
            "maxBuckets": 300,
            "showGrid": true,
            "showFill": true,
            "colSpan": 1,
            "cardHeight": graphsRoot.placeholderRowHeight
        });
        syncRowHeights(graphsModel.count - 1, graphsRoot.placeholderRowHeight);
    }

    spacing: Kirigami.Units.mediumSpacing
    Layout.fillWidth: true
    Layout.fillHeight: true
    Component.onCompleted: {
        loadDefaultGraphs();
        syncLoadedMeta();
    }
    onGlobal3StdFilterChanged: {
        for (let i = 0; i < graphsModel.count; ++i) {
            graphsModel.setProperty(i, "filterOutliers3Std", graphsRoot.global3StdFilter);
        }
    }
    onWindowSecondsChanged: {
        // snap range to most recent [maxTime - windowSeconds, maxTime] when a preset is selected in the sidebar
        if (graphsRoot.dataSourceMode !== "live" && graphsRoot.datasetMaxTime > graphsRoot.datasetMinTime) {
            graphsRoot.customSpanActive = true;
            let endT = graphsRoot.datasetMaxTime;
            let startT = graphsRoot.windowSeconds >= 99999 ? graphsRoot.datasetMinTime : Math.max(graphsRoot.datasetMinTime, endT - graphsRoot.windowSeconds);
            graphsRoot.rangeStart = startT;
            graphsRoot.rangeEnd = endT;
            timespanSlider.setValues(startT, endT);
        } else {
            graphsRoot.customSpanActive = false;
        }
    }

    Connections {
        function onData_loaded(mode, filePath, meta) {
            graphsRoot.syncLoadedMeta();
            if (graphsRoot.dataSourceMode === "live")
                graphsRoot.dataSourceMode = mode === "remote" ? "remote" : "local";

            graphsRoot.notifyUnshownLoadedData(meta);
        }

        function onChannels_changed() {
            if (typeof backend !== "undefined" && backend) {
                graphsRoot.availableChannels = backend.available_channels;
                if (graphsModel.count === 0)
                    graphsRoot.loadDefaultGraphs();

            }
        }

        target: typeof backend !== "undefined" ? backend : null
        ignoreUnknownSignals: true
    }

    ListModel {
        id: graphsModel
    }

    // scrollable grid of GraphCards + add graph button
    Controls.ScrollView {
        id: graphsScroll

        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        rightPadding: 0

        GridLayout {
            id: graphsGrid

            // derive fixed single-column width from scroll view width and column count so cards never warble
            readonly property real singleColumnWidth: {
                var cols = Math.max(1, columns);
                var totalSpacing = (cols - 1) * columnSpacing;
                return Math.max(120, Math.floor((width - totalSpacing) / cols));
            }

            width: graphsScroll.availableWidth
            columns: width < 700 ? 1 : (width < 1080 ? 2 : 3)
            columnSpacing: Kirigami.Units.mediumSpacing
            rowSpacing: Kirigami.Units.mediumSpacing
            onColumnsChanged: graphsRoot.syncRowHeights(-1, 0)

            Repeater {
                model: graphsModel

                GraphCard {
                    cardIndex: index
                    totalCards: graphsModel.count
                    title: model.title
                    channelKey: model.channelKey
                    xAxisLabel: model.xAxisLabel
                    yAxisLabel: model.yAxisLabel
                    accentColor: model.accentColor
                    autoScale: model.autoScale
                    manualMinY: model.manualMinY
                    manualMaxY: model.manualMaxY
                    minYRange: model.minYRange
                    filterOutliers3Std: model.filterOutliers3Std
                    smoothingWindow: model.smoothingWindow
                    maxBuckets: model.maxBuckets
                    showGrid: model.showGrid
                    showFill: model.showFill
                    colSpan: Math.min(graphsGrid.columns, model.colSpan)
                    baseColumnWidth: graphsGrid.singleColumnWidth
                    columnSpacing: graphsGrid.columnSpacing
                    cardHeight: model.cardHeight
                    editLayoutMode: graphsRoot.editLayoutMode
                    dataSourceMode: graphsRoot.dataSourceMode
                    windowSeconds: graphsRoot.windowSeconds
                    useCustomRange: graphsRoot.dataSourceMode !== "live" && graphsRoot.customSpanActive
                    customRangeStart: graphsRoot.rangeStart
                    customRangeEnd: graphsRoot.rangeEnd
                    onEditRequested: function(idx) {
                        var item = graphsModel.get(idx);
                        graphEditModal.openForCard(idx, item, graphsRoot.availableChannels);
                    }
                    onRemoveRequested: function(idx) {
                        if (idx >= 0 && idx < graphsModel.count) {
                            graphsModel.remove(idx);
                            graphsRoot.syncRowHeights(-1, 0);
                        }
                    }
                    onMoveRequested: function(fromIdx, toIdx) {
                        if (fromIdx >= 0 && fromIdx < graphsModel.count && toIdx >= 0 && toIdx < graphsModel.count) {
                            let movedH = graphsModel.get(toIdx).cardHeight;
                            graphsModel.move(fromIdx, toIdx, 1);
                            graphsRoot.syncRowHeights(toIdx, movedH);
                        }
                    }
                    onResizeRequested: function(idx, newSpan, newHeight) {
                        if (idx >= 0 && idx < graphsModel.count) {
                            graphsModel.setProperty(idx, "colSpan", newSpan);
                            graphsRoot.syncRowHeights(idx, newHeight);
                        }
                    }
                }

            }

            // placeholder card to add a new graph
            Kirigami.Card {
                id: addGraphPlaceholderCard

                clip: true
                implicitWidth: graphsGrid.singleColumnWidth
                width: graphsGrid.singleColumnWidth
                Layout.fillWidth: false
                Layout.columnSpan: 1
                Layout.preferredWidth: graphsGrid.singleColumnWidth
                Layout.minimumWidth: graphsGrid.singleColumnWidth
                Layout.maximumWidth: graphsGrid.singleColumnWidth
                Layout.minimumHeight: 210
                Layout.preferredHeight: Math.max(210, graphsRoot.placeholderRowHeight)

                contentItem: Item {
                    Layout.fillWidth: true
                    Layout.fillHeight: true

                    ColumnLayout {
                        anchors.centerIn: parent
                        spacing: Kirigami.Units.smallSpacing

                        Controls.Label {
                            text: "+"
                            font.pixelSize: 48
                            font.bold: true
                            color: addCardMouse.containsMouse ? Kirigami.Theme.highlightColor : Kirigami.Theme.disabledTextColor
                            Layout.alignment: Qt.AlignHCenter
                        }

                        Kirigami.Heading {
                            text: "Add Graph"
                            level: 3
                            color: addCardMouse.containsMouse ? Kirigami.Theme.textColor : Kirigami.Theme.disabledTextColor
                            Layout.alignment: Qt.AlignHCenter
                        }

                        Controls.Label {
                            text: "Click to add a new telemetry graph card"
                            font.pointSize: Kirigami.Theme.smallFont.pointSize
                            color: Kirigami.Theme.disabledTextColor
                            horizontalAlignment: Text.AlignHCenter
                            Layout.alignment: Qt.AlignHCenter
                        }

                    }

                    MouseArea {
                        id: addCardMouse

                        anchors.fill: parent
                        hoverEnabled: true
                        cursorShape: Qt.PointingHandCursor
                        onClicked: graphsRoot.addNewGraphCard()
                    }

                }

            }

        }

        // show vertical scrollbar whenever graphsRoot is visible (supports single or multi-page views)
        Controls.ScrollBar.vertical: Controls.ScrollBar {
            parent: contentStack.parent
            anchors.top: parent.top
            anchors.left: parent.right
            anchors.bottom: parent.bottom
            anchors.leftMargin: Kirigami.Units.smallSpacing
            policy: graphsRoot.visible ? Controls.ScrollBar.AsNeeded : Controls.ScrollBar.AlwaysOff
            enabled: graphsRoot.visible
        }

    }

    // timespan slider (visible when viewing logs / loaded files)
    Kirigami.Card {
        visible: graphsRoot.dataSourceMode !== "live"
        Layout.fillWidth: true

        contentItem: ColumnLayout {
            id: sliderCol

            spacing: 4

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.mediumSpacing

                Kirigami.Icon {
                    source: "measure"
                    Layout.preferredWidth: Kirigami.Units.iconSizes.small
                    Layout.preferredHeight: Kirigami.Units.iconSizes.small
                }

                Controls.Label {
                    text: graphsRoot.loadedFileName !== "" ? ("Log timespan — " + graphsRoot.loadedFileName) : "Log timespan selector"
                    font.bold: true
                    elide: Text.ElideRight
                }

                Controls.Label {
                    text: "Start: " + graphsRoot.rangeStart.toFixed(1) + "s  |  End: " + graphsRoot.rangeEnd.toFixed(1) + "s  |  Span: " + Math.max(0, graphsRoot.rangeEnd - graphsRoot.rangeStart).toFixed(1) + "s"
                    font.family: "monospace"
                    color: Kirigami.Theme.highlightColor
                    elide: Text.ElideRight
                    Layout.fillWidth: true
                }

                Controls.Button {
                    text: "Full range"
                    flat: true
                    onClicked: {
                        graphsRoot.customSpanActive = true;
                        graphsRoot.rangeStart = graphsRoot.datasetMinTime;
                        graphsRoot.rangeEnd = graphsRoot.datasetMaxTime;
                        timespanSlider.setValues(graphsRoot.datasetMinTime, graphsRoot.datasetMaxTime);
                    }
                }

            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Kirigami.Units.smallSpacing

                Controls.Label {
                    text: graphsRoot.datasetMinTime.toFixed(1) + "s"
                    font.family: "monospace"
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    color: Kirigami.Theme.disabledTextColor
                }

                // the actual slider
                Controls.RangeSlider {
                    id: timespanSlider

                    Layout.fillWidth: true
                    from: graphsRoot.datasetMinTime
                    to: Math.max(graphsRoot.datasetMinTime + 1, graphsRoot.datasetMaxTime)
                    first.value: graphsRoot.rangeStart
                    second.value: graphsRoot.rangeEnd
                    first.onMoved: {
                        graphsRoot.customSpanActive = true;
                        graphsRoot.rangeStart = first.value;
                    }
                    second.onMoved: {
                        graphsRoot.customSpanActive = true;
                        graphsRoot.rangeEnd = second.value;
                    }
                }

                Controls.Label {
                    text: graphsRoot.datasetMaxTime.toFixed(1) + "s"
                    font.family: "monospace"
                    font.pointSize: Kirigami.Theme.smallFont.pointSize
                    color: Kirigami.Theme.disabledTextColor
                }

            }

        }

    }

    // modal dialog for editing a GraphCard
    GraphEditDialog {
        id: graphEditModal

        onSettingsApplied: function(idx, cfg) {
            if (idx < 0 || idx >= graphsModel.count)
                return ;

            graphsModel.setProperty(idx, "title", cfg.title);
            graphsModel.setProperty(idx, "channelKey", cfg.channelKey);
            graphsModel.setProperty(idx, "accentColor", cfg.accentColor);
            graphsModel.setProperty(idx, "xAxisLabel", cfg.xAxisLabel);
            graphsModel.setProperty(idx, "yAxisLabel", cfg.yAxisLabel);
            graphsModel.setProperty(idx, "autoScale", cfg.autoScale);
            graphsModel.setProperty(idx, "manualMinY", cfg.manualMinY);
            graphsModel.setProperty(idx, "manualMaxY", cfg.manualMaxY);
            graphsModel.setProperty(idx, "filterOutliers3Std", cfg.filterOutliers3Std);
            graphsModel.setProperty(idx, "smoothingWindow", cfg.smoothingWindow);
            graphsModel.setProperty(idx, "maxBuckets", cfg.maxBuckets);
            graphsModel.setProperty(idx, "showGrid", cfg.showGrid);
            graphsModel.setProperty(idx, "showFill", cfg.showFill);
            graphsModel.setProperty(idx, "colSpan", cfg.colSpan);
            graphsRoot.syncRowHeights(idx, graphsModel.get(idx).cardHeight);
        }
    }

}
