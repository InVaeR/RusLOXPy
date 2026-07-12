from typing import Dict

from PySide6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QTableWidget,
    QTableWidgetItem, QHeaderView, QMessageBox, QDialog, QListWidget,
    QListWidgetItem, QDialogButtonBox, QFileDialog, QLabel, QLineEdit,
    QStackedWidget, QMenu, QInputDialog,
)
from pathlib import Path

from PySide6.QtGui import QShortcut, QKeySequence
from PySide6.QtCore import Qt
from services.watchlist import WatchListManager
from data.repository import Repository
from core.process_scanner import list_running_apps
from ui.components.empty_state import EmptyState
from ui.components.app_icons import get_app_icon, asset_pixmap
from ui.components.app_item_delegate import AppItemDelegate
from ui.theme import PALETTE as C
from utils.format import fmt_duration


class AddAppDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Добавить приложение")
        self.setMinimumSize(560, 480)
        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Выберите из запущенных процессов:"))
        search_row = QHBoxLayout()
        self.search_edit = QLineEdit(self)
        self.search_edit.setPlaceholderText("Поиск...")
        self.search_edit.textChanged.connect(self._filter_apps)
        search_row.addWidget(self.search_edit, 1)
        btn_refresh = QPushButton("⟳", self)
        btn_refresh.setToolTip("Обновить список процессов")
        btn_refresh.setFixedWidth(40)
        btn_refresh.clicked.connect(self._reload)
        search_row.addWidget(btn_refresh)
        layout.addLayout(search_row)
        self.list_widget = QListWidget(self)
        self.list_widget.setItemDelegate(AppItemDelegate(self.list_widget))
        self.list_widget.setSpacing(2)
        self.list_widget.itemDoubleClicked.connect(lambda _: self.accept())
        self._all_apps: Dict[str, str] = {}
        self._populate_running_apps()
        layout.addWidget(self.list_widget)
        btn_browse = QPushButton("Обзор... (.exe)", self)
        btn_browse.clicked.connect(self._browse_exe)
        layout.addWidget(btn_browse)
        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel, self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._selected_name = ""
        self._selected_exe = ""
        self._from_browse = False

    def _populate_running_apps(self):
        self._all_apps = list_running_apps()
        self._fill(self._all_apps)

    def _reload(self):
        self._populate_running_apps()
        self._filter_apps(self.search_edit.text())

    def _fill(self, apps: dict):
        self.list_widget.clear()
        for name, exe in sorted(apps.items()):
            item = QListWidgetItem(name)
            item.setData(Qt.ItemDataRole.UserRole, exe)
            icon = get_app_icon(exe)
            if icon:
                item.setData(Qt.ItemDataRole.DecorationRole, icon)
            self.list_widget.addItem(item)

    def _filter_apps(self, text: str):
        t = text.lower()
        filtered = {
            n: e for n, e in self._all_apps.items()
            if not t or t in n.lower() or t in e.lower()
        }
        self._fill(filtered)

    def _browse_exe(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Выберите исполняемый файл", "", "Executable (*.exe)"
        )
        if path:
            self._selected_name = Path(path).name
            self._selected_exe = path
            self._from_browse = True
            self.accept()

    def selected_app(self):
        if not self._from_browse:
            it = self.list_widget.currentItem()
            if it:
                self._selected_name = it.text()
                self._selected_exe = it.data(Qt.ItemDataRole.UserRole) or ""
        return self._selected_name, self._selected_exe


