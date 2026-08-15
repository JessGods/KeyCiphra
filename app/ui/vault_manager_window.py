"""Tela inicial para criar, selecionar e organizar cofres independentes."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from app.models.managed_vault import LEGACY_STORAGE, ManagedVault
from app.services.vault_catalog_service import (
    VaultArchiveAuthenticationError,
    VaultCatalogError,
    VaultCatalogService,
    VaultNameError,
)
from app.ui.archived_vaults_dialog import ArchivedVaultsDialog
from app.ui.icons import lucide_icon
from app.ui.message_dialog import MessageDialog
from app.ui.vault_manager_dialogs import (
    ArchiveVaultDialog,
    NewVaultDialog,
    RenameVaultDialog,
)
from app.ui.window_chrome import install_window_chrome
from app.utils.logging_config import get_logger


class VaultManagerWindow(QMainWindow):
    open_requested = Signal(object)
    vault_created = Signal(object, object)

    def __init__(self, service: VaultCatalogService, notice: str | None = None) -> None:
        super().__init__()
        self._service = service
        self._notice_text = notice
        self._list = QListWidget()
        self._list.setObjectName("vaultList")
        self._name = QLabel("Selecione um cofre")
        self._name.setObjectName("vaultSelectedName")
        self._details = QLabel()
        self._details.setObjectName("muted")
        self._details.setWordWrap(True)
        self._open_button = QPushButton("Abrir cofre")
        self._rename_button = QPushButton("Renomear")
        self._archive_button = QPushButton("Arquivar")
        self.setWindowTitle("KeyCiphra — Gerenciar cofres")
        self.setMinimumSize(760, 540)
        self.resize(980, 650)
        self._build_ui()
        self.refresh()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("vaultManagerRoot")
        layout = QVBoxLayout(root)
        layout.setContentsMargins(18, 8, 18, 20)
        layout.setSpacing(16)
        install_window_chrome(self, layout, "KeyCiphra — Cofres", allow_maximize=True)

        heading = QHBoxLayout()
        heading.setSpacing(15)
        badge = QLabel()
        badge.setObjectName("vaultManagerBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(58, 58)
        badge.setPixmap(lucide_icon("vault", "#dbeafe", 31).pixmap(31, 31))
        heading.addWidget(badge)
        text = QVBoxLayout()
        title = QLabel("Seus cofres")
        title.setObjectName("dialogTitle")
        text.addWidget(title)
        subtitle = QLabel(
            "Cada cofre possui senha mestra, credenciais e backups completamente separados."
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        text.addWidget(subtitle)
        heading.addLayout(text, 1)
        create = QPushButton("Novo cofre")
        create.setObjectName("primaryButton")
        create.setIcon(lucide_icon("folder-plus", "#ffffff", 18))
        create.setIconSize(QSize(18, 18))
        create.setMinimumHeight(42)
        create.clicked.connect(self._create)
        archives = QPushButton("Arquivados")
        archives.setObjectName("secondaryButton")
        archives.setIcon(lucide_icon("archive", "#e5e7eb", 18))
        archives.setIconSize(QSize(18, 18))
        archives.setMinimumHeight(42)
        archives.clicked.connect(self._open_archives)
        heading.addWidget(archives)
        heading.addWidget(create)
        layout.addLayout(heading)

        if self._notice_text:
            notice = QLabel(self._notice_text)
            notice.setObjectName("sessionNotice")
            notice.setWordWrap(True)
            layout.addWidget(notice)

        content = QHBoxLayout()
        content.setSpacing(16)
        sidebar = QFrame()
        sidebar.setObjectName("vaultManagerSidebar")
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(12, 12, 12, 12)
        sidebar_layout.addWidget(self._list)
        self._list.currentItemChanged.connect(self._selection_changed)
        self._list.itemDoubleClicked.connect(lambda _item: self._open())
        content.addWidget(sidebar, 5)

        card = QFrame()
        card.setObjectName("vaultManagerCard")
        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(28, 28, 28, 26)
        card_layout.setSpacing(14)
        icon = QLabel()
        icon.setObjectName("vaultDetailBadge")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(64, 64)
        icon.setPixmap(lucide_icon("lock", "#bfdbfe", 31).pixmap(31, 31))
        card_layout.addWidget(icon)
        card_layout.addWidget(self._name)
        card_layout.addWidget(self._details)
        card_layout.addStretch()
        self._open_button.setObjectName("primaryButton")
        self._open_button.setIcon(lucide_icon("lock", "#ffffff", 18))
        self._open_button.clicked.connect(self._open)
        self._open_button.setMinimumHeight(44)
        card_layout.addWidget(self._open_button)
        secondary = QHBoxLayout()
        self._rename_button.setObjectName("secondaryButton")
        self._rename_button.setIcon(lucide_icon("pencil", "#e5e7eb", 17))
        self._rename_button.clicked.connect(self._rename)
        secondary.addWidget(self._rename_button)
        self._archive_button.setObjectName("dangerButton")
        self._archive_button.setIcon(lucide_icon("archive", "#fecaca", 17))
        self._archive_button.clicked.connect(self._archive)
        secondary.addWidget(self._archive_button)
        card_layout.addLayout(secondary)
        content.addWidget(card, 4)
        layout.addLayout(content, 1)
        self.setCentralWidget(root)

    def refresh(self, selected_id: str | None = None) -> None:
        self._list.clear()
        vaults = self._service.list_vaults()
        for vault in vaults:
            item = QListWidgetItem()
            item.setText(vault.name)
            item.setData(Qt.ItemDataRole.UserRole, vault.id)
            item.setIcon(
                lucide_icon(
                    "shield-check" if vault.storage_kind == LEGACY_STORAGE else "vault",
                    "#60a5fa",
                    21,
                )
            )
            item.setSizeHint(QSize(0, 54))
            self._list.addItem(item)
            if vault.id == selected_id:
                self._list.setCurrentItem(item)
        if self._list.currentItem() is None and self._list.count():
            self._list.setCurrentRow(0)
        self._selection_changed(self._list.currentItem())

    def _selected(self) -> ManagedVault | None:
        item = self._list.currentItem()
        if item is None:
            return None
        try:
            return self._service.get(str(item.data(Qt.ItemDataRole.UserRole)))
        except VaultCatalogError:
            return None

    def _selection_changed(self, item: QListWidgetItem | None, _previous=None) -> None:  # type: ignore[no-untyped-def]
        del item
        vault = self._selected()
        enabled = vault is not None
        for button in (self._open_button, self._rename_button, self._archive_button):
            button.setEnabled(enabled)
        if vault is None:
            self._name.setText("Nenhum cofre cadastrado")
            self._details.setText(
                "Crie seu primeiro cofre para começar. A senha mestra nunca será armazenada."
            )
            return
        created = datetime.fromisoformat(vault.created_at).astimezone().strftime("%d/%m/%Y")
        kind = "Cofre principal preservado" if vault.storage_kind == LEGACY_STORAGE else "Cofre isolado"
        self._name.setText(vault.name)
        self._details.setText(
            f"{kind} • criado em {created}\n\nA abertura exige a senha mestra deste cofre."
        )

    def _open(self) -> None:
        vault = self._selected()
        if vault is not None:
            self.open_requested.emit(vault)

    def _create(self) -> None:
        dialog = NewVaultDialog(self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            vault, session = self._service.create(dialog.vault_name, dialog.master_password)
        except (TypeError, ValueError, RuntimeError) as exc:
            get_logger().warning("vault.catalog_create_failed type=%s", type(exc).__name__)
            MessageDialog.warning(self, str(exc), title="Cofre não criado")
            return
        finally:
            dialog.clear_secrets()
        get_logger().info("vault.catalog_created")
        self.vault_created.emit(vault, session)

    def _rename(self) -> None:
        vault = self._selected()
        if vault is None:
            return
        dialog = RenameVaultDialog(vault.name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            renamed = self._service.rename(vault.id, dialog.vault_name)
        except (VaultNameError, VaultCatalogError, TypeError, ValueError) as exc:
            MessageDialog.warning(self, str(exc), title="Nome não alterado")
            return
        get_logger().info("vault.catalog_renamed")
        self.refresh(renamed.id)

    def _archive(self) -> None:
        vault = self._selected()
        if vault is None:
            return
        dialog = ArchiveVaultDialog(vault.name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        try:
            archive_path = self._service.archive(vault.id, dialog.master_password)
        except VaultArchiveAuthenticationError:
            get_logger().warning("vault.catalog_archive_authentication_failed")
            MessageDialog.warning(
                self,
                "Não foi possível autenticar o cofre.",
                title="Cofre não arquivado",
                detail="Confira a senha mestra e tente novamente.",
            )
            return
        except VaultCatalogError as exc:
            get_logger().error("vault.catalog_archive_failed type=%s", type(exc).__name__)
            MessageDialog.error(self, str(exc), title="Cofre não arquivado")
            return
        finally:
            dialog.clear_secrets()
        get_logger().info("vault.catalog_archived")
        self.refresh()
        MessageDialog.warning(
            self,
            "O cofre saiu da lista e foi preservado na área de arquivos.",
            title="Cofre arquivado",
            detail=str(archive_path),
        )

    def _open_archives(self) -> None:
        dialog = ArchivedVaultsDialog(self._service, self)
        dialog.exec()
        if dialog.restored_vault is not None:
            self.refresh(dialog.restored_vault.id)
            MessageDialog.warning(
                self,
                f'“{dialog.restored_vault.name}” voltou para a lista de cofres.',
                title="Cofre recuperado",
                detail="Use a senha mestra original para desbloqueá-lo.",
            )
