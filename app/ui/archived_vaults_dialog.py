"""Lista e recupera cofres arquivados sem substituir dados ativos."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QVBoxLayout,
)

from app.models.archived_vault import ArchivedVault
from app.models.managed_vault import ManagedVault
from app.services.vault_catalog_service import (
    VaultCatalogError,
    VaultCatalogService,
    VaultNameError,
    VaultRestoreAuthenticationError,
)
from app.ui.icons import lucide_icon
from app.ui.message_dialog import MessageDialog
from app.ui.vault_manager_dialogs import RestoreArchivedVaultDialog
from app.ui.window_chrome import install_window_chrome
from app.utils.logging_config import get_logger


class ArchivedVaultsDialog(QDialog):
    def __init__(self, service: VaultCatalogService, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self._service = service
        self._restored: ManagedVault | None = None
        self._archives: dict[str, ArchivedVault] = {}
        self._list = QListWidget()
        self._list.setObjectName("archivedVaultList")
        self._name = QLabel("Selecione um arquivo")
        self._name.setObjectName("vaultSelectedName")
        self._details = QLabel()
        self._details.setObjectName("muted")
        self._details.setWordWrap(True)
        self._restore_button = QPushButton("Recuperar cofre")
        self.setObjectName("credentialDialog")
        self.setWindowTitle("Cofres arquivados")
        self.setMinimumSize(720, 500)
        self.resize(880, 580)
        self._build_ui()
        self._refresh()

    @property
    def restored_vault(self) -> ManagedVault | None:
        return self._restored

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 8, 18, 18)
        outer.setSpacing(16)
        install_window_chrome(self, outer, "Cofres arquivados", allow_maximize=True)

        header = QHBoxLayout()
        badge = QLabel()
        badge.setObjectName("dialogIconBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(54, 54)
        badge.setPixmap(lucide_icon("archive", "#dbeafe", 28).pixmap(28, 28))
        header.addWidget(badge)
        heading = QVBoxLayout()
        title = QLabel("Cofres arquivados")
        title.setObjectName("dialogTitle")
        heading.addWidget(title)
        subtitle = QLabel(
            "Recupere um cofre como item independente, sem alterar os cofres ativos."
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        outer.addLayout(header)

        content = QHBoxLayout()
        content.setSpacing(14)
        list_card = QFrame()
        list_card.setObjectName("vaultManagerSidebar")
        list_layout = QVBoxLayout(list_card)
        list_layout.setContentsMargins(10, 10, 10, 10)
        list_layout.addWidget(self._list)
        self._list.currentItemChanged.connect(self._selection_changed)
        self._list.itemDoubleClicked.connect(lambda _item: self._restore())
        content.addWidget(list_card, 5)

        details_card = QFrame()
        details_card.setObjectName("vaultManagerCard")
        details = QVBoxLayout(details_card)
        details.setContentsMargins(24, 24, 24, 22)
        details.setSpacing(13)
        icon = QLabel()
        icon.setObjectName("vaultDetailBadge")
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon.setFixedSize(60, 60)
        icon.setPixmap(lucide_icon("archive", "#bfdbfe", 29).pixmap(29, 29))
        details.addWidget(icon)
        details.addWidget(self._name)
        details.addWidget(self._details)
        details.addStretch()
        self._restore_button.setObjectName("primaryButton")
        self._restore_button.setIcon(lucide_icon("rotate-ccw", "#ffffff", 18))
        self._restore_button.setIconSize(QSize(18, 18))
        self._restore_button.setMinimumHeight(44)
        self._restore_button.clicked.connect(self._restore)
        details.addWidget(self._restore_button)
        content.addWidget(details_card, 4)
        outer.addLayout(content, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        close = QPushButton("Fechar")
        close.setObjectName("secondaryButton")
        close.setIcon(lucide_icon("x", "#e5e7eb", 17))
        close.clicked.connect(self.reject)
        close.setMinimumHeight(40)
        footer.addWidget(close)
        outer.addLayout(footer)

    def _refresh(self) -> None:
        self._list.clear()
        archives = self._service.list_archived()
        self._archives = {archive.archive_key: archive for archive in archives}
        for archive in archives:
            item = QListWidgetItem(archive.vault.name)
            item.setData(Qt.ItemDataRole.UserRole, archive.archive_key)
            item.setIcon(lucide_icon("archive", "#60a5fa", 20))
            item.setSizeHint(QSize(0, 52))
            self._list.addItem(item)
        if self._list.count():
            self._list.setCurrentRow(0)
        self._selection_changed(self._list.currentItem())

    def _selected(self) -> ArchivedVault | None:
        item = self._list.currentItem()
        if item is None:
            return None
        return self._archives.get(str(item.data(Qt.ItemDataRole.UserRole)))

    def _selection_changed(self, _current=None, _previous=None) -> None:  # type: ignore[no-untyped-def]
        archive = self._selected()
        self._restore_button.setEnabled(archive is not None)
        if archive is None:
            self._name.setText("Nenhum cofre arquivado")
            self._details.setText(
                "Quando um cofre for arquivado, ele aparecerá aqui para recuperação."
            )
            return
        archived_at = datetime.fromisoformat(archive.archived_at).astimezone().strftime(
            "%d/%m/%Y às %H:%M"
        )
        source = "Metadados originais preservados" if archive.has_manifest else "Arquivo da versão 0.7.0 reconhecido"
        self._name.setText(archive.vault.name)
        self._details.setText(
            f"Arquivado em {archived_at}\n\n{source}. A senha mestra original será exigida."
        )

    def _restore(self) -> None:
        archive = self._selected()
        if archive is None:
            return
        dialog = RestoreArchivedVaultDialog(archive.vault.name, self)
        try:
            if dialog.exec() != QDialog.DialogCode.Accepted:
                return
            restored = self._service.restore_archived(
                archive.archive_key,
                dialog.vault_name,
                dialog.master_password,
            )
        except VaultRestoreAuthenticationError:
            get_logger().warning("vault.archive_restore_authentication_failed")
            MessageDialog.warning(
                self,
                "Não foi possível autenticar o cofre arquivado.",
                title="Cofre não recuperado",
                detail="Confira a senha mestra e tente novamente.",
            )
            return
        except (VaultNameError, VaultCatalogError, TypeError, ValueError) as exc:
            get_logger().error("vault.archive_restore_failed type=%s", type(exc).__name__)
            MessageDialog.warning(self, str(exc), title="Cofre não recuperado")
            return
        finally:
            dialog.clear_secrets()
            dialog.deleteLater()
        get_logger().info("vault.archive_restored")
        self._restored = restored
        self.accept()
