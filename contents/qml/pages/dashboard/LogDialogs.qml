import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: root

    required property string targetActionLog

    signal renameConfirmed(string newName)
    signal deleteConfirmed()

    function openRename(initialName) {
        renameField.text = initialName;
        renameDialog.open();
    }

    function openDeleteConfirm() {
        deleteConfirmDialog.open();
    }

    Kirigami.PromptDialog {
        id: renameDialog

        title: "Rename logfile"
        subtitle: "Enter a new filename for '" + root.targetActionLog + "':"
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: {
            var newName = renameField.text.trim();
            if (newName !== "" && newName !== root.targetActionLog)
                root.renameConfirmed(newName);

        }

        Controls.TextField {
            id: renameField

            Layout.fillWidth: true
            placeholderText: "New filename..."
            onAccepted: renameDialog.accept()
        }

    }

    Kirigami.PromptDialog {
        id: deleteConfirmDialog

        title: "Mark log for deletion?"
        subtitle: "'" + root.targetActionLog + "' will be <b>permanently deleted</b> when the session or application closes.<br>You can undo this at any time before closing."
        dialogType: Kirigami.PromptDialog.Warning
        iconName: "dialog-warning"
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: root.deleteConfirmed()
    }

}
