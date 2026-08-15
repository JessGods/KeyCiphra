"""Smoke test das janelas sem abrir uma interface visível."""

from __future__ import annotations

import os
from pathlib import Path

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QFont  # noqa: E402
from PySide6.QtCore import Qt  # noqa: E402
from PySide6.QtWidgets import (  # noqa: E402
    QApplication,
    QComboBox,
    QFileDialog,
    QLineEdit,
    QListWidget,
    QPushButton,
    QScrollArea,
    QSpinBox,
)

from app.models.app_settings import AppSettings  # noqa: E402
from app.models.credential import Credential  # noqa: E402
from app.repositories.category_repository import CategoryRepository  # noqa: E402
from app.repositories.credential_repository import CredentialRepository  # noqa: E402
from app.security.kdf import KDFParameters  # noqa: E402
from app.services.backup_service import BackupService  # noqa: E402
from app.services.clipboard_service import ClipboardService  # noqa: E402
from app.services.category_service import CategoryService  # noqa: E402
from app.services.vault_service import VaultService  # noqa: E402
from app.ui.credential_dialog import CredentialDialog  # noqa: E402
from app.ui.category_manager_dialog import CategoryManagerDialog  # noqa: E402
from app.ui.login_window import LoginWindow  # noqa: E402
from app.ui.main_window import MainWindow  # noqa: E402
from app.ui.message_dialog import MessageDialog, MessageKind  # noqa: E402
from app.ui.password_generator_dialog import PasswordGeneratorDialog  # noqa: E402
from app.ui.settings_dialog import SettingsDialog  # noqa: E402
from app.ui.vault_restore_dialog import VaultRestoreDialog  # noqa: E402
from app.ui.window_chrome import WindowChrome  # noqa: E402


FAST_TEST_PARAMETERS = KDFParameters(
    time_cost=1,
    memory_cost_kib=8 * 1_024,
    parallelism=1,
)


