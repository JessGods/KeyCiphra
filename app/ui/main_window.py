"""Painel principal do cofre desbloqueado."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from PySide6.QtCore import QSize, QStandardPaths, Qt, Signal
from PySide6.QtGui import QAction
from PySide6.QtWidgets import (
    QAbstractItemView,
    QComboBox,
    QDialog,
    QFileDialog,
    QHBoxLayout,
    QHeaderView,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMenu,
    QPushButton,
    QSizePolicy,
    QTableWidget,
    QTableWidgetItem,
    QVBoxLayout,
    QWidget,
)

from app.models.app_settings import AppSettings
from app.models.credential import Credential
from app.repositories.category_repository import CategoryRepositoryIntegrityError
from app.repositories.credential_repository import CredentialRepository, RepositoryIntegrityError
from app.security.session import VaultSession
from app.services.backup_service import (
    BackupAuthenticationError,
    BackupError,
    BackupService,
)
from app.services.category_service import CategoryService
from app.services.clipboard_service import ClipboardService
from app.services.demo_data_service import DemoDataResult, DemoDataService
from app.ui.category_manager_dialog import CategoryManagerDialog
from app.ui.credential_dialog import CredentialDialog
from app.ui.icons import lucide_icon
from app.ui.message_dialog import MessageDialog
from app.ui.settings_dialog import SettingsDialog
from app.ui.vault_restore_dialog import VaultRestoreDialog
from app.ui.window_chrome import install_window_chrome
from app.utils.logging_config import get_logger


class MainWindow(QMainWindow):
    """Lista e altera credenciais sem acessar SQLite diretamente."""

    lock_requested = Signal()
    switch_vault_requested = Signal()
    vault_restored = Signal(str)
    settings_changed = Signal(object)

    def __init__(
        self,
        repository: CredentialRepository,
        session: VaultSession,
        clipboard_service: ClipboardService,
        backup_service: BackupService | None = None,
        settings: AppSettings | None = None,
        *,
        category_service: CategoryService | None = None,
        vault_name: str = "Cofre principal",
    ) -> None:
        super().__init__()
        self._repository = repository
        self._session = session
        self._clipboard = clipboard_service
        self._backup_service = backup_service
        self._settings = settings or AppSettings()
        self._category_service = category_service
        self._vault_name = vault_name
        self._credentials: list[Credential] = []
        self._action_column_width = 0
        self._transfer_directory = self._default_transfer_directory()

        self._search = QLineEdit()
        self._category_filter = QComboBox()
        self._table = QTableWidget(0, 4)
        self._status = QLabel()

        self.setWindowTitle(f"KeyCiphra — {self._vault_name}")
        self.setMinimumSize(680, 480)
        self.resize(1040, 680)
        self._build_ui()

    def initialize(self) -> bool:
        """Carrega o cofre após todos os sinais da janela estarem conectados."""
        return self._load_credentials()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("mainRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 8, 18, 18)
        layout.setSpacing(16)
        install_window_chrome(
            self,
            layout,
            f"KeyCiphra — {self._vault_name}",
            allow_maximize=True,
        )

        header = QHBoxLayout()
        shield = QLabel()
        shield.setPixmap(lucide_icon("shield-check", "#60a5fa", 30).pixmap(30, 30))
        header.addWidget(shield)
        title = QLabel("KEYCIPHRA")
        title.setObjectName("brand")
        header.addWidget(title)
        header.addStretch()
        if self._backup_service is not None:
            backup_button = QPushButton("Backup")
            self._configure_button(backup_button, "database-backup")
            backup_button.setToolTip("Criar agora um snapshot criptografado do cofre")
            backup_button.clicked.connect(self._create_backup)
            header.addWidget(backup_button)

            transfer_button = QPushButton("Transferir")
            self._configure_button(transfer_button, "restore")
            transfer_button.setToolTip("Exportar ou importar um cofre criptografado")
            transfer_menu = QMenu(transfer_button)
            export_action = QAction(
                lucide_icon("database-backup", "#dbeafe", 18),
                "Exportar cofre…",
                transfer_menu,
            )
            export_action.triggered.connect(self._export_vault)
            transfer_menu.addAction(export_action)
            import_action = QAction(
                lucide_icon("restore", "#dbeafe", 18),
                "Importar/Restaurar cofre…",
                transfer_menu,
            )
            import_action.triggered.connect(self._import_vault)
            transfer_menu.addAction(import_action)
            transfer_button.setMenu(transfer_menu)
            header.addWidget(transfer_button)
        settings_button = QPushButton()
        settings_button.setAccessibleName("Configurações")
        settings_button.setToolTip("Configurações de segurança")
        settings_button.setIcon(lucide_icon("settings-2", "#e5e7eb", 19))
        settings_button.setIconSize(QSize(19, 19))
        settings_button.setFixedSize(42, 42)
        settings_button.clicked.connect(self._open_settings)
        header.addWidget(settings_button)
        vaults_button = QPushButton("Cofres")
        self._configure_button(vaults_button, "vault")
        vaults_button.setToolTip("Bloquear e escolher outro cofre")
        vaults_button.clicked.connect(self._switch_vault)
        header.addWidget(vaults_button)
        lock_button = QPushButton("Bloquear")
        self._configure_button(lock_button, "lock")
        lock_button.clicked.connect(self._lock)
        header.addWidget(lock_button)
        layout.addLayout(header)

        toolbar = QHBoxLayout()
        toolbar.setSpacing(12)
        self._search.setPlaceholderText("Buscar por título, usuário ou categoria...")
        self._search.setClearButtonEnabled(True)
        self._search.setMinimumHeight(max(42, self._search.fontMetrics().height() + 24))
        self._search.addAction(
            lucide_icon("search", "#94a3b8", 18),
            QLineEdit.ActionPosition.LeadingPosition,
        )
        self._search.textChanged.connect(self._apply_filter)
        toolbar.addWidget(self._search, 1)

        self._category_filter.setAccessibleName("Filtrar por categoria")
        self._category_filter.setToolTip("Exibir somente credenciais de uma categoria")
        self._category_filter.setMinimumWidth(170)
        self._category_filter.setMinimumHeight(
            max(42, self._category_filter.fontMetrics().height() + 22)
        )
        self._category_filter.addItem("Todas as categorias", None)
        self._category_filter.addItem("Sem categoria", "")
        self._category_filter.currentIndexChanged.connect(self._apply_filter)
        toolbar.addWidget(self._category_filter)

        categories_button = QPushButton()
        categories_button.setAccessibleName("Gerenciar categorias")
        categories_button.setToolTip("Criar, editar ou excluir categorias")
        categories_button.setIcon(lucide_icon("tags", "#e5e7eb", 19))
        categories_button.setIconSize(QSize(19, 19))
        categories_button.setFixedSize(42, 42)
        categories_button.setEnabled(self._category_service is not None)
        categories_button.clicked.connect(lambda: self._manage_categories(self))
        toolbar.addWidget(categories_button)

        add_button = QPushButton("Nova credencial")
        add_button.setObjectName("primaryButton")
        self._configure_button(add_button, "plus")
        add_button.clicked.connect(self._add)
        toolbar.addWidget(add_button)
        layout.addLayout(toolbar)

        self._table.setHorizontalHeaderLabels(("Título", "Usuário", "Categoria", "Ações"))
        self._table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self._table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self._table.setAlternatingRowColors(True)
        self._table.setShowGrid(False)
        self._table.verticalHeader().setVisible(False)
        header_view = self._table.horizontalHeader()
        header_view.setMinimumSectionSize(90)
        header_view.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        header_view.setSectionResizeMode(2, QHeaderView.ResizeMode.ResizeToContents)
        header_view.setSectionResizeMode(3, QHeaderView.ResizeMode.Fixed)
        self._set_default_action_width()
        layout.addWidget(self._table, 1)

        self._status.setObjectName("muted")
        layout.addWidget(self._status)
        self._clipboard.cleared.connect(
            lambda: self.statusBar().showMessage("Clipboard limpo automaticamente.", 4_000)
        )
        self.setCentralWidget(root)

    def _set_default_action_width(self) -> None:
        button_size = 26
        self._action_column_width = (button_size * 3) + 36
        self._table.setColumnWidth(3, self._action_column_width)

    def _configure_button(
        self,
        button: QPushButton,
        icon_name: str,
        *,
        compact: bool = False,
    ) -> None:
        icon_size = max(17, button.fontMetrics().height())
        button.setIcon(lucide_icon(icon_name, "#e5e7eb", icon_size))
        button.setIconSize(QSize(icon_size, icon_size))
        text_width = button.fontMetrics().horizontalAdvance(button.text())
        horizontal_space = 28 if compact else 38
        button.setMinimumWidth(text_width + icon_size + horizontal_space)
        button_height = max(28, button.fontMetrics().height() + (14 if compact else 20))
        if compact:
            button.setObjectName("compactActionButton")
            square_size = 26
            button.setFixedSize(square_size, square_size)
            button.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        else:
            button.setMinimumHeight(button_height)
            button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def _load_credentials(self) -> bool:
        try:
            self._credentials = self._repository.list_all()
            if self._category_service is not None:
                self._category_service.synchronize(self._credentials)
                self._refresh_category_filter()
        except (CategoryRepositoryIntegrityError, RepositoryIntegrityError):
            MessageDialog.error(
                self,
                "Um item armazenado não pôde ser autenticado. O cofre será bloqueado.",
                title="Falha de integridade",
            )
            self._credentials.clear()
            self._session.lock()
            return False
        self._apply_filter()
        return True

    def _apply_filter(self) -> None:
        query = self._search.text().strip().casefold()
        selected_category = self._category_filter.currentData()
        filtered = [
            credential
            for credential in self._credentials
            if (
                selected_category is None
                or credential.category.strip().casefold()
                == str(selected_category).strip().casefold()
            )
            and (
                not query
                or query in credential.title.casefold()
                or query in credential.username.casefold()
                or query in credential.category.casefold()
            )
        ]
        self._populate_table(filtered)
        total = len(self._credentials)
        category_label = (
            "Todas as categorias"
            if selected_category is None
            else str(self._category_filter.currentText())
        )
        self._status.setText(
            f"{len(filtered)} de {total} credencial(is)  •  {category_label}"
        )

    def _refresh_category_filter(self) -> None:
        selected = self._category_filter.currentData()
        names = self._category_names()
        self._category_filter.blockSignals(True)
        self._category_filter.clear()
        self._category_filter.addItem("Todas as categorias", None)
        self._category_filter.addItem("Sem categoria", "")
        for name in names:
            self._category_filter.addItem(name, name)
        index = self._category_filter.findData(selected)
        self._category_filter.setCurrentIndex(index if index >= 0 else 0)
        self._category_filter.blockSignals(False)

    def _category_names(self) -> list[str]:
        if self._category_service is None:
            return sorted(
                {item.category.strip() for item in self._credentials if item.category.strip()},
                key=str.casefold,
            )
        return [category.name for category in self._category_service.list_all()]

    def _populate_table(self, credentials: list[Credential]) -> None:
        self._table.setRowCount(len(credentials))
        largest_actions_width = self._action_column_width
        for row, credential in enumerate(credentials):
            title_item = QTableWidgetItem(credential.title)
            title_item.setData(Qt.ItemDataRole.UserRole, credential.id)
            self._table.setItem(row, 0, title_item)
            self._table.setItem(row, 1, QTableWidgetItem(self._mask_username(credential.username)))
            self._table.setItem(row, 2, QTableWidgetItem(credential.category or "—"))

            actions = QWidget()
            actions.setObjectName("tableActions")
            actions_layout = QHBoxLayout(actions)
            actions_layout.setContentsMargins(7, 5, 7, 5)
            actions_layout.setSpacing(6)
            actions_layout.addStretch()

            copy_button = QPushButton()
            self._configure_button(copy_button, "copy", compact=True)
            copy_button.setAccessibleName("Copiar senha")
            copy_button.setToolTip("Copiar senha; o clipboard será limpo em 25 segundos")
            copy_button.setEnabled(bool(credential.password))
            copy_button.clicked.connect(lambda checked=False, item=credential: self._copy_password(item))
            actions_layout.addWidget(copy_button)

            edit_button = QPushButton()
            self._configure_button(edit_button, "pencil", compact=True)
            edit_button.setAccessibleName("Editar credencial")
            edit_button.setToolTip("Editar credencial")
            edit_button.clicked.connect(lambda checked=False, item=credential: self._edit(item))
            actions_layout.addWidget(edit_button)

            delete_button = QPushButton()
            self._configure_button(delete_button, "trash", compact=True)
            delete_button.setProperty("danger", True)
            delete_button.setAccessibleName("Excluir credencial")
            delete_button.setToolTip("Excluir credencial")
            delete_button.clicked.connect(lambda checked=False, item=credential: self._delete(item))
            actions_layout.addWidget(delete_button)
            actions_layout.addStretch()

            required_width = sum(button.minimumWidth() for button in (copy_button, edit_button, delete_button))
            required_width += actions_layout.spacing() * 4 + 14
            actions.setMinimumWidth(required_width)
            largest_actions_width = max(largest_actions_width, required_width)
            row_height = max(
                self.fontMetrics().height() + 32,
                max(button.height() for button in (copy_button, edit_button, delete_button)) + 10,
            )
            self._table.setRowHeight(row, row_height)
            self._table.setCellWidget(row, 3, actions)

        if largest_actions_width != self._action_column_width:
            self._action_column_width = largest_actions_width
        self._table.setColumnWidth(3, self._action_column_width)

    def _add(self) -> None:
        dialog = CredentialDialog(
            parent=self,
            categories=self._category_names(),
            manage_categories=self._manage_categories,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._repository.add(dialog.credential())
            self._load_credentials()
            self.statusBar().showMessage("Credencial salva com segurança.", 4_000)
            get_logger().info("credential.created")
        except Exception as exc:
            get_logger().error("credential.create_failed type=%s", type(exc).__name__)
            MessageDialog.error(self, "Não foi possível salvar a credencial.")

    def _edit(self, credential: Credential) -> None:
        dialog = CredentialDialog(
            credential,
            self,
            categories=self._category_names(),
            manage_categories=self._manage_categories,
        )
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            self._repository.update(dialog.credential())
            self._load_credentials()
            self.statusBar().showMessage("Credencial atualizada.", 4_000)
            get_logger().info("credential.updated")
        except Exception as exc:
            get_logger().error("credential.update_failed type=%s", type(exc).__name__)
            MessageDialog.error(self, "Não foi possível atualizar a credencial.")

    def _delete(self, credential: Credential) -> None:
        confirmed = MessageDialog.confirm(
            self,
            f'Excluir permanentemente “{credential.title}”?',
            title="Excluir credencial",
            confirm_text="Excluir",
        )
        if not confirmed:
            return
        try:
            self._repository.delete(credential.id)
            self._load_credentials()
            get_logger().info("credential.deleted")
        except Exception as exc:
            get_logger().error("credential.delete_failed type=%s", type(exc).__name__)
            MessageDialog.error(self, "Não foi possível excluir a credencial.")

    def _copy_password(self, credential: Credential) -> None:
        self._clipboard.copy_secret(credential.password)
        self.statusBar().showMessage(
            f"Senha copiada; limpeza automática em {self._clipboard.timeout_seconds} segundos.",
            5_000,
        )

    def _manage_categories(self, parent: QWidget) -> list[str]:
        if self._category_service is None:
            return self._category_names()
        dialog = CategoryManagerDialog(
            self._category_service,
            parent,
            populate_demo=self._populate_demo_data,
        )
        dialog.exec()
        if dialog.changed:
            self._load_credentials()
            self.statusBar().showMessage("Categorias do cofre atualizadas.", 5_000)
        else:
            self._refresh_category_filter()
            self._apply_filter()
        return self._category_names()

    def _populate_demo_data(self) -> DemoDataResult:
        if self._category_service is None:
            return DemoDataResult(0, 0)
        return DemoDataService(self._category_service, self._repository).populate()

    def _open_settings(self) -> None:
        dialog = SettingsDialog(self._settings, self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self.settings_changed.emit(dialog.settings)

    def apply_settings(self, settings: AppSettings) -> None:
        self._settings = settings
        self.statusBar().showMessage(
            "Configurações salvas — bloqueio após "
            f"{settings.auto_lock_minutes} minuto(s) sem cliques, teclas ou rolagem.",
            8_000,
        )

    def _create_backup(self) -> None:
        if self._backup_service is None:
            return
        try:
            backup = self._backup_service.create_backup()
            self.notify_backup_created(backup.name)
            get_logger().info("backup.manual_created")
        except BackupError as exc:
            get_logger().error("backup.manual_failed type=%s", type(exc).__name__)
            MessageDialog.error(
                self,
                "Não foi possível criar um backup íntegro do cofre.",
                title="Falha no backup",
            )

    def notify_backup_created(self, filename: str) -> None:
        self.statusBar().showMessage(f"Backup criptografado criado: {filename}", 7_000)

    def _export_vault(self) -> None:
        if self._backup_service is None:
            return
        destination = self._choose_export_destination()
        if destination is None:
            return
        if destination.exists() and not MessageDialog.confirm(
            self,
            f'Já existe um arquivo chamado “{destination.name}”. Deseja substituí-lo?',
            title="Substituir exportação",
            confirm_text="Substituir",
        ):
            return
        try:
            exported = self._backup_service.export_backup(destination)
            self.statusBar().showMessage(
                f"Cofre criptografado exportado: {exported}",
                9_000,
            )
            get_logger().info("vault.exported")
        except BackupError as exc:
            get_logger().error("vault.export_failed type=%s", type(exc).__name__)
            MessageDialog.error(
                self,
                "Não foi possível exportar uma cópia íntegra do cofre.",
                title="Falha na exportação",
            )

    def _import_vault(self) -> None:
        if self._backup_service is None:
            return
        source = self._choose_import_source()
        if source is None:
            return
        dialog = VaultRestoreDialog(source, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            safety_backup = self._backup_service.restore_backup(
                source,
                dialog.master_password,
            )
        except BackupAuthenticationError:
            get_logger().warning("vault.restore_authentication_failed")
            MessageDialog.error(
                self,
                "A senha está incorreta ou o arquivo contém dados adulterados.",
                title="Cofre não autenticado",
                detail="O cofre atual permaneceu intacto.",
            )
            return
        except BackupError as exc:
            get_logger().error("vault.restore_failed type=%s", type(exc).__name__)
            MessageDialog.error(
                self,
                "Não foi possível restaurar este arquivo com segurança.",
                title="Falha na restauração",
                detail="O cofre atual permaneceu intacto.",
            )
            return

        self._credentials.clear()
        self._table.clearContents()
        self._clipboard.clear_secret()
        self._session.lock()
        self.vault_restored.emit(
            f"Cofre restaurado com sucesso. Backup anterior preservado como {safety_backup.name}."
        )

    def _choose_export_destination(self) -> Path | None:
        timestamp = datetime.now(UTC).astimezone().strftime("%Y-%m-%d_%H-%M-%S")
        dialog = self._file_dialog("Exportar cofre criptografado")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptSave)
        dialog.setFileMode(QFileDialog.FileMode.AnyFile)
        dialog.setDefaultSuffix("db")
        dialog.selectFile(f"keyciphra_{timestamp}.db")
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        destination = Path(dialog.selectedFiles()[0])
        self._remember_transfer_directory(destination.parent)
        return (
            destination
            if destination.suffix.lower() == ".db"
            else destination.with_suffix(".db")
        )

    def _choose_import_source(self) -> Path | None:
        dialog = self._file_dialog("Importar cofre criptografado")
        dialog.setAcceptMode(QFileDialog.AcceptMode.AcceptOpen)
        dialog.setFileMode(QFileDialog.FileMode.ExistingFile)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return None
        source = Path(dialog.selectedFiles()[0])
        self._remember_transfer_directory(source.parent)
        return source

    def _file_dialog(self, title: str) -> QFileDialog:
        dialog = QFileDialog(self, title)
        dialog.setObjectName("fileDialog")
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog, True)
        dialog.setNameFilter("Cofre KeyCiphra (*.db);;Todos os arquivos (*)")
        initial_directory = (
            self._transfer_directory
            if self._transfer_directory.is_dir()
            else self._default_transfer_directory()
        )
        dialog.setDirectory(str(initial_directory))
        dialog.resize(820, 560)
        return dialog

    def _remember_transfer_directory(self, directory: Path) -> None:
        """Mantém a última pasta apenas na sessão, sem persistir caminhos privados."""
        candidate = Path(directory)
        if candidate.is_dir():
            self._transfer_directory = candidate

    @staticmethod
    def _default_transfer_directory() -> Path:
        documents = QStandardPaths.writableLocation(
            QStandardPaths.StandardLocation.DocumentsLocation
        )
        candidate = Path(documents) if documents else Path.home()
        return candidate if candidate.is_dir() else Path.home()

    def _lock(self) -> None:
        self._credentials.clear()
        self._table.clearContents()
        self._clipboard.clear_secret()
        self._session.lock()
        get_logger().info("vault.locked")
        self.lock_requested.emit()

    def _switch_vault(self) -> None:
        self._credentials.clear()
        self._table.clearContents()
        self._clipboard.clear_secret()
        self._session.lock()
        get_logger().info("vault.switch_requested")
        self.switch_vault_requested.emit()

    def lock_vault(self) -> None:
        """Bloqueia a sessão por solicitação externa, como inatividade."""
        if self._session.is_unlocked:
            self._lock()

    @staticmethod
    def _mask_username(username: str) -> str:
        if not username:
            return "—"
        visible = min(3, len(username))
        return username[:visible] + "•" * min(8, max(3, len(username) - visible))

    def closeEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        self._credentials.clear()
        self._clipboard.clear_secret()
        self._session.lock()
        super().closeEvent(event)
