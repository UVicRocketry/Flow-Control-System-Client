import QtQuick
import org.kde.kirigami as Kirigami

// Shared theme-color resolver and palette definitions for GraphCard and GraphEditDialog
QtObject {
    id: root

    readonly property var themeColorPalette: [{
        "key": "theme:highlight",
        "label": "Theme Highlight"
    }, {
        "key": "theme:positive",
        "label": "Theme Positive"
    }, {
        "key": "theme:neutral",
        "label": "Theme Neutral"
    }, {
        "key": "theme:negative",
        "label": "Theme Negative"
    }, {
        "key": "theme:active",
        "label": "Theme Active"
    }, {
        "key": "theme:link",
        "label": "Theme Link"
    }, {
        "key": "theme:visited",
        "label": "Theme Visited"
    }]

    readonly property var fixedColorPalette: ["#3daee9", "#2ecc71", "#e67e22", "#e74c3c", "#f39c12", "#9b59b6", "#1abc9c", "#e84393"]

    function resolve(accentColor) {
        var key = String(accentColor || "theme:highlight");
        if (key === "theme:highlight")
            return Kirigami.Theme.highlightColor;
        if (key === "theme:positive")
            return Kirigami.Theme.positiveTextColor;
        if (key === "theme:neutral")
            return Kirigami.Theme.neutralTextColor;
        if (key === "theme:negative")
            return Kirigami.Theme.negativeTextColor;
        if (key === "theme:active")
            return Kirigami.Theme.activeTextColor;
        if (key === "theme:link")
            return Kirigami.Theme.linkColor;
        if (key === "theme:visited")
            return Kirigami.Theme.visitedLinkColor;
        if (key === "theme:text")
            return Kirigami.Theme.textColor;
        return key;
    }
}