def test_login_and_main_windows_initialize(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    database_path = tmp_path / "vault.db"
    vault_service = VaultService(database_path)

    login = LoginWindow(vault_service)
    session = vault_service.create(
        "frase-mestra-ficticia-longa",
        FAST_TEST_PARAMETERS,
    )
    repository = CredentialRepository(database_path, session)
    repository.add(
        Credential.create(
            title="Serviço fictício",
            username="teste@example.invalid",
            password="segredo-fictício",
            category="Teste",
        )
    )
    clipboard_service = ClipboardService(application.clipboard())
    category_service = CategoryService(CategoryRepository(database_path, session), repository)
    main = MainWindow(
        repository,
        session,
        clipboard_service,
        BackupService(database_path, tmp_path / "backups"),
        category_service=category_service,
    )
    assert main.initialize()
    credential_dialog = CredentialDialog(
        parent=main,
        categories=main._category_names(),
        manage_categories=main._manage_categories,
    )
    category_dialog = CategoryManagerDialog(
        category_service,
        main,
        populate_demo=main._populate_demo_data,
    )
    generator_dialog = PasswordGeneratorDialog(credential_dialog)
    message_dialog = MessageDialog(
        "Não foi possível desbloquear o cofre.",
        kind=MessageKind.WARNING,
        title="Cofre bloqueado",
        detail="Confira sua frase-senha e tente novamente.",
        parent=login,
    )
    restore_dialog = VaultRestoreDialog(database_path, main)
    settings_dialog = SettingsDialog(AppSettings(), main)

    assert login.windowTitle() == "KeyCiphra — Cofre local"
    assert main.windowTitle() == "KeyCiphra — Cofre desbloqueado"
    assert login.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert main.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert credential_dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert generator_dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert restore_dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert settings_dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert category_dialog.windowFlags() & Qt.WindowType.FramelessWindowHint
    assert login.findChild(WindowChrome) is not None
    assert main.findChild(WindowChrome) is not None
    assert credential_dialog.findChild(WindowChrome) is not None
    assert restore_dialog.findChild(WindowChrome) is not None
    assert settings_dialog.findChild(WindowChrome) is not None
    assert category_dialog.findChild(WindowChrome) is not None
    assert len(generator_dialog.password) == 20
    actions = main._table.cellWidget(0, 3)
    assert actions is not None
    assert main._table.columnWidth(3) >= actions.minimumWidth()
    action_buttons = actions.findChildren(QPushButton)
    assert action_buttons
    assert main._table.rowHeight(0) >= max(button.height() for button in action_buttons) + 10
    assert all(button.text() == "" for button in action_buttons)
    assert all(button.width() == button.height() for button in action_buttons)
    assert all(button.width() == 26 for button in action_buttons)
    assert {button.accessibleName() for button in action_buttons} == {
        "Copiar senha",
        "Editar credencial",
        "Excluir credencial",
    }
    assert credential_dialog.findChild(QScrollArea, "formScroll") is not None
    category_combo = credential_dialog.findChild(QComboBox, "credentialCategory")
    assert category_combo is not None
    assert category_combo.findText("Teste") >= 0
    category_filter = next(
        combo
        for combo in main.findChildren(QComboBox)
        if combo.accessibleName() == "Filtrar por categoria"
    )
    assert category_filter.findText("Teste") >= 0
    category_filter.setCurrentText("Teste")
    assert main._table.rowCount() == 1
    category_filter.setCurrentText("Sem categoria")
    assert main._table.rowCount() == 0
    assert category_dialog.findChild(QListWidget, "categoryList") is not None
    demo_button = next(
        button
        for button in category_dialog.findChildren(QPushButton)
        if button.text() == "Adicionar exemplos"
    )
    assert demo_button.isEnabled()
    assert message_dialog.objectName() == "messageDialog"
    assert message_dialog.minimumWidth() == 390
    restore_password = restore_dialog.findChild(QLineEdit, "restorePassword")
    assert restore_password is not None
    assert restore_password.echoMode() == QLineEdit.EchoMode.Password
    assert len(settings_dialog.findChildren(QSpinBox)) == 3
    assert settings_dialog.settings == AppSettings()
    assert all(
        spin.buttonSymbols() == QSpinBox.ButtonSymbols.NoButtons
        for spin in settings_dialog.findChildren(QSpinBox)
    )
    stepper_buttons = [
        button
        for button in settings_dialog.findChildren(QPushButton)
        if button.objectName() == "stepperButton"
    ]
    assert len(stepper_buttons) == 6
    decrease_auto_lock = next(
        button
        for button in stepper_buttons
        if button.accessibleName() == "Diminuir bloqueio automático"
    )
    decrease_auto_lock.click()
    assert settings_dialog.settings.auto_lock_minutes == 4

    backup_button = next(
        button for button in main.findChildren(QPushButton) if button.text() == "Backup"
    )
    backup_button.click()
    assert list((tmp_path / "backups").glob("vault_*.db"))
    transfer_button = next(
        button for button in main.findChildren(QPushButton) if button.text() == "Transferir"
    )
    assert transfer_button.menu() is not None
    assert {action.text() for action in transfer_button.menu().actions()} == {
        "Exportar cofre…",
        "Importar/Restaurar cofre…",
    }
    file_dialog = main._file_dialog("Selecionar cofre")
    assert file_dialog.testOption(QFileDialog.Option.DontUseNativeDialog)
    settings_button = next(
        button
        for button in main.findChildren(QPushButton)
        if button.accessibleName() == "Configurações"
    )
    assert settings_button.width() == settings_button.height() == 42

    clipboard_service.set_timeout_seconds(45)
    assert clipboard_service.timeout_seconds == 45
    main.apply_settings(AppSettings(clipboard_seconds=45))

    clipboard = application.clipboard()
    main._clipboard.copy_secret("segredo-temporario-ficticio")
    assert clipboard.text() == "segredo-temporario-ficticio"
    main.lock_vault()
    assert clipboard.text() == ""
    assert not session.is_unlocked

    message_dialog.close()
    file_dialog.close()
    restore_dialog.close()
    settings_dialog.close()
    category_dialog.close()
    generator_dialog.close()
    credential_dialog.close()
    main.close()
    login.close()


def test_action_column_expands_with_large_font(tmp_path: Path) -> None:
    application = QApplication.instance() or QApplication([])
    original_font = application.font()
    large_font = QFont(original_font)
    large_font.setPointSize(18)
    application.setFont(large_font)

    database_path = tmp_path / "large-font-vault.db"
    vault = VaultService(database_path)
    session = vault.create("frase-mestra-ficticia-longa", FAST_TEST_PARAMETERS)
    repository = CredentialRepository(database_path, session)
    repository.add(Credential.create(title="Teste", password="segredo-fictício"))
    main = MainWindow(
        repository,
        session,
        ClipboardService(application.clipboard()),
        category_service=CategoryService(
            CategoryRepository(database_path, session),
            repository,
        ),
    )

    try:
        assert main.initialize()
        actions = main._table.cellWidget(0, 3)
        assert actions is not None
        assert main._table.columnWidth(3) >= actions.minimumWidth()
        assert main.minimumWidth() == 680
    finally:
        main.close()
        application.setFont(original_font)
