import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// plot canvas area with telemetry data, interactive crosshair, and hover readout pill
Item {
    id: root

    required property var history
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
    // hover crosshair state (rendered via Scene Graph Rectangle primitives, zero Canvas repaints on hover)
    property bool isHoveringPlot: false
    property real hoverMouseX: 0
    property real hoverMouseY: 0
    property int hoveredPointIndex: -1
    property real hoverPtX: 0
    property real hoverPtY: 0
    property var screenPoints: []
    property string _lastAxesKey: ""
    readonly property real padL: root.yAxisLabel !== "" ? 58 : 44
    readonly property real padR: 14
    readonly property real padT: 10
    readonly property real padB: root.xAxisLabel !== "" ? 32 : 20
    readonly property real plotW: Math.max(0, width - padL - padR)
    readonly property real plotH: Math.max(0, height - padT - padB)
    readonly property var computedYBounds: {
        var minV = root.manualMinY;
        var maxV = root.manualMaxY;
        if (root.autoScale) {
            if (root.history.length > 0) {
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

    function updateHoverPoint() {
        var pts = root.screenPoints;
        if (!root.isHoveringPlot || !pts || pts.length === 0) {
            root.hoveredPointIndex = -1;
            return ;
        }
        var bestIdx = -1;
        var bestDist = 999999;
        for (let i = 0; i < pts.length; ++i) {
            let d = Math.abs(pts[i].x - root.hoverMouseX);
            if (d < bestDist) {
                bestDist = d;
                bestIdx = i;
            }
        }
        root.hoveredPointIndex = bestIdx;
        if (bestIdx >= 0 && bestIdx < pts.length) {
            root.hoverPtX = pts[bestIdx].x;
            root.hoverPtY = pts[bestIdx].y;
        }
    }

    function requestAxesPaintIfNeeded() {
        if (!root.hasData)
            return ;

        var bounds = root.computedYBounds;
        if (!bounds)
            return ;

        var dt = Math.max(0.001, root.plotTMax - root.plotTMin);
        var xKey = (root.useCustomRange || root.dataSourceMode !== "live") ? (root.plotTMin.toFixed(2) + ":" + root.plotTMax.toFixed(2)) : dt.toFixed(2);
        var tc = Kirigami.Theme.textColor;
        var key = [Math.round(width), Math.round(height), bounds.min.toFixed(1), bounds.max.toFixed(1), root.showGrid ? 1 : 0, root.xAxisLabel, root.yAxisLabel, root.useCustomRange ? 1 : 0, root.dataSourceMode, xKey, tc.r.toFixed(2), tc.g.toFixed(2), tc.b.toFixed(2)].join("|");
        if (key !== root._lastAxesKey) {
            root._lastAxesKey = key;
            if (!axesPaintTimer.running)
                axesPaintTimer.start();

        }
    }

    function requestPaint() {
        if (!root.hasData) {
            axesPaintTimer.stop();
            paintTimer.stop();
            root._lastAxesKey = "";
            root.screenPoints = [];
            root.hoveredPointIndex = -1;
            return ;
        }
        requestAxesPaintIfNeeded();
        if (!paintTimer.running)
            paintTimer.start();

    }

    Layout.fillWidth: true
    Layout.fillHeight: true
    Layout.minimumHeight: 110

    Timer {
        id: axesPaintTimer

        interval: 0
        repeat: false
        onTriggered: {
            if (root.hasData)
                axesCanvas.requestPaint();

        }
    }

    Timer {
        id: paintTimer

        interval: 0
        repeat: false
        onTriggered: {
            if (root.hasData)
                canvas.requestPaint();

        }
    }

    // static layer: grid lines, axis ticks, and labels (repaints only on resize, Y-scale, or range changes)
    Canvas {
        id: axesCanvas

        anchors.fill: parent
        visible: root.hasData
        onWidthChanged: {
            if (root.hasData && width > 0 && height > 0)
                root.requestPaint();

        }
        onHeightChanged: {
            if (root.hasData && width > 0 && height > 0)
                root.requestPaint();

        }
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            if (!root.hasData || width <= 60 || height <= 50)
                return ;

            var padL = root.padL;
            var padT = root.padT;
            var plotW = root.plotW;
            var plotH = root.plotH;
            if (plotW <= 20 || plotH <= 20)
                return ;

            var bounds = root.computedYBounds;
            if (!bounds)
                return ;

            var minV = bounds.min;
            var maxV = bounds.max;
            var textColor = Kirigami.Theme.textColor;
            var disabledColor = Kirigami.Theme.disabledTextColor;
            // 1. horizontal & vertical grid lines
            if (root.showGrid) {
                ctx.strokeStyle = Qt.rgba(textColor.r, textColor.g, textColor.b, 0.1);
                ctx.lineWidth = 1;
                ctx.beginPath();
                for (let g = 0; g <= 4; ++g) {
                    let gy = padT + (plotH * (g / 4));
                    ctx.moveTo(padL, gy);
                    ctx.lineTo(padL + plotW, gy);
                }
                for (let vg = 1; vg < 4; ++vg) {
                    let vx = padL + (plotW * (vg / 4));
                    ctx.moveTo(vx, padT);
                    ctx.lineTo(vx, padT + plotH);
                }
                ctx.stroke();
            }
            // 2. y-axis tick labels and rotated y-axis label
            ctx.fillStyle = Qt.rgba(textColor.r, textColor.g, textColor.b, 0.75);
            ctx.font = "10px monospace";
            ctx.textAlign = "right";
            ctx.textBaseline = "top";
            ctx.fillText(maxV.toFixed(1), padL - 6, padT);
            if (plotH >= 65) {
                ctx.textBaseline = "middle";
                ctx.fillText(((minV + maxV) / 2).toFixed(1), padL - 6, padT + plotH * 0.5);
            }
            ctx.textBaseline = "bottom";
            ctx.fillText(minV.toFixed(1), padL - 6, padT + plotH);
            if (root.yAxisLabel !== "") {
                ctx.save();
                ctx.translate(9, padT + plotH * 0.5);
                ctx.rotate(-Math.PI / 2);
                ctx.textAlign = "center";
                ctx.textBaseline = "top";
                ctx.font = "bold 9px sans-serif";
                ctx.fillStyle = Qt.rgba(disabledColor.r, disabledColor.g, disabledColor.b, 0.85);
                ctx.fillText(root.yAxisLabel, 0, 0);
                ctx.restore();
            }
            // 3. horizontal axis line & ticks (bottom)
            var t_min = root.plotTMin;
            var t_max = root.plotTMax;
            var dt = Math.max(0.001, t_max - t_min);
            ctx.strokeStyle = Qt.rgba(textColor.r, textColor.g, textColor.b, 0.25);
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(padL, padT + plotH);
            ctx.lineTo(padL + plotW, padT + plotH);
            ctx.stroke();
            ctx.fillStyle = Qt.rgba(textColor.r, textColor.g, textColor.b, 0.78);
            ctx.font = "9px monospace";
            ctx.textBaseline = "top";
            var fractions = plotW < 180 ? [0, 0.5, 1] : [0, 0.25, 0.5, 0.75, 1];
            for (let fIdx = 0; fIdx < fractions.length; ++fIdx) {
                let frac = fractions[fIdx];
                let tx = padL + frac * plotW;
                ctx.strokeStyle = Qt.rgba(textColor.r, textColor.g, textColor.b, 0.35);
                ctx.beginPath();
                ctx.moveTo(tx, padT + plotH);
                ctx.lineTo(tx, padT + plotH + 3);
                ctx.stroke();
                let labelText = "";
                if (root.useCustomRange || root.dataSourceMode !== "live") {
                    let absT = t_min + frac * dt;
                    labelText = absT.toFixed(1) + "s";
                } else {
                    let secRemaining = dt * (1 - frac);
                    if (frac === 1 || secRemaining < 0.05) {
                        labelText = "0s";
                    } else if (dt <= 60) {
                        labelText = "-" + secRemaining.toFixed(0) + "s";
                    } else {
                        let mins = Math.floor(secRemaining / 60);
                        let remSecs = Math.round(secRemaining % 60);
                        labelText = remSecs === 0 ? ("-" + mins + "m") : ("-" + mins + "m" + remSecs + "s");
                    }
                }
                if (frac === 0)
                    ctx.textAlign = "left";
                else if (frac === 1)
                    ctx.textAlign = "right";
                else
                    ctx.textAlign = "center";
                ctx.fillText(labelText, tx, padT + plotH + 4);
            }
            if (root.xAxisLabel !== "") {
                ctx.textAlign = "center";
                ctx.textBaseline = "bottom";
                ctx.font = "bold 9px sans-serif";
                ctx.fillStyle = Qt.rgba(disabledColor.r, disabledColor.g, disabledColor.b, 0.85);
                ctx.fillText(root.xAxisLabel, padL + plotW * 0.5, height - 1);
            }
        }
    }

    // dynamic data layer: draws only the min/max envelope, gradient fill, polyline, and latest dot
    Canvas {
        id: canvas

        anchors.fill: parent
        visible: root.hasData
        onPaint: {
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            var n = root.history.length;
            if (width <= 60 || height <= 50 || n === 0) {
                root.screenPoints = [];
                root.updateHoverPoint();
                return ;
            }
            var padL = root.padL;
            var padT = root.padT;
            var plotW = root.plotW;
            var plotH = root.plotH;
            if (plotW <= 20 || plotH <= 20)
                return ;

            var bounds = root.computedYBounds;
            if (!bounds)
                return ;

            var minV = bounds.min;
            var range = bounds.range;
            var accent = root.resolvedColor;
            var t_min = root.plotTMin;
            var dt = Math.max(0.001, root.plotTMax - t_min);
            // map bucketed points to screen coordinates
            var pts = [];
            for (let idx = 0; idx < n; ++idx) {
                let pt = root.history[idx];
                let normX = (pt.t - t_min) / dt;
                let px = padL + Math.max(0, Math.min(1, normX)) * plotW;
                let normY = (pt.v - minV) / range;
                let py = padT + (1 - Math.max(0, Math.min(1, normY))) * plotH;
                let minPy = py;
                let maxPy = py;
                if (pt.minV !== undefined && pt.maxV !== undefined && pt.count > 1) {
                    let normMinY = (pt.minV - minV) / range;
                    let normMaxY = (pt.maxV - minV) / range;
                    minPy = padT + (1 - Math.max(0, Math.min(1, normMinY))) * plotH;
                    maxPy = padT + (1 - Math.max(0, Math.min(1, normMaxY))) * plotH;
                }
                pts.push({
                    "x": px,
                    "y": py,
                    "minY": minPy,
                    "maxY": maxPy,
                    "t": pt.t,
                    "v": pt.v,
                    "count": pt.count ?? 1
                });
            }
            root.screenPoints = pts;
            root.updateHoverPoint();
            if (pts.length === 0)
                return ;

            ctx.save();
            ctx.beginPath();
            ctx.rect(padL, padT, plotW, plotH);
            ctx.clip();
            // 7. bucket min/max envelope band (when downsampling large datasets)
            var rCol = Math.round(accent.r * 255);
            var gCol = Math.round(accent.g * 255);
            var bCol = Math.round(accent.b * 255);
            if (pts.length > 1 && root.rawPointCount > root.bucketCount) {
                ctx.beginPath();
                for (let e1 = 0; e1 < pts.length; ++e1) {
                    if (e1 === 0)
                        ctx.moveTo(pts[e1].x, pts[e1].maxY);
                    else
                        ctx.lineTo(pts[e1].x, pts[e1].maxY);
                }
                for (let e2 = pts.length - 1; e2 >= 0; --e2) {
                    ctx.lineTo(pts[e2].x, pts[e2].minY);
                }
                ctx.closePath();
                ctx.fillStyle = "rgba(" + rCol + "," + gCol + "," + bCol + ", 0.14)";
                ctx.fill();
            }
            // 8. area gradient fill
            if (root.showFill && pts.length > 1) {
                let grad = ctx.createLinearGradient(0, padT, 0, padT + plotH);
                grad.addColorStop(0, "rgba(" + rCol + "," + gCol + "," + bCol + ", 0.24)");
                grad.addColorStop(1, "rgba(" + rCol + "," + gCol + "," + bCol + ", 0.0)");
                ctx.beginPath();
                ctx.moveTo(pts[0].x, padT + plotH);
                for (let p = 0; p < pts.length; ++p) {
                    ctx.lineTo(pts[p].x, pts[p].y);
                }
                ctx.lineTo(pts[pts.length - 1].x, padT + plotH);
                ctx.closePath();
                ctx.fillStyle = grad;
                ctx.fill();
            }
            // 9. line stroke
            ctx.beginPath();
            ctx.strokeStyle = accent;
            ctx.lineWidth = root.lineStroke;
            for (let s = 0; s < pts.length; ++s) {
                if (s === 0)
                    ctx.moveTo(pts[s].x, pts[s].y);
                else
                    ctx.lineTo(pts[s].x, pts[s].y);
            }
            ctx.stroke();
            // 10. dot on newest point (end of graph)
            var last = pts[pts.length - 1];
            ctx.beginPath();
            ctx.arc(last.x, last.y, 2.8, 0, 2 * Math.PI);
            ctx.fillStyle = accent;
            ctx.fill();
            // end rendering loop
            ctx.restore();
        }
    }

    // crosshair overlay renders separate from the rest of the canvas
    Item {
        id: crosshairOverlay

        anchors.fill: parent
        visible: root.isHoveringPlot && root.hoveredPointIndex >= 0 && root.hoveredPointIndex < root.screenPoints.length

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

        visible: root.isHoveringPlot && root.hoveredPointIndex >= 0 && root.hoveredPointIndex < root.history.length
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
                if (root.hoveredPointIndex < 0 || root.hoveredPointIndex >= root.history.length)
                    return "";

                var pt = root.history[root.hoveredPointIndex];
                return "t=" + Number(pt.t).toFixed(2) + "s | " + Number(pt.v).toFixed(2) + (root.yAxisLabel !== "" ? " " + root.yAxisLabel : "");
            }
        }

    }

}
