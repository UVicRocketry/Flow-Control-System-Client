import "./sidebar"
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

ColumnLayout {
    id: root

    property string activePageName: "dashboard"
    // list of currently visible page names in the main view area (supports single StackLayout or multi-page side-by-side layouts)
    property var visiblePages: [activePageName]
    property int unreadNotificationCount: 0
    property string timeScalePreset: "30s"
    property int customWindowSeconds: 45
    property bool smoothAllActive: false
    property bool editLayoutActive: false
    readonly property real effectiveWindowSeconds: {
        if (timeScalePreset === "30s")
            return 30;

        if (timeScalePreset === "1m")
            return 60;

        if (timeScalePreset === "3m")
            return 180;

        return Math.max(5, Number(customWindowSeconds));
    }

    signal navigateRequested(string pageName)
    signal settingsRequested()
    signal notificationsRequested()
    signal timeScaleChanged(real seconds)

    // returns true whenever the specified page is currently visible on screen
    function isPageVisible(pageName) {
        if (root.visiblePages && root.visiblePages.length > 0) {
            for (let i = 0; i < root.visiblePages.length; ++i) {
                if (root.visiblePages[i] === pageName)
                    return true;

            }
            return false;
        }
        return root.activePageName === pageName;
    }

    spacing: Kirigami.Units.smallSpacing
    Layout.fillWidth: true
    Layout.fillHeight: true

    // top view navigation list
    SidebarNavList {
        activePageName: root.activePageName
        visiblePages: root.visiblePages
        onNavigateRequested: function(pageName) {
            root.activePageName = pageName;
            root.navigateRequested(pageName);
        }
    }

    // view-specific helpers (each is shown when its corresponding view is visible, supporting multiple views open at once)
    DashboardViewHelper {
        visible: root.isPageVisible("dashboard")
    }

    ActuatorsViewHelper {
        visible: root.isPageVisible("actuators")
    }

    GraphsViewHelper {
        visible: root.isPageVisible("graphs")
        timeScalePreset: root.timeScalePreset
        customWindowSeconds: root.customWindowSeconds
        effectiveWindowSeconds: root.effectiveWindowSeconds
        smoothAllActive: root.smoothAllActive
        editLayoutActive: root.editLayoutActive
        onPresetSelected: function(preset) {
            root.timeScalePreset = preset;
            root.timeScaleChanged(root.effectiveWindowSeconds);
        }
        onCustomSecondsModified: function(seconds) {
            root.customWindowSeconds = seconds;
            root.timeScaleChanged(root.effectiveWindowSeconds);
        }
        onSmoothAllToggled: function(active) {
            root.smoothAllActive = active;
        }
        onEditLayoutToggled: function(active) {
            root.editLayoutActive = active;
        }
    }

    // bottom spacer
    Item {
        Layout.fillHeight: true
    }

    // bottom bar: settings (bottom-left) and notification tray (bottom-right)
    SidebarBottomBar {
        unreadNotificationCount: root.unreadNotificationCount
        onSettingsRequested: root.settingsRequested()
        onNotificationsRequested: root.notificationsRequested()
    }

}
