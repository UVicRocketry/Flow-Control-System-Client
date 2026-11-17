import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// self-contained telemetry graph card combining header, plot canvas, statistics footer, and resize handles
Kirigami.Card {
    id: root

    // modifiable by the user / Graphs.qml
    property int cardIndex: 0
    property int totalCards: 1
    property string channelKey: "P_RUN_TANK"
    property string title: "Runtank Pressure"
    property string xAxisLabel: "Time (s)"
    property string yAxisLabel: "PSI"
    property string accentColor: "theme:highlight"
    property bool autoScale: true
    property real manualMinY: 0
    property real manualMaxY: 1000
    property real lineStroke: 1.75
    property real minYRange: 10
    property bool filterOutliers3Std: false
    property int smoothingWindow: 1
    property int maxBuckets: 300
    property bool showGrid: true
    property bool showFill: true
    readonly property GraphColorHelper colorHelper: GraphColorHelper {
    }
    // theme-aware resolved colour (updates automatically when Kirigami.Theme changes)
    readonly property color resolvedColor: colorHelper.resolve(root.accentColor)
    // layout & resizing properties (fixedCardWidth locks card width to colSpan so content changes never cause warbling)
    property bool editLayoutMode: false
    property int colSpan: 1
    property real cardHeight: 230
    property real baseColumnWidth: Kirigami.Units.gridUnit * 13
    property real columnSpacing: Kirigami.Units.mediumSpacing
    readonly property int effectiveColSpan: Math.max(1, Math.min(3, root.colSpan))
    readonly property real fixedCardWidth: (root.baseColumnWidth * effectiveColSpan) + (root.columnSpacing * (effectiveColSpan - 1))
    // time window & mode inputs (given by sidebar)
    property string dataSourceMode: "live"
    property real windowSeconds: 30
    property bool useCustomRange: false
    property real customRangeStart: 0
    property real customRangeEnd: 30
    // computed / queried state
    property var tsData: []
    property var vsData: []
    property var minVsData: []
    property var maxVsData: []
    readonly property bool hasData: root.tsData.length > 0
    property real statMin: 0
    property real statMax: 100
    property real statMean: 0
    property real currentValue: 0
    property int rawPointCount: 0
    property int bucketCount: 0
    property real plotTMin: 0
    property real plotTMax: 30
    property bool _ready: false
    property bool _staleWhileOffscreen: true

    signal editRequested(int index)
    signal removeRequested(int index)
    signal moveRequested(int fromIndex, int toIndex)
    signal resizeRequested(int index, int newColSpan, real newHeight)

    function applyChannelData(res) {
        if (res && res.ts !== undefined) {
            root.tsData = res.ts;
            root.vsData = res.vs;
            root.minVsData = res.minVs;
            root.maxVsData = res.maxVs;
            root.statMin = Number(res.min ?? 0);
            root.statMax = Number(res.max ?? 100);
            root.statMean = Number(res.mean ?? 0);
            root.currentValue = Number(res.latest ?? 0);
            root.rawPointCount = Number(res.rawCount ?? 0);
            root.bucketCount = Number(res.bucketCount ?? 0);
            root.plotTMin = Number(res.tMin ?? 0);
            root.plotTMax = Number(res.tMax ?? 30);
        }
        plotCanvas.requestPaint();
    }

    function refreshFromBackend() {
        if (!root.visible) {
            root._staleWhileOffscreen = true;
            return ;
        }
        if (typeof backend === "undefined" || backend === null || typeof backend.get_channel_data !== "function" || root.channelKey === "") {
            plotCanvas.requestPaint();
            return ;
        }
        root._staleWhileOffscreen = false;
        // pass negative windowSeconds when using preset trailing windows so backend slices most recent samples
        var tStartArg = root.useCustomRange ? root.customRangeStart : -root.windowSeconds;
        var tEndArg = root.useCustomRange ? root.customRangeEnd : -1;
        var res = backend.get_channel_data(root.dataSourceMode, root.channelKey, tStartArg, tEndArg, root.maxBuckets, root.filterOutliers3Std, root.smoothingWindow);
        root.applyChannelData(res);
    }

    implicitWidth: fixedCardWidth
    width: fixedCardWidth
    Layout.fillWidth: false
    Layout.columnSpan: effectiveColSpan
    Layout.preferredWidth: fixedCardWidth
    Layout.minimumWidth: fixedCardWidth
    Layout.maximumWidth: fixedCardWidth
    Layout.minimumHeight: 210
    Layout.preferredHeight: Math.max(210, root.cardHeight)
    Component.onCompleted: {
        root._ready = true;
    }
    onChannelKeyChanged: {
        if (root._ready)
            refreshFromBackend();

    }
    onFilterOutliers3StdChanged: {
        if (root._ready)
            refreshFromBackend();

    }
    onSmoothingWindowChanged: {
        if (root._ready)
            refreshFromBackend();

    }
    onMaxBucketsChanged: {
        if (root._ready)
            refreshFromBackend();

    }
    onAutoScaleChanged: plotCanvas.requestPaint()
    onManualMinYChanged: plotCanvas.requestPaint()
    onManualMaxYChanged: plotCanvas.requestPaint()
    onShowFillChanged: plotCanvas.requestPaint()

    header: GraphCardHeader {
        cardIndex: root.cardIndex
        totalCards: root.totalCards
        title: root.title
        channelKey: root.channelKey
        yAxisLabel: root.yAxisLabel
        resolvedColor: root.resolvedColor
        filterOutliers3Std: root.filterOutliers3Std
        smoothingWindow: root.smoothingWindow
        hasData: root.hasData
        currentValue: root.currentValue
        editLayoutMode: root.editLayoutMode
        onEditRequested: function(idx) {
            root.editRequested(idx);
        }
        onRemoveRequested: function(idx) {
            root.removeRequested(idx);
        }
        onMoveRequested: function(fromIdx, toIdx) {
            root.moveRequested(fromIdx, toIdx);
        }
    }

    contentItem: Item {
        Layout.fillWidth: true
        Layout.fillHeight: true
        Layout.minimumHeight: 135

        ColumnLayout {
            anchors.fill: parent
            spacing: 4

            GraphCanvas {
                id: plotCanvas

                tsData: root.tsData
                vsData: root.vsData
                minVsData: root.minVsData
                maxVsData: root.maxVsData
                hasData: root.hasData
                channelKey: root.channelKey
                xAxisLabel: root.xAxisLabel
                yAxisLabel: root.yAxisLabel
                resolvedColor: root.resolvedColor
                autoScale: root.autoScale
                manualMinY: root.manualMinY
                manualMaxY: root.manualMaxY
                minYRange: root.minYRange
                lineStroke: root.lineStroke
                showGrid: root.showGrid
                showFill: root.showFill
                statMin: root.statMin
                statMax: root.statMax
                rawPointCount: root.rawPointCount
                bucketCount: root.bucketCount
                plotTMin: root.plotTMin
                plotTMax: root.plotTMax
                useCustomRange: root.useCustomRange
                dataSourceMode: root.dataSourceMode
            }

            GraphCardFooter {
                hasData: root.hasData
                statMin: root.statMin
                statMax: root.statMax
                statMean: root.statMean
            }

        }

        GraphResizeHandles {
            cardIndex: root.cardIndex
            colSpan: root.colSpan
            cardHeight: root.cardHeight
            baseColumnWidth: root.baseColumnWidth
            resolvedColor: root.resolvedColor
            editLayoutMode: root.editLayoutMode
            onResizeRequested: function(idx, newSpan, newHeight) {
                root.resizeRequested(idx, newSpan, newHeight);
            }
        }

    }

}
