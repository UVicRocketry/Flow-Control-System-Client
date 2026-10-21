import QtQuick

QtObject {
    id: root

    // --- Inputs from Parent ---
    property string dataSourceMode: "live"
    property string lastHistoryMode: "local"
    property string selectedLogName: ""
    property string targetActionLog: ""
    // --- Reactive Maps & State ---
    property var pendingDeleteMap: ({
    })
    property var renamedLogsMap: ({
    })
    // Detect whether the backend WebSocket is currently connected
    readonly property bool isWebsocketConnected: {
        if (typeof backend === "undefined" || backend === null)
            return false;

        if (backend.connected !== undefined)
            return Boolean(backend.connected);

        if (backend.is_connected !== undefined)
            return Boolean(backend.is_connected);

        if (backend.isConnected !== undefined)
            return Boolean(backend.isConnected);

        return false;
    }
    readonly property string effectiveLogMode: dataSourceMode === "live" ? lastHistoryMode : dataSourceMode
    readonly property var activeLogList: {
        var rawList = [];
        if (effectiveLogMode === "local") {
            if (typeof backend !== "undefined" && backend !== null && Array.isArray(backend.localLogs))
                rawList = backend.localLogs;
            else
                rawList = ["run_2026_10_19_coldflow.csv", "run_2026_10_18_leakcheck.csv", "telemetry_dump_04.bin", "run_2026_10_12_purge.log"];
        } else {
            if (!isWebsocketConnected)
                rawList = [];
            else if (typeof backend !== "undefined" && backend !== null && Array.isArray(backend.remoteLogs))
                rawList = backend.remoteLogs;
            else
                rawList = [];
        }
        return rawList.filter(function(item) {
            return item !== null && item !== undefined && String(item).trim() !== "";
        }).map(function(item) {
            var strItem = String(item);
            var k = logKey(effectiveLogMode, strItem);
            return renamedLogsMap[k] !== undefined ? renamedLogsMap[k] : strItem;
        });
    }

    // --- Helper Functions ---
    function logKey(mode, name) {
        return mode + ":" + name;
    }

    function isMarkedForDeletion(name) {
        return !!pendingDeleteMap[logKey(effectiveLogMode, name)];
    }

    function markForDeletion(name) {
        if (!name)
            return ;

        var next = Object.assign({
        }, pendingDeleteMap);
        next[logKey(effectiveLogMode, name)] = true;
        pendingDeleteMap = next;
        if (typeof backend !== "undefined" && backend !== null && backend.mark_log_for_deletion !== undefined)
            backend.mark_log_for_deletion(effectiveLogMode, name);

    }

    function undoDeletion(name) {
        if (!name)
            return ;

        var next = Object.assign({
        }, pendingDeleteMap);
        delete next[logKey(effectiveLogMode, name)];
        pendingDeleteMap = next;
        if (typeof backend !== "undefined" && backend !== null && backend.unmark_log_for_deletion !== undefined)
            backend.unmark_log_for_deletion(effectiveLogMode, name);

    }

    function commitPendingDeletions() {
        var keys = Object.keys(pendingDeleteMap);
        for (let i = 0; i < keys.length; i++) {
            let parts = keys[i].split(":");
            let mode = parts[0];
            let filename = parts.slice(1).join(":");
            if (typeof backend !== "undefined" && backend !== null && backend.delete_log !== undefined)
                backend.delete_log(mode, filename);

        }
        pendingDeleteMap = ({
        });
    }

    function applyRename(oldName, newName) {
        let next = Object.assign({
        }, renamedLogsMap);
        next[logKey(effectiveLogMode, oldName)] = newName;
        renamedLogsMap = next;
        if (selectedLogName === oldName)
            selectedLogName = newName;

        if (typeof backend !== "undefined" && backend !== null && backend.rename_log !== undefined)
            backend.rename_log(effectiveLogMode, oldName, newName);

    }

    function refreshLogs(mode) {
        if (typeof backend === "undefined" || backend === null)
            return ;

        if (mode === "local" && backend.refresh_local_logs !== undefined)
            backend.refresh_local_logs();
        else if (mode === "remote" && isWebsocketConnected && backend.refresh_remote_logs !== undefined)
            backend.refresh_remote_logs();
    }

    function loadSelectedLog() {
        if (typeof backend !== "undefined" && backend !== null && backend.load_log !== undefined)
            backend.load_log(effectiveLogMode, selectedLogName);

    }

    function showInFileBrowser() {
        if (typeof backend !== "undefined" && backend !== null && backend.show_in_file_browser !== undefined)
            backend.show_in_file_browser(selectedLogName);

    }

}
