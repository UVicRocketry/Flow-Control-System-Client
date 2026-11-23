import QtQuick

// state and backend bridge helper for Dashboard data file lists, selection, renames, and deferred deletions
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
    property var pendingDeleteMap: ({
    })
    // Detect whether the WebSocket (ws) is currently connected
    readonly property bool isWebsocketConnected: {
        if (typeof ws !== "undefined" && ws !== null && ws.isConnected !== undefined)
            return Boolean(ws.isConnected);

        return false;
    }
    readonly property string effectiveDataMode: dataSourceMode === "live" ? lastHistoryMode : dataSourceMode
    readonly property var externalDataList: (typeof backend !== "undefined" && backend) ? backend.external_data : []
    readonly property var activeDataList: {
        if (typeof backend === "undefined" || !backend)
            return [];

        if (effectiveDataMode === "local")
            return backend.local_data;

        return isWebsocketConnected ? backend.remote_data : [];
    }

    // --- Helper Functions ---
    function dataKey(mode, name) {
        return mode + ":" + name;
    }

    function dataModeFor(name) {
        return externalDataList.indexOf(name) !== -1 ? "external" : effectiveDataMode;
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
    }

    function undoDeletion(name) {
        if (!name)
            return ;

        var mode = dataModeFor(name);
        var next = Object.assign({
        }, pendingDeleteMap);
        delete next[dataKey(mode, name)];
        pendingDeleteMap = next;
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
        if (typeof backend === "undefined" || backend === null || !backend.rename_data(mode, oldName, newName))
            return ;
        if (selectedDataName === oldName)
            selectedDataName = newName;

        if (loadedDataName === oldName)
            loadedDataName = newName;
    }

    function downloadSelectedData() {
        if (!selectedDataName)
            return ;

        if (typeof backend !== "undefined" && backend !== null && backend.download_remote_data !== undefined)
            backend.download_remote_data(selectedDataName);
    }

    function pushSelectedData() {
        if (!selectedDataName)
            return ;

        var mode = dataModeFor(selectedDataName);
        if (typeof backend !== "undefined" && backend !== null && backend.push_data_to_remote !== undefined)
            backend.push_data_to_remote(mode, selectedDataName);
    }

    function refreshData(mode) {
        if (typeof backend === "undefined" || backend === null)
            return ;

        if (mode === "local" && backend.refresh_local_data !== undefined)
            backend.refresh_local_data();
        else if (mode === "remote" && isWebsocketConnected && backend.refresh_remote_data !== undefined)
            backend.refresh_remote_data();
    }

    function hideExternalData(name) {
        if (!name)
            return ;

        if (typeof backend !== "undefined" && backend !== null && backend.hide_external_data !== undefined)
            backend.hide_external_data(name);

        if (selectedDataName === name)
            selectedDataName = "";
    }

    function onLoad_data(mode, filePath, data) {
        if (!filePath)
            return ;

        var resolvedMode = mode || dataModeFor(filePath);
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

    }

    function openSelectedData() {
        if (typeof backend !== "undefined" && backend !== null && backend.open_data !== undefined)
            backend.open_data("");

    }

}
