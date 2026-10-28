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
    required property int bucketCount
    required property real plotTMin
    required property real plotTMax
    required property bool useCustomRange
    required property string dataSourceMode
    // hover crosshair state
    property bool isHoveringPlot: false
    property real hoverMouseX: 0
    property real hoverMouseY: 0
    property int hoveredPointIndex: -1

    function requestPaint() {
        canvas.requestPaint();
    }

    clip: true
    Layout.fillWidth: true
    Layout.fillHeight: true
    Layout.minimumHeight: 110

    Canvas {
        id: canvas

        anchors.fill: parent
        opacity: root.hasData ? 1 : 0.32
        onWidthChanged: {
            if (width > 0 && height > 0)
                requestPaint();

        }
        onHeightChanged: {
            if (width > 0 && height > 0)
                requestPaint();

        }
        onPaint: {
            // begin rendering loop
            var ctx = getContext("2d");
            ctx.clearRect(0, 0, width, height);
            var n = root.history.length;
            if (width <= 60 || height <= 50)
                return ;

            var hasYLabel = root.yAxisLabel !== "";
            var hasXLabel = root.xAxisLabel !== "";
            var padL = hasYLabel ? 58 : 44;
            var padR = 14;
            var padT = 10;
            var padB = hasXLabel ? 32 : 20;
            var plotW = width - padL - padR;
            var plotH = height - padT - padB;
            if (plotW <= 20 || plotH <= 20)
                return ;

            // 1. compute y min & max (autoscale vs manual)
            var minV = root.manualMinY;
            var maxV = root.manualMaxY;
            if (root.autoScale) {
                if (n > 0) {
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
            var range = maxV - minV;
            if (range <= 0.0001)
                range = 1;

            var textColor = Kirigami.Theme.textColor;
            var disabledColor = Kirigami.Theme.disabledTextColor;
            var accent = root.resolvedColor;
            // 2. horizontal & vertical grid lines
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
            // 3. y-axis tick labels and rotated y-axis label
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
            if (hasYLabel) {
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
            // 4. time window parameters (horizontal axis)
            var t_min = root.plotTMin;
            var t_max = root.plotTMax;
            var dt = Math.max(0.001, t_max - t_min);
            // 5. horizontal axis line & ticks (bottom)
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
            // x-axis label positioned below tick numbers with non-overlapping margin
            if (hasXLabel) {
                ctx.textAlign = "center";
                ctx.textBaseline = "bottom";
                ctx.font = "bold 9px sans-serif";
                ctx.fillStyle = Qt.rgba(disabledColor.r, disabledColor.g, disabledColor.b, 0.85);
                ctx.fillText(root.xAxisLabel, padL + plotW * 0.5, height - 1);
            }
            // 6. map bucketed points to screen coordinates (clipped to plot rect)
            var pts = [];
            var bestHoverIdx = -1;
            var bestHoverDist = 999999;
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
                if (root.isHoveringPlot) {
                    let d = Math.abs(px - root.hoverMouseX);
                    if (d < bestHoverDist) {
                        bestHoverDist = d;
                        bestHoverIdx = idx;
                    }
                }
            }
            root.hoveredPointIndex = bestHoverIdx;
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
            // 11. render crosshair if hovering
            if (root.isHoveringPlot && bestHoverIdx >= 0 && bestHoverIdx < pts.length) {
                let hPt = pts[bestHoverIdx];
                ctx.strokeStyle = Qt.rgba(textColor.r, textColor.g, textColor.b, 0.45);
                ctx.lineWidth = 1;
                ctx.beginPath();
                ctx.moveTo(hPt.x, padT);
                ctx.lineTo(hPt.x, padT + plotH);
                ctx.moveTo(padL, hPt.y);
                ctx.lineTo(padL + plotW, hPt.y);
                ctx.stroke();
                ctx.beginPath();
                ctx.arc(hPt.x, hPt.y, 4.5, 0, 2 * Math.PI);
                ctx.fillStyle = accent;
                ctx.fill();
                ctx.lineWidth = 1.5;
                ctx.strokeStyle = "#ffffff";
                ctx.stroke();
            }
            // end rendering loop
            ctx.restore();
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
            canvas.requestPaint();
        }
        onExited: {
            root.isHoveringPlot = false;
            root.hoveredPointIndex = -1;
            canvas.requestPaint();
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
        clip: true
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
