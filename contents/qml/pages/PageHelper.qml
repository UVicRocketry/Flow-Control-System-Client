import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// Manages inline single/split view panes, lazy page loading, popout windows, and the split tab bar
Item {
    id: pageHelperRoot

    // Properties supplied by the main window (toolbar / WebSocket / sidebar state)
    property bool keybindsEnabled: false
    property bool isWebsocketConnected: false
    property real windowSeconds: 30
    property bool global3StdFilter: false
    property bool editLayoutMode: false
    // Page layout & popout window state
    property string leftPageName: "dashboard"
    property string rightPageName: ""
    property string focusedPane: "left"
    property real splitRatio: 0.5
    property var poppedOutPages: ({
    })
    property var popoutWindows: ({
    })
    readonly property var pageOrder: ["dashboard", "actuators", "graphs", "video"]
    readonly property var pageMeta: ({
        "dashboard": {
            "title": "Data sources",
            "icon": "computer",
            "minWidth": Kirigami.Units.gridUnit * 34
        },
        "actuators": {
            "title": "Valve actuators",
            "icon": "network-wired",
            "minWidth": Kirigami.Units.gridUnit * 24
        },
        "graphs": {
            "title": "Graphs",
            "icon": "utilities-system-monitor",
            "minWidth": Kirigami.Units.gridUnit * 24
        },
        "video": {
            "title": "Video",
            "icon": "camera-video",
            "minWidth": Kirigami.Units.gridUnit * 24
        }
    })
    readonly property bool splitViewActive: rightPageName !== ""
    readonly property string activeInlinePage: (focusedPane === "right" && splitViewActive) ? rightPageName : leftPageName
    readonly property real availableSplitWidth: Math.max(1, splitGrid.width - (splitViewActive ? splitGrid.columnSpacing : 0))
    readonly property real leftPaneTargetWidth: {
        if (!splitViewActive)
            return availableSplitWidth;

        let leftMin = pageMinWidthFor(leftPageName);
        let rightMin = pageMinWidthFor(rightPageName);
        let maxLeft = Math.max(leftMin, availableSplitWidth - rightMin);
        return Math.max(leftMin, Math.min(maxLeft, Math.round(availableSplitWidth * splitRatio)));
    }
    readonly property real rightPaneTargetWidth: {
        if (!splitViewActive)
            return 0;

        let rightMin = pageMinWidthFor(rightPageName);
        return Math.max(rightMin, availableSplitWidth - leftPaneTargetWidth);
    }
    readonly property real minimumRequiredWidth: {
        let leftMin = pageMinWidthFor(leftPageName);
        if (!splitViewActive)
            return leftMin + Kirigami.Units.gridUnit;

        return leftMin + pageMinWidthFor(rightPageName) + (Kirigami.Units.gridUnit * 1.5);
    }
    readonly property var visiblePages: {
        let left = leftPageName;
        let right = rightPageName;
        let popped = poppedOutPages;
        let pages = [];
        for (let i = 0; i < pageOrder.length; ++i) {
            let p = pageOrder[i];
            if (left === p || right === p || !!popped[p])
                pages.push(p);

        }
        return pages;
    }
    readonly property var actuatorsPage: actuatorsPageLoader.item ?? actuatorsPageLoader
    readonly property var graphsPage: graphsPageLoader.item ?? graphsPageLoader
    readonly property var videoPage: videoPageLoader.item ?? videoPageLoader

    function pageTitleFor(pageName) {
        return (pageMeta[pageName] && pageMeta[pageName].title) || "";
    }

    function pageIconFor(pageName) {
        return (pageMeta[pageName] && pageMeta[pageName].icon) || "";
    }

    function pageMinWidthFor(pageName) {
        return (pageMeta[pageName] && pageMeta[pageName].minWidth) || (Kirigami.Units.gridUnit * 24);
    }

    function pageContainerFor(pageName) {
        if (pageName === "dashboard")
            return dashboardPage;

        if (pageName === "actuators")
            return actuatorsPageLoader;

        if (pageName === "graphs")
            return graphsPageLoader;

        if (pageName === "video")
            return videoPageLoader;

        return null;
    }

    function ensurePageLoaded(pageName) {
        if (pageName === "actuators")
            actuatorsPageLoader.active = true;
        else if (pageName === "graphs")
            graphsPageLoader.active = true;
        else if (pageName === "video")
            videoPageLoader.active = true;
    }

    function pickDefaultRightPage(excludeName) {
        for (let i = 0; i < pageOrder.length; ++i) {
            if (pageOrder[i] !== excludeName && !poppedOutPages[pageOrder[i]])
                return pageOrder[i];

        }
        for (let i = 0; i < pageOrder.length; ++i) {
            if (pageOrder[i] !== excludeName)
                return pageOrder[i];

        }
        return "";
    }

    function syncPagePlacements() {
        for (let i = 0; i < pageOrder.length; ++i) {
            let name = pageOrder[i];
            let container = pageContainerFor(name);
            if (!container)
                continue;

            if (poppedOutPages[name] && popoutWindows[name]) {
                ensurePageLoaded(name);
                container.parent = popoutWindows[name].hostLayout;
                container.visible = true;
            } else if (leftPageName === name) {
                ensurePageLoaded(name);
                container.parent = leftPaneFrame.pageHost;
                container.visible = true;
            } else if (rightPageName === name) {
                ensurePageLoaded(name);
                container.parent = rightPaneFrame.pageHost;
                container.visible = true;
            } else {
                container.visible = false;
                container.parent = hiddenPagesPool;
            }
        }
    }

    function navigateInline(pageName) {
        if (splitViewActive && focusedPane === "right")
            openPageInRightPanel(pageName);
        else
            openPageInLeftPanel(pageName);
    }

    function openPageInLeftPanel(pageName) {
        if (rightPageName === pageName) {
            let prevLeft = leftPageName;
            leftPageName = pageName;
            rightPageName = prevLeft;
        } else {
            leftPageName = pageName;
        }
        focusedPane = "left";
        syncPagePlacements();
    }

    function openPageInRightPanel(pageName) {
        if (leftPageName === pageName) {
            if (rightPageName !== "") {
                let prevRight = rightPageName;
                rightPageName = pageName;
                leftPageName = prevRight;
            } else {
                leftPageName = pickDefaultRightPage(pageName);
                rightPageName = pageName;
            }
        } else {
            rightPageName = pageName;
        }
        focusedPane = "right";
        syncPagePlacements();
    }

    function openPageInNewWindow(pageName) {
        if (!pageName)
            return ;

        if (poppedOutPages[pageName] && popoutWindows[pageName]) {
            let existingWin = popoutWindows[pageName];
            existingWin.show();
            existingWin.raise();
            existingWin.requestActivate();
            return ;
        }
        ensurePageLoaded(pageName);
        let win = popoutWindowComponent.createObject(popoutWindowsOwner, {
            "pageName": pageName,
            "pageTitle": pageTitleFor(pageName)
        });
        if (!win)
            return ;

        win.returnRequested.connect(function(returnedName) {
            pageHelperRoot.returnPoppedOutPage(returnedName);
        });
        let nextWins = Object.assign({
        }, popoutWindows);
        nextWins[pageName] = win;
        popoutWindows = nextWins;
        let nextPopped = Object.assign({
        }, poppedOutPages);
        nextPopped[pageName] = true;
        poppedOutPages = nextPopped;
        syncPagePlacements();
        win.show();
    }

    function returnPoppedOutPage(pageName) {
        if (!poppedOutPages[pageName])
            return ;

        let nextPopped = Object.assign({
        }, poppedOutPages);
        delete nextPopped[pageName];
        poppedOutPages = nextPopped;
        syncPagePlacements();
        let win = popoutWindows[pageName];
        if (win) {
            let nextWins = Object.assign({
            }, popoutWindows);
            delete nextWins[pageName];
            popoutWindows = nextWins;
            win.hide();
            win.destroy();
        }
    }

    function closeAllPopouts() {
        let keys = Object.keys(popoutWindows);
        for (let i = 0; i < keys.length; ++i) returnPoppedOutPage(keys[i])
    }

    function toggleSplitView() {
        if (splitViewActive) {
            rightPageName = "";
            focusedPane = "left";
        } else {
            let candidate = pickDefaultRightPage(leftPageName);
            if (candidate)
                rightPageName = candidate;

        }
        syncPagePlacements();
    }

    function swapSplitPanes() {
        if (!splitViewActive)
            return ;

        let prevLeftRatio = leftPaneTargetWidth / availableSplitWidth;
        let tmp = leftPageName;
        leftPageName = rightPageName;
        rightPageName = tmp;
        splitRatio = 1 - prevLeftRatio;
        focusedPane = focusedPane === "left" ? "right" : "left";
        syncPagePlacements();
    }

    function collapseSplitTo(remainingPage) {
        if (!splitViewActive)
            return ;

        leftPageName = remainingPage;
        rightPageName = "";
        focusedPane = "left";
        syncPagePlacements();
    }

    function closeLeftPane() {
        collapseSplitTo(rightPageName);
    }

    function closeRightPane() {
        collapseSplitTo(leftPageName);
    }

    Component.onCompleted: syncPagePlacements()

    QtObject {
        id: popoutWindowsOwner
    }

    Component {
        id: popoutWindowComponent

        PopoutWindow {
        }

    }

    // Off-screen pool holding inactive views so they keep state without being destroyed
    Item {
        id: hiddenPagesPool

        visible: false

        Dashboard {
            id: dashboardPage
        }

        Loader {
            id: actuatorsPageLoader

            Layout.fillWidth: true
            Layout.fillHeight: true
            asynchronous: true
            active: false

            sourceComponent: Actuators {
                id: actuatorsPage

                keybindsEnabled: pageHelperRoot.keybindsEnabled
                isWebsocketConnected: pageHelperRoot.isWebsocketConnected
                inLeftSplitPane: pageHelperRoot.splitViewActive && pageHelperRoot.leftPageName === "actuators" && !pageHelperRoot.poppedOutPages["actuators"]
            }

        }

        Loader {
            id: graphsPageLoader

            Layout.fillWidth: true
            Layout.fillHeight: true
            asynchronous: true
            active: false

            sourceComponent: Graphs {
                id: graphsPage

                windowSeconds: pageHelperRoot.windowSeconds
                global3StdFilter: pageHelperRoot.global3StdFilter
                editLayoutMode: pageHelperRoot.editLayoutMode
                dataSourceMode: dashboardPage.dataSourceMode
                inLeftSplitPane: pageHelperRoot.splitViewActive && pageHelperRoot.leftPageName === "graphs" && !pageHelperRoot.poppedOutPages["graphs"]
            }

        }

        Loader {
            id: videoPageLoader

            Layout.fillWidth: true
            Layout.fillHeight: true
            asynchronous: true
            active: false

            sourceComponent: Video {
                id: videoPage
            }

        }

    }

    // Pass-through focus overlay spanning full PageHelper bounds (including right-margin scrollbars)
    MouseArea {
        z: 999
        width: pageHelperRoot.width
        height: pageHelperRoot.height
        acceptedButtons: Qt.AllButtons
        hoverEnabled: false
        propagateComposedEvents: true
        onPressed: function(mouse) {
            if (pageHelperRoot.splitViewActive) {
                let rightStartX = splitGrid.x + rightPaneFrame.x;
                pageHelperRoot.focusedPane = (mouse.x >= rightStartX) ? "right" : "left";
            } else {
                pageHelperRoot.focusedPane = "left";
            }
            mouse.accepted = false;
        }
    }

    // Hover-revealed resize handlebar positioned in the vertical seam between the two split panes/tabs
    SplitResizeHandle {
        id: splitResizeHandle

        visible: pageHelperRoot.splitViewActive
        z: 1000
        y: splitGrid.y
        width: Math.max(splitGrid.columnSpacing, 10)
        height: splitGrid.height
        seamCenterX: splitGrid.x + leftPaneFrame.x + leftPaneFrame.width + (splitGrid.columnSpacing / 2)
        availableWidth: pageHelperRoot.availableSplitWidth
        leftMinWidth: pageHelperRoot.pageMinWidthFor(pageHelperRoot.leftPageName)
        rightMinWidth: pageHelperRoot.pageMinWidthFor(pageHelperRoot.rightPageName)
        leftTargetWidth: pageHelperRoot.leftPaneTargetWidth
        splitRatio: pageHelperRoot.splitRatio
        onRatioChanged: function(newRatio) {
            pageHelperRoot.splitRatio = newRatio;
        }
    }

    ColumnLayout {
        width: pageHelperRoot.width
        height: pageHelperRoot.height
        spacing: 0

        GridLayout {
            id: splitGrid

            Layout.fillWidth: true
            Layout.fillHeight: true
            Layout.margins: Kirigami.Units.gridUnit / 2
            columns: pageHelperRoot.splitViewActive ? 2 : 1
            columnSpacing: Kirigami.Units.gridUnit / 2
            rowSpacing: Kirigami.Units.gridUnit / 2

            SplitPaneFrame {
                id: leftPaneFrame

                pageName: pageHelperRoot.leftPageName
                pageTitle: pageHelperRoot.pageTitleFor(pageHelperRoot.leftPageName)
                pageIcon: pageHelperRoot.pageIconFor(pageHelperRoot.leftPageName)
                poppedOut: !!pageHelperRoot.poppedOutPages[pageHelperRoot.leftPageName]
                splitViewActive: pageHelperRoot.splitViewActive
                minimumPaneWidth: pageHelperRoot.pageMinWidthFor(pageHelperRoot.leftPageName)
                preferredPaneWidth: pageHelperRoot.leftPaneTargetWidth
                onReturnRequested: function(pageName) {
                    pageHelperRoot.returnPoppedOutPage(pageName);
                }
            }

            SplitPaneFrame {
                id: rightPaneFrame

                visible: pageHelperRoot.splitViewActive
                pageName: pageHelperRoot.rightPageName
                pageTitle: pageHelperRoot.pageTitleFor(pageHelperRoot.rightPageName)
                pageIcon: pageHelperRoot.pageIconFor(pageHelperRoot.rightPageName)
                poppedOut: !!pageHelperRoot.poppedOutPages[pageHelperRoot.rightPageName]
                splitViewActive: pageHelperRoot.splitViewActive
                minimumPaneWidth: pageHelperRoot.pageMinWidthFor(pageHelperRoot.rightPageName)
                preferredPaneWidth: pageHelperRoot.rightPaneTargetWidth
                onReturnRequested: function(pageName) {
                    pageHelperRoot.returnPoppedOutPage(pageName);
                }
            }

            SplitTabBar {
                visible: pageHelperRoot.splitViewActive
                paneSide: "left"
                pageTitle: pageHelperRoot.pageTitleFor(pageHelperRoot.leftPageName)
                focused: pageHelperRoot.focusedPane === "left"
                preferredTabWidth: pageHelperRoot.leftPaneTargetWidth
                onSwapRequested: pageHelperRoot.swapSplitPanes()
                onCloseRequested: pageHelperRoot.closeLeftPane()
                onFocusRequested: pageHelperRoot.focusedPane = "left"
            }

            SplitTabBar {
                visible: pageHelperRoot.splitViewActive
                paneSide: "right"
                pageTitle: pageHelperRoot.pageTitleFor(pageHelperRoot.rightPageName)
                focused: pageHelperRoot.focusedPane === "right"
                preferredTabWidth: pageHelperRoot.rightPaneTargetWidth
                onSwapRequested: pageHelperRoot.swapSplitPanes()
                onCloseRequested: pageHelperRoot.closeRightPane()
                onFocusRequested: pageHelperRoot.focusedPane = "right"
            }

        }

    }

    Timer {
        id: warmupTimer

        interval: 400
        running: true
        repeat: false
        onTriggered: {
            graphsPageLoader.active = true;
            actuatorsPageLoader.active = true;
            videoPageLoader.active = true;
        }
    }

}