class WatchListView(QWidget):
    def __init__(self, watchlist_manager: WatchListManager,
                 repo: Repository = None, on_changed=None, parent=None):
        super().__init__(parent)
        self.manager = watchlist_manager
        self._repo = repo
        self._on_changed = on_changed
        self.setObjectName("watchlistView")
        self.setStyleSheet(f"#watchlistView {{ background: {C.bg}; }}")

        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 24, 24, 24)
        layout.setSpacing(12)

        title = QLabel("Отслеживаемые приложения")
        title.setStyleSheet("font-size:20px; font-weight:700;")
        layout.addWidget(title)

        self._content_stack = QStackedWidget()
        self._content_stack.setObjectName("wlContentStack")
        self._content_stack.setStyleSheet(f"#wlContentStack {{ background: {C.bg}; }}")

        self._empty = EmptyState(
            "Список пуст",
            "Добавьте приложения, время которых хотите отслеживать",
            "＋ Добавить приложение", self._on_add,
            pixmap=asset_pixmap("apps.png", 64),
        )
        self._content_stack.addWidget(self._empty)

        self.table = QTableWidget(0, 4)
        self.table.setHorizontalHeaderLabels(
            ["Приложение", "Процесс", "Путь", "Сегодня"])
        self.table.horizontalHeader().setStretchLastSection(False)
        self.table.horizontalHeader().setSectionResizeMode(
            QHeaderView.ResizeMode.Interactive)
        self.table.setColumnWidth(0, 220)
        self.table.setColumnWidth(1, 160)
        self.table.setColumnWidth(3, 120)
        self.table.setAlternatingRowColors(True)
        self.table.setStyleSheet(
            f"QTableWidget {{ background-color: transparent; alternate-background-color: {C.surface_hover}; }}"
        )
        self.table.setShowGrid(False)
        self.table.verticalHeader().setDefaultSectionSize(32)
        self.table.setSortingEnabled(True)
        self.table.setContextMenuPolicy(
            Qt.ContextMenuPolicy.CustomContextMenu)
        self.table.customContextMenuRequested.connect(self._context_menu)
        self.table.cellDoubleClicked.connect(self._on_cell_dclick)
        sc_del = QShortcut(QKeySequence(QKeySequence.StandardKey.Delete),
                           self.table)
        sc_del.setContext(Qt.ShortcutContext.WidgetShortcut)
        sc_del.activated.connect(self._on_remove)
        self._content_stack.addWidget(self.table)

        layout.addWidget(self._content_stack, 1)

        btn_layout = QHBoxLayout()
        btn_add = QPushButton("＋ Добавить приложение", self)
        btn_add.setObjectName("primary")
        btn_add.clicked.connect(self._on_add)
        btn_remove = QPushButton("🗑  Удалить", self)
        btn_remove.clicked.connect(self._on_remove)
        btn_layout.addWidget(btn_add)
        btn_layout.addWidget(btn_remove)
        btn_layout.addStretch()
        layout.addLayout(btn_layout)

        self.refresh()

    def refresh(self):
        apps = self.manager.get_all()
        today_map = self._repo.get_today_seconds_by_app() if self._repo else {}

        if not apps:
            self._content_stack.setCurrentWidget(self._empty)
            self.table.setRowCount(0)
            return
        self._content_stack.setCurrentWidget(self.table)

        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        self.table.setRowCount(len(apps))
        for i, app in enumerate(apps):
            display = app.display_name or ""
            icon = get_app_icon(app.exe_path)
            item0 = QTableWidgetItem(display)
            if icon:
                item0.setIcon(icon)
            item0.setData(Qt.ItemDataRole.UserRole, app.id)
            item0.setFlags(item0.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 0, item0)

            for col, val in [
                (1, app.process_name),
                (2, app.exe_path or ""),
            ]:
                item = QTableWidgetItem(val)
                item.setFlags(item.flags() & ~Qt.ItemFlag.ItemIsEditable)
                self.table.setItem(i, col, item)

            sec = today_map.get(app.process_name, 0)
            time_item = QTableWidgetItem(fmt_duration(sec, short=True))
            time_item.setData(Qt.ItemDataRole.UserRole, sec)
            time_item.setFlags(
                time_item.flags() & ~Qt.ItemFlag.ItemIsEditable)
            self.table.setItem(i, 3, time_item)

        self.table.setSortingEnabled(sorting)

    def refresh_times(self):
        if not self._repo:
            return
        today = self._repo.get_today_seconds_by_app()
        sorting = self.table.isSortingEnabled()
        self.table.setSortingEnabled(False)
        for row in range(self.table.rowCount()):
            proc_item = self.table.item(row, 1)
            time_item = self.table.item(row, 3)
            if not proc_item or not time_item:
                continue
            sec = today.get(proc_item.text(), 0)
            time_item.setText(fmt_duration(sec, short=True))
            time_item.setData(Qt.ItemDataRole.UserRole, sec)
        self.table.setSortingEnabled(sorting)

    def _on_add(self):
        dlg = AddAppDialog(self)
        if dlg.exec() == QDialog.DialogCode.Accepted:
            name, exe = dlg.selected_app()
            if name:
                result = self.manager.add_app(name, exe, name)
                if result == -1:
                    QMessageBox.information(
                        self, "Добавление",
                        f"Приложение «{name}» уже в списке.")
                if self._on_changed:
                    self._on_changed()
                self.refresh()

    def _on_remove(self):
        row = self.table.currentRow()
        if row < 0:
            return
        self._remove_row(row)

    def _remove_row(self, row):
        app_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        reply = QMessageBox.question(
            self, "Подтверждение",
            "Удалить приложение и всю статистику по нему?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
        )
        if reply == QMessageBox.StandardButton.Yes:
            self.manager.remove_app(app_id)
            if self._on_changed:
                self._on_changed()
            self.refresh()

    def _on_cell_dclick(self, row: int, col: int):
        if col == 0:
            self._rename_row(row)

    def _rename_row(self, row):
        app_id = self.table.item(row, 0).data(Qt.ItemDataRole.UserRole)
        current = self.table.item(row, 0).text()
        new, ok = QInputDialog.getText(
            self, "Переименовать",
            "Отображаемое имя:", text=current
        )
        if ok and new.strip() and self._repo:
            self._repo.update_display_name(app_id, new.strip())
            self.refresh()

    def _context_menu(self, pos):
        row = self.table.rowAt(pos.y())
        if row < 0:
            return
        menu = QMenu(self)
        act_rename = menu.addAction("✎  Переименовать")
        act_delete = menu.addAction("🗑  Удалить")
        action = menu.exec(self.table.viewport().mapToGlobal(pos))
        if action == act_delete:
            self._remove_row(row)
        elif action == act_rename:
            self._rename_row(row)
