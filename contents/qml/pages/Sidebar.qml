import "./sidebar"
import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

// persistent left sidebar hosting page navigation, contextual view helpers, settings, and notifications
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
    property bool keybindsEnabled: false
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
    signal openInLeftRequested(string pageName)
    signal openInRightRequested(string pageName)
    signal openInNewWindowRequested(string pageName)
    signal settingsRequested()
    signal notificationsRequested()
    signal timeScaleChanged(real seconds)
    signal abortRequested()

    // returns true whenever the specified page is currently visible on screen
    function isPageVisible(pageName) {
        if (root.visiblePages && root.visiblePages.length > 0)
            return root.visiblePages.indexOf(pageName) !== -1;

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
            root.navigateRequested(pageName);
        }
        onOpenInLeftRequested: function(pageName) {
            root.openInLeftRequested(pageName);
        }
        onOpenInRightRequested: function(pageName) {
            root.openInRightRequested(pageName);
        }
        onOpenInNewWindowRequested: function(pageName) {
            root.openInNewWindowRequested(pageName);
        }
    }

    // Scrollable region for view-specific helpers so split-view & popout helpers never clip or overflow
    Controls.ScrollView {
        Layout.fillWidth: true
        Layout.fillHeight: true
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: Kirigami.Units.smallSpacing

            ActuatorsViewHelper {
                visible: root.isPageVisible("actuators")
                keybindsEnabled: root.keybindsEnabled
                onAbortRequested: root.abortRequested()
                onKeybindsToggled: function(enabled) {
                    root.keybindsEnabled = enabled;
                }
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

        }

    }

    // bottom bar: settings (bottom-left) and notification tray (bottom-right)
    SidebarBottomBar {
        unreadNotificationCount: root.unreadNotificationCount
        onSettingsRequested: root.settingsRequested()
        onNotificationsRequested: root.notificationsRequested()
    }

}
