import QtQuick
import org.kde.kirigami as Kirigami

Column {
    id: root

    // Bound to settings/config key ("INFO", "WARN", or "ERR")
    property string minSeverity: "INFO"
    property int defaultDurationMs: 5000
    property int warnDurationMs: 6000
    property int maxVisibleToasts: 5
    property int _nextId: 0

    function severityRank(level) {
        const ranks = {
            "INFO": 0,
            "WARN": 1,
            "ERR": 2
        };
        return ranks[level] !== undefined ? ranks[level] : 0;
    }

    function showToast(level, messageText) {
        if (severityRank(level) < severityRank(minSeverity))
            return ;

        // Enforce maximum visible toast cap: evict the oldest non-ERR toast first
        while (toastModel.count >= maxVisibleToasts) {
            let evictIdx = 0;
            for (let i = 0; i < toastModel.count; i++) {
                if (toastModel.get(i).level !== "ERR") {
                    evictIdx = i;
                    break;
                }
            }
            toastModel.remove(evictIdx);
        }
        toastModel.append({
            "toastId": ++_nextId,
            "level": level,
            "message": messageText,
            "totalMs": level === "ERR" ? 0 : (level === "WARN" ? warnDurationMs : defaultDurationMs)
        });
    }

    function appendLog(level, messageText) {
        showToast(level, messageText);
    }

    function removeToast(id) {
        for (let i = 0; i < toastModel.count; i++) {
            if (toastModel.get(i).toastId === id) {
                toastModel.remove(i);
                break;
            }
        }
    }

    spacing: Kirigami.Units.smallSpacing

    ListModel {
        id: toastModel
    }

    Repeater {
        model: toastModel

        delegate: NotificationToast {
            id: toastDelegate

            // Use `required property var model` to avoid shadowing `level` and `totalMs` on NotificationToast
            required property var model

            width: root.width
            text: model.message
            level: model.level
            totalMs: model.totalMs
            timed: model.level !== "ERR" && model.totalMs > 0
            animateEntryExit: true
            onDismissed: root.removeToast(model.toastId)
            onTimeout: root.removeToast(model.toastId)
        }

    }

    // Smoothly slide remaining toasts up/down when a toast is added or removed
    move: Transition {
        NumberAnimation {
            properties: "y"
            duration: Kirigami.Units.longDuration
            easing.type: Easing.OutCubic
        }

    }

}
