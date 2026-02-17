"""Utility helpers for folder selection/removal dialogs."""

from __future__ import annotations

from pathlib import Path
from typing import List, Optional, Tuple

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QRadioButton,
    QTreeWidget,
    QVBoxLayout,
)

MATCH_EXACT = "exact"
MATCH_PARTIAL = "partial"


class FolderNameDeleteDialog(QDialog):
    """Small dialog to capture folder name deletion criteria."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("フォルダ削除（名前指定）")
        self.setModal(True)
        self.setMinimumWidth(360)

        layout = QVBoxLayout(self)

        instructions = QLabel("削除するフォルダ名を入力し、照合方法を選択してください。")
        instructions.setWordWrap(True)
        layout.addWidget(instructions)

        self.name_edit = QLineEdit()
        self.name_edit.setPlaceholderText("例: Project01")
        layout.addWidget(self.name_edit)

        match_layout = QHBoxLayout()
        match_layout.addWidget(QLabel("照合方法:"))

        self.exact_radio = QRadioButton("完全一致")
        self.partial_radio = QRadioButton("部分一致")
        self.partial_radio.setChecked(True)

        match_layout.addWidget(self.exact_radio)
        match_layout.addWidget(self.partial_radio)
        match_layout.addStretch()
        layout.addLayout(match_layout)

        self.button_box = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        layout.addWidget(self.button_box)

        # Disable OK until text is entered
        ok_button = self.button_box.button(QDialogButtonBox.Ok)
        if ok_button:
            ok_button.setEnabled(False)
        self.name_edit.textChanged.connect(lambda text: ok_button.setEnabled(bool(text.strip())) if ok_button else None)

        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)

        self.name_edit.setFocus(Qt.OtherFocusReason)

    def get_query(self) -> str:
        """Return the trimmed folder name query."""
        return self.name_edit.text().strip()

    def get_match_mode(self) -> str:
        """Return the selected match mode identifier."""
        return MATCH_EXACT if self.exact_radio.isChecked() else MATCH_PARTIAL


def remove_folders_matching_query(
    folder_tree: QTreeWidget,
    selected_paths: Optional[List[Path]],
    query: str,
    *,
    match_mode: str,
    case_sensitive: bool = False,
) -> List[Path]:
    """Remove top-level folders whose names match the query.

    Args:
        folder_tree: The tree widget containing top-level folder items.
        selected_paths: Optional list mirroring the folders; items found will be removed from it.
        query: The search string typed by the user.
        match_mode: Either ``MATCH_EXACT`` or ``MATCH_PARTIAL``.
        case_sensitive: When True, comparisons keep case sensitivity.

    Returns:
        A list of Path objects that were removed from the tree.
    """

    if not query:
        return []

    normalized_query = query if case_sensitive else query.lower()
    matches: List[Tuple[int, Path]] = []

    for index in range(folder_tree.topLevelItemCount()):
        item = folder_tree.topLevelItem(index)
        if item is None:
            continue
        path_str = item.data(0, Qt.UserRole)
        if not path_str:
            continue

        path_obj = Path(path_str)
        folder_name = path_obj.name if case_sensitive else path_obj.name.lower()

        if match_mode == MATCH_EXACT and folder_name == normalized_query:
            matches.append((index, path_obj))
        elif match_mode == MATCH_PARTIAL and normalized_query in folder_name:
            matches.append((index, path_obj))

    if not matches:
        return []

    # Remove from tree/backing list in reverse order to keep indexes valid
    for index, path_obj in reversed(matches):
        folder_tree.takeTopLevelItem(index)
        if selected_paths is not None and path_obj in selected_paths:
            selected_paths.remove(path_obj)

    # Preserve original order in return value
    return [path for _, path in matches]


__all__ = [
    "FolderNameDeleteDialog",
    "MATCH_EXACT",
    "MATCH_PARTIAL",
    "remove_folders_matching_query",
]
