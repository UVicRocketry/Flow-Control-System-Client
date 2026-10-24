import QtQuick

QtObject {
    id: root

    // --- Inputs from Parent ---
    property string dataSourceMode: "live"
    property string lastHistoryMode: "local"
    property string selectedDataName: ""
    property string loadedDataName: ""
    property var loadedData: null
    property string targetActionData: ""
    // --- Reactive Maps & State ---
    property var externalRawList: []
    property var pendingDeleteMap: ({
    })
    property var renamedDataMap: ({
    })
    // Detect whether the WebSocket (ws) is currently connected
    readonly property bool isWebsocketConnected: {
        if (typeof ws !== "undefined" && ws !== null && ws.isConnected !== undefined)
            return Boolean(ws.isConnected);

        return false;
    }
    readonly property string effectiveDataMode: dataSourceMode === "live" ? lastHistoryMode : dataSourceMode
    readonly property var externalDataList: {
        return externalRawList.filter(function(item) {
            return item !== null && item !== undefined && String(item).trim() !== "";
        }).map(function(item) {
            var strItem = String(item);
            var k = dataKey("external", strItem);
            return renamedDataMap[k] !== undefined ? renamedDataMap[k] : strItem;
        });
    }
    readonly property var activeDataList: {
        var rawList = [];
        if (effectiveDataMode === "local") {
            if (typeof backend !== "undefined" && backend !== null && Array.isArray(backend.localData))
                rawList = backend.localData;
            else
                rawList = ["run_2026_10_19_coldflow.csv", "run_2026_10_18_leakcheck.csv", "telemetry_dump_04.bin", "run_2026_10_12_purge.csv"];
        } else {
            if (!isWebsocketConnected)
                rawList = [];
            else if (typeof backend !== "undefined" && backend !== null && Array.isArray(backend.remoteData))
                rawList = backend.remoteData;
            else
                rawList = [];
        }
        return rawList.filter(function(item) {
            return item !== null && item !== undefined && String(item).trim() !== "";
        }).map(function(item) {
            var strItem = String(item);
            var k = dataKey(effectiveDataMode, strItem);
            return renamedDataMap[k] !== undefined ? renamedDataMap[k] : strItem;
        });
    }

    // --- Helper Functions ---
    function dataKey(mode, name) {
        return mode + ":" + name;
    }

    function dataModeFor(name) {
        if (externalDataList.indexOf(name) !== -1 || externalRawList.indexOf(name) !== -1)
            return "external";

        return effectiveDataMode;
    }

    function isMarkedForDeletion(name) {
        var mode = dataModeFor(name);
        return !!pendingDeleteMap[dataKey(mode, name)];
    }

    function markForDeletion(name) {
        if (!name)
            return ;

        var mode = dataModeFor(name);
        var next = Object.assign({
        }, pendingDeleteMap);
        next[dataKey(mode, name)] = true;
        pendingDeleteMap = next;
        if (typeof backend !== "undefined" && backend !== null && backend.mark_data_for_deletion !== undefined)
            backend.mark_data_for_deletion(mode, name);

    }

    function undoDeletion(name) {
        if (!name)
            return ;

        var mode = dataModeFor(name);
        var next = Object.assign({
        }, pendingDeleteMap);
        delete next[dataKey(mode, name)];
        pendingDeleteMap = next;
        if (typeof backend !== "undefined" && backend !== null && backend.unmark_data_for_deletion !== undefined)
            backend.unmark_data_for_deletion(mode, name);

    }

    function commitPendingDeletions() {
        var keys = Object.keys(pendingDeleteMap);
        for (let i = 0; i < keys.length; i++) {
            let parts = keys[i].split(":");
            let mode = parts[0];
            let filename = parts.slice(1).join(":");
            if (typeof backend !== "undefined" && backend !== null && backend.delete_data !== undefined)
                backend.delete_data(mode, filename);

        }
        pendingDeleteMap = ({
        });
    }

    function applyRename(oldName, newName) {
        var mode = dataModeFor(oldName);
        let next = Object.assign({
        }, renamedDataMap);
        next[dataKey(mode, oldName)] = newName;
        renamedDataMap = next;
        if (selectedDataName === oldName)
            selectedDataName = newName;

        if (loadedDataName === oldName)
            loadedDataName = newName;

        if (typeof backend !== "undefined" && backend !== null && backend.rename_data !== undefined)
            backend.rename_data(mode, oldName, newName);

    }

    function refreshData(mode) {
        if (typeof backend === "undefined" || backend === null)
            return ;

        if (mode === "local" && backend.refresh_local_data !== undefined)
            backend.refresh_local_data();
        else if (mode === "remote" && isWebsocketConnected && backend.refresh_remote_data !== undefined)
            backend.refresh_remote_data();
    }

    function onLoad_data(mode, filePath, data) {
        if (!filePath)
            return ;

        var resolvedMode = mode || dataModeFor(filePath);
        if (resolvedMode === "external") {
            if (externalRawList.indexOf(filePath) === -1 && externalDataList.indexOf(filePath) === -1) {
                var nextExt = externalRawList.slice();
                nextExt.unshift(filePath);
                externalRawList = nextExt;
            }
        }
        selectedDataName = filePath;
        loadedDataName = filePath;
        loadedData = data !== undefined && data !== null ? data : {
            "source": resolvedMode,
            "path": filePath
        };
    }

    function loadSelectedData() {
        if (!selectedDataName)
            return ;

        var mode = dataModeFor(selectedDataName);
        if (typeof backend !== "undefined" && backend !== null && backend.load_data !== undefined)
            backend.load_data(mode, selectedDataName);
        else
            onLoad_data(mode, selectedDataName, null);
    }

    function openSelectedData() {
        // TODO when moved to topbar, use existing entered directory to replace quotes
        if (typeof backend !== "undefined" && backend !== null && backend.open_data !== undefined)
            backend.open_data("");

    }

    function showInFileBrowser() {
        if (typeof backend !== "undefined" && backend !== null && backend.show_in_file_browser !== undefined)
            backend.show_in_file_browser(selectedDataName);

    }

}
