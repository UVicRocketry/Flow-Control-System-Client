import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import QtQuick.Shapes
import org.kde.kirigami as Kirigami

// GPU-accelerated plot area using Scene Graph primitives for axes/grid/crosshair and QtQuick.Shapes for telemetry curves
Item {
    id: root

    required property var tsData
    required property var vsData
    required property var minVsData
    required property var maxVsData
    required property bool hasData
    required property string channelKey
    required property string xAxisLabel
    required property string yAxisLabel
    required property color resolvedColor
    required property bool autoScale
    required property real manualMinY
    required property real manualMaxY
    required property real minYRange
    required property real lineStroke
    required property bool showGrid
    required property bool showFill
    required property real statMin
    required property real statMax
    required property int rawPointCount
    property int bucketCount
    required property real plotTMin
    required property real plotTMax
    required property bool useCustomRange
    required property string dataSourceMode
    // hover crosshair state (rendered via Scene Graph Rectangle primitives)
    property bool isHoveringPlot: false
    property real hoverMouseX: 0
    property real hoverMouseY: 0
    property int hoveredPointIndex: -1
    property real hoverPtX: 0
    property real hoverPtY: 0
    property var screenXs: []
    property var screenYs: []
    property real lastPtX: 0
    property real lastPtY: 0
    property bool hasValidPlotPoints: false
    readonly property real padL: root.yAxisLabel !== "" ? 58 : 44
    readonly property real padR: 14
    readonly property real padT: 10
    readonly property real padB: root.xAxisLabel !== "" ? 32 : 20
    readonly property real plotW: Math.max(0, width - padL - padR)
    readonly property real plotH: Math.max(0, height - padT - padB)
    readonly property var xTickFractions: root.plotW < 180 ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1]
    readonly property var computedYBounds: {
        var minV = root.manualMinY;
        var maxV = root.manualMaxY;
        if (root.autoScale) {
            if (root.hasData) {
                minV = root.statMin;
                maxV = root.statMax;
            } else {
                minV = 0;
                maxV = 100;
            }
            if ((maxV - minV) < root.minYRange) {
                let mid = (minV + maxV) / 2;
                minV = mid - (root.minYRange / 2);
                maxV = mid + (root.minYRange / 2);
            }
            let padSpan = (maxV - minV) * 0.08;
            minV -= padSpan;
            maxV += padSpan;
        }
        return {
            "min": minV,
            "max": maxV,
            "range": Math.max(0.0001, maxV - minV)
        };
    }

    function formatXTickLabel(frac) {
        var t_min = root.plotTMin;
        var dt = Math.max(0.001, root.plotTMax - t_min);
        if (root.useCustomRange || root.dataSourceMode !== "live") {
            let absT = t_min + frac * dt;
            return absT.toFixed(1) + "s";
        }
        let secRemaining = dt * (1 - frac);
        if (frac === 1 || secRemaining < 0.05)
            return "0s";
        if (dt <= 60)
            return "-" + secRemaining.toFixed(0) + "s";
        let mins = Math.floor(secRemaining / 60);
        let remSecs = Math.round(secRemaining % 60);
        return remSecs === 0 ? ("-" + mins + "m") : ("-" + mins + "m" + remSecs + "s");
    }

    function updateHoverPoint() {
        var xs = root.screenXs;
        var ys = root.screenYs;
        var n = xs ? xs.length : 0;
        if (!root.isHoveringPlot || n === 0) {
            root.hoveredPointIndex = -1;
            return ;
        }
        // Binary search on sorted screenXs
        var targetX = root.hoverMouseX;
        var lo = 0;
        var hi = n - 1;
        while (lo < hi) {
            let mid = (lo + hi) >> 1;
            if (xs[mid] < targetX)
                lo = mid + 1;
            else
                hi = mid;
        }
        var bestIdx = lo;
        if (lo > 0 && Math.abs(xs[lo - 1] - targetX) <= Math.abs(xs[lo] - targetX))
            bestIdx = lo - 1;

        root.hoveredPointIndex = bestIdx;
        root.hoverPtX = xs[bestIdx];
        root.hoverPtY = ys[bestIdx];
    }

    function rebuildPlotGeometry() {
        var ts = root.tsData;
        var vs = root.vsData;
        var minVs = root.minVsData;
        var maxVs = root.maxVsData;
        var n = ts ? ts.length : 0;
        var pW = root.plotW;
        var pH = root.plotH;
        if (!root.hasData || width <= 60 || height <= 50 || pW <= 20 || pH <= 20 || n === 0) {
            root.screenXs = [];
            root.screenYs = [];
            root.hasValidPlotPoints = false;
            linePolyline.path = [];
            fillPolyline.path = [];
            envelopePolyline.path = [];
            root.updateHoverPoint();
            return ;
        }

        var bounds = root.computedYBounds;
        var minV = bounds.min;
        var invRange = 1.0 / bounds.range;
        var t_min = root.plotTMin;
        var invDt = 1.0 / Math.max(0.001, root.plotTMax - t_min);
        var pL = root.padL;
        var pT = root.padT;
        var drawEnv = n > 1 && root.rawPointCount > root.bucketCount && minVs && maxVs && minVs.length === n;

        var sXs = new Array(n);
        var sYs = new Array(n);
        var linePts = new Array(n);
        var envPts = drawEnv ? new Array(n * 2 + 1) : [];

        for (let idx = 0; idx < n; ++idx) {
            let normX = (ts[idx] - t_min) * invDt;
            if (normX < 0)
                normX = 0;
            else if (normX > 1)
                normX = 1;
            let lx = normX * pW;

            let normY = (vs[idx] - minV) * invRange;
            if (normY < 0)
                normY = 0;
            else if (normY > 1)
                normY = 1;
            let ly = (1.0 - normY) * pH;

            sXs[idx] = pL + lx;
            sYs[idx] = pT + ly;
            linePts[idx] = Qt.point(lx, ly);

            if (drawEnv) {
                let normMinY = (minVs[idx] - minV) * invRange;
                if (normMinY < 0)
                    normMinY = 0;
                else if (normMinY > 1)
                    normMinY = 1;
                let normMaxY = (maxVs[idx] - minV) * invRange;
                if (normMaxY < 0)
                    normMaxY = 0;
                else if (normMaxY > 1)
                    normMaxY = 1;
                envPts[idx] = Qt.point(lx, (1.0 - normMaxY) * pH);
                envPts[(n * 2 - 1) - idx] = Qt.point(lx, (1.0 - normMinY) * pH);
            }
        }

        if (drawEnv)
            envPts[n * 2] = envPts[0];

        if (root.showFill && n > 1) {
            var fillPts = new Array(n + 3);
            fillPts[0] = Qt.point(linePts[0].x, pH);
            for (let i = 0; i < n; ++i) {
                fillPts[i + 1] = linePts[i];
            }
            fillPts[n + 1] = Qt.point(linePts[n - 1].x, pH);
            fillPts[n + 2] = fillPts[0];
            fillPolyline.path = fillPts;
        } else {
            fillPolyline.path = [];
        }

        envelopePolyline.path = envPts;
        linePolyline.path = n > 1 ? linePts : [];
        root.screenXs = sXs;
        root.screenYs = sYs;
        root.lastPtX = sXs[n - 1];
        root.lastPtY = sYs[n - 1];
        root.hasValidPlotPoints = true;
        root.updateHoverPoint();
    }

    function requestPaint() {
        if (!root.hasData) {
            paintTimer.stop();
            root.screenXs = [];
            root.screenYs = [];
            root.hasValidPlotPoints = false;
            linePolyline.path = [];
            fillPolyline.path = [];
            envelopePolyline.path = [];
            root.hoveredPointIndex = -1;
            return ;
        }
        if (!paintTimer.running)
            paintTimer.start();
    }

    Layout.fillWidth: true
    Layout.fillHeight: true
    Layout.minimumHeight: 110
    onWidthChanged: {
        if (root.hasData && width > 0 && height > 0)
            root.requestPaint();
    }
    onHeightChanged: {
        if (root.hasData && width > 0 && height > 0)
            root.requestPaint();
    }

    Timer {
        id: paintTimer

        interval: 0
        repeat: false
        onTriggered: root.rebuildPlotGeometry()
    }

    // 1. Static/semi-static axes & grid layer (pure Scene Graph Rectangle and Text nodes)
    Item {
        id: axesLayer

        anchors.fill: parent
        visible: root.hasData && root.width > 60 && root.height > 50 && root.plotW > 20 && root.plotH > 20

        // Horizontal grid lines (5 lines: 0%, 25%, 50%, 75%, 100%)
        Repeater {
            model: root.showGrid ? 5 : 0

            Rectangle {
                required property int index

                x: root.padL
                y: Math.round(root.padT + (root.plotH * (index / 4)))
                width: root.plotW
                height: 1
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.1)
            }
        }

        // Vertical grid lines (3 interior lines: 25%, 50%, 75%)
        Repeater {
            model: root.showGrid ? 3 : 0

            Rectangle {
                required property int index

                x: Math.round(root.padL + (root.plotW * ((index + 1) / 4)))
                y: root.padT
                width: 1
                height: root.plotH
                color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.1)
            }
        }

        // Y-axis top tick label (max)
        Text {
            x: root.padL - 6 - implicitWidth
            y: root.padT
            text: root.computedYBounds.max.toFixed(1)
            font.family: "monospace"
            font.pixelSize: 10
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.75)
        }

        // Y-axis middle tick label (mid)
        Text {
            visible: root.plotH >= 65
            x: root.padL - 6 - implicitWidth
            y: root.padT + (root.plotH * 0.5) - (implicitHeight * 0.5)
            text: ((root.computedYBounds.min + root.computedYBounds.max) * 0.5).toFixed(1)
            font.family: "monospace"
            font.pixelSize: 10
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.75)
        }

        // Y-axis bottom tick label (min)
        Text {
            x: root.padL - 6 - implicitWidth
            y: root.padT + root.plotH - implicitHeight
            text: root.computedYBounds.min.toFixed(1)
            font.family: "monospace"
            font.pixelSize: 10
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.75)
        }

        // Rotated Y-axis title
        Text {
            visible: root.yAxisLabel !== ""
            x: 9 - (implicitWidth * 0.5)
            y: root.padT + (root.plotH * 0.5) - (implicitHeight * 0.5)
            text: root.yAxisLabel
            rotation: -90
            font.family: "sans-serif"
            font.pixelSize: 9
            font.bold: true
            color: Qt.rgba(Kirigami.Theme.disabledTextColor.r, Kirigami.Theme.disabledTextColor.g, Kirigami.Theme.disabledTextColor.b, 0.85)
        }

        // Bottom X-axis baseline
        Rectangle {
            x: root.padL
            y: root.padT + root.plotH
            width: root.plotW
            height: 1
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.25)
        }

        // X-axis tick marks & labels
        Repeater {
            model: root.xTickFractions

            Item {
                required property real modelData
                readonly property real tickX: root.padL + (modelData * root.plotW)

                Rectangle {
                    x: Math.round(parent.tickX)
                    y: root.padT + root.plotH
                    width: 1
                    height: 3
                    color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.35)
                }

                Text {
                    x: parent.modelData === 0 ? parent.tickX : (parent.modelData === 1 ? parent.tickX - implicitWidth : parent.tickX - (implicitWidth * 0.5))
                    y: root.padT + root.plotH + 4
                    text: root.formatXTickLabel(parent.modelData)
                    font.family: "monospace"
                    font.pixelSize: 9
                    color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.78)
                }
            }
        }

        // X-axis title
        Text {
            visible: root.xAxisLabel !== ""
            x: root.padL + (root.plotW * 0.5) - (implicitWidth * 0.5)
            y: root.height - implicitHeight - 1
            text: root.xAxisLabel
            font.family: "sans-serif"
            font.pixelSize: 9
            font.bold: true
            color: Qt.rgba(Kirigami.Theme.disabledTextColor.r, Kirigami.Theme.disabledTextColor.g, Kirigami.Theme.disabledTextColor.b, 0.85)
        }
    }

    // 2. Dynamic GPU curve layer: min/max envelope, gradient area fill, and polyline stroke
    Shape {
        id: plotShape

        x: root.padL
        y: root.padT
        width: root.plotW
        height: root.plotH
        clip: true
        visible: root.hasData && root.hasValidPlotPoints
        preferredRendererType: Shape.CurveRenderer

        // Bucket min/max envelope band
        ShapePath {
            strokeColor: "transparent"
            strokeWidth: 0
            fillColor: Qt.rgba(root.resolvedColor.r, root.resolvedColor.g, root.resolvedColor.b, 0.14)

            PathPolyline {
                id: envelopePolyline
            }
        }

        // Area linear gradient fill
        ShapePath {
            strokeColor: "transparent"
            strokeWidth: 0
            fillGradient: LinearGradient {
                x1: 0
                y1: 0
                x2: 0
                y2: root.plotH

                GradientStop {
                    position: 0
                    color: Qt.rgba(root.resolvedColor.r, root.resolvedColor.g, root.resolvedColor.b, 0.24)
                }

                GradientStop {
                    position: 1
                    color: Qt.rgba(root.resolvedColor.r, root.resolvedColor.g, root.resolvedColor.b, 0.0)
                }
            }

            PathPolyline {
                id: fillPolyline
            }
        }

        // Main telemetry polyline stroke
        ShapePath {
            strokeColor: root.resolvedColor
            strokeWidth: root.lineStroke
            fillColor: "transparent"
            capStyle: ShapePath.RoundCap
            joinStyle: ShapePath.RoundJoin

            PathPolyline {
                id: linePolyline
            }
        }
    }

    // Dot on newest point (end of graph)
    Rectangle {
        visible: root.hasData && root.hasValidPlotPoints
        x: root.lastPtX - 2.8
        y: root.lastPtY - 2.8
        width: 5.6
        height: 5.6
        radius: 2.8
        color: root.resolvedColor
    }

    // crosshair overlay renders separate from the rest of the plot
    Item {
        id: crosshairOverlay

        anchors.fill: parent
        visible: root.isHoveringPlot && root.hoveredPointIndex >= 0 && root.hoveredPointIndex < root.screenXs.length

        Rectangle {
            x: Math.round(root.hoverPtX)
            y: root.padT
            width: 1
            height: root.plotH
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.45)
        }

        Rectangle {
            x: root.padL
            y: Math.round(root.hoverPtY)
            width: root.plotW
            height: 1
            color: Qt.rgba(Kirigami.Theme.textColor.r, Kirigami.Theme.textColor.g, Kirigami.Theme.textColor.b, 0.45)
        }

        Rectangle {
            x: root.hoverPtX - 4.5
            y: root.hoverPtY - 4.5
            width: 9
            height: 9
            radius: 4.5
            color: root.resolvedColor
            border.color: "#ffffff"
            border.width: 1.5
        }
    }

    // centered "no data" label styled like addGraphPlaceholderCard when channel has no points
    ColumnLayout {
        anchors.centerIn: parent
        visible: !root.hasData
        spacing: Kirigami.Units.smallSpacing

        Kirigami.Heading {
            text: "No Data"
            level: 3
            color: Kirigami.Theme.disabledTextColor
            Layout.alignment: Qt.AlignHCenter
        }

        Controls.Label {
            text: "No telemetry data for " + (root.channelKey !== "" ? root.channelKey : "this graph")
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            color: Kirigami.Theme.disabledTextColor
            horizontalAlignment: Text.AlignHCenter
            Layout.alignment: Qt.AlignHCenter
        }
    }

    // hover MouseArea for interactive crosshair inspection
    MouseArea {
        anchors.fill: parent
        enabled: root.hasData
        hoverEnabled: true
        acceptedButtons: Qt.NoButton
        onPositionChanged: function(mouse) {
            root.isHoveringPlot = true;
            root.hoverMouseX = mouse.x;
            root.hoverMouseY = mouse.y;
            root.updateHoverPoint();
        }
        onExited: {
            root.isHoveringPlot = false;
            root.hoveredPointIndex = -1;
        }
    }

    // floating crosshair readout pill (bounded strictly inside plot area)
    Rectangle {
        id: hoverPill

        readonly property real plotLeftOffset: root.yAxisLabel !== "" ? 62 : 48
        readonly property real maxAvailableWidth: Math.max(60, parent.width - plotLeftOffset - 18)

        visible: root.isHoveringPlot && root.hoveredPointIndex >= 0 && root.hoveredPointIndex < root.tsData.length
        x: {
            // flip pill to left side of plot when cursor approaches right half so it never obscures the point
            var preferredX = root.hoverMouseX > (parent.width * 0.55) ? plotLeftOffset : (parent.width - width - 16);
            return Math.max(plotLeftOffset, Math.min(parent.width - width - 16, preferredX));
        }
        y: 12
        height: 20
        width: Math.min(hoverLabel.implicitWidth + 12, maxAvailableWidth)
        radius: 4
        color: Qt.rgba(Kirigami.Theme.backgroundColor.r, Kirigami.Theme.backgroundColor.g, Kirigami.Theme.backgroundColor.b, 0.9)
        border.color: root.resolvedColor
        border.width: 1

        Controls.Label {
            id: hoverLabel

            anchors.fill: parent
            anchors.leftMargin: 6
            anchors.rightMargin: 6
            verticalAlignment: Text.AlignVCenter
            elide: Text.ElideRight
            font.family: "monospace"
            font.pointSize: Kirigami.Theme.smallFont.pointSize
            text: {
                if (root.hoveredPointIndex < 0 || root.hoveredPointIndex >= root.tsData.length)
                    return "";

                var tVal = root.tsData[root.hoveredPointIndex];
                var vVal = root.vsData[root.hoveredPointIndex];
                return "t=" + Number(tVal).toFixed(2) + "s | " + Number(vVal).toFixed(2) + (root.yAxisLabel !== "" ? " " + root.yAxisLabel : "");
            }
        }
    }
}
