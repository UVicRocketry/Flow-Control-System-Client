import QtQuick
import QtQuick.Controls as Controls
import QtQuick.Layouts
import org.kde.kirigami as Kirigami

Item {
    id: root

    required property string targetActionData

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

        title: "Rename datafile"
        subtitle: "Enter a new filename for '" + root.targetActionData + "':"
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: {
            var newName = renameField.text.trim();
            if (newName !== "" && newName !== root.targetActionData)
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

        title: "Mark data for deletion?"
        subtitle: "'" + root.targetActionData + "' will be <b>permanently deleted</b> when the session or application closes.<br>You can undo this at any time before closing."
        dialogType: Kirigami.PromptDialog.Warning
        iconName: "dialog-warning"
        standardButtons: Kirigami.Dialog.Ok | Kirigami.Dialog.Cancel
        onAccepted: root.deleteConfirmed()
    }

}
