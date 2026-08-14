"""Bootstrap da aplicação desktop KeyCiphra."""

from __future__ import annotations

import signal
import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from app.repositories.credential_repository import CredentialRepository
from app.security.auto_lock import AutoLockManager
from app.security.session import VaultSession
from app.services.backup_service import BackupError, BackupService
from app.services.clipboard_service import ClipboardService
from app.services.vault_service import VaultService
from app.ui.icons import lucide_icon
from app.ui.login_window import LoginWindow, as_vault_session
from app.ui.main_window import MainWindow
from app.ui.message_dialog import MessageDialog
from app.utils.paths import BACKUP_DIRECTORY, DEFAULT_VAULT_PATH


AUTO_LOCK_SECONDS = 5 * 60
SIGNAL_POLL_INTERVAL_MS = 200


def install_graceful_interrupt_handler(application: QApplication) -> QTimer:
    """Converte Ctrl+C em encerramento normal do loop Qt, sem traceback."""

    def request_shutdown(signum: int, frame: object) -> None:
        del signum, frame
        application.quit()

    signal.signal(signal.SIGINT, request_shutdown)
    if hasattr(signal, "SIGBREAK"):
        signal.signal(signal.SIGBREAK, request_shutdown)

    # Mantém o interpretador recebendo sinais mesmo quando o Qt está ocioso.
    poller = QTimer(application)
    poller.setInterval(SIGNAL_POLL_INTERVAL_MS)
    poller.timeout.connect(lambda: None)
    poller.start()
    return poller


APP_STYLESHEET = """
QWidget {
    color: #e5e7eb;
    font-family: "Segoe UI";
}
QWidget#mainRoot, QWidget#loginRoot, QDialog {
    background-color: #0f172a;
}
QWidget#windowChrome { background: transparent; }
QLabel#windowChromeTitle {
    color: #94a3b8;
    font-size: 9pt;
    font-weight: 600;
}
QPushButton#windowControlButton, QPushButton#windowCloseButton {
    background-color: transparent;
    border: 0;
    border-radius: 6px;
    padding: 0;
}
QPushButton#windowControlButton:hover { background-color: #263449; }
QPushButton#windowCloseButton:hover { background-color: #b91c1c; }
QWidget#loginRoot {
    background: qradialgradient(cx:0.50, cy:0.42, radius:0.85,
        fx:0.50, fy:0.42, stop:0 #17233a, stop:0.62 #111827, stop:1 #0b1220);
}
QFrame#authShell {
    background-color: #1f2937;
    border: 1px solid #334155;
    border-radius: 22px;
}
QFrame#authHero {
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 #1d4ed8, stop:0.55 #2563eb, stop:1 #0e7490);
    border: 0;
    border-radius: 16px;
}
QFrame#authForm {
    background-color: #1f2937;
    border: 0;
    border-radius: 16px;
}
QDialog#credentialDialog {
    background: qradialgradient(cx:0.15, cy:0.05, radius:1.1,
        fx:0.15, fy:0.05, stop:0 #172554, stop:0.34 #111827, stop:1 #0b1220);
}
QFrame#dialogCard {
    background-color: #111b2e;
    border: 1px solid #334155;
    border-radius: 14px;
}
QDialog#messageDialog { background: transparent; }
QFrame#messagePanel {
    background-color: #111b2e;
    border: 1px solid #334155;
    border-radius: 16px;
}
QLabel#messageIconBadge {
    background-color: #1e293b;
    border: 1px solid #475569;
    border-radius: 25px;
}
QLabel#messageIconBadge[kind="warning"] {
    background-color: #3b2a0b;
    border-color: #854d0e;
}
QLabel#messageIconBadge[kind="error"],
QLabel#messageIconBadge[kind="confirmation"] {
    background-color: #3f171b;
    border-color: #7f1d1d;
}
QLabel#messageTitle {
    color: #f8fafc;
    font-size: 14pt;
    font-weight: 700;
}
QLabel#messageBody { color: #dbe4f0; }
QLabel#messageDetail { color: #94a3b8; font-size: 9pt; }
QFrame#messageDivider { color: #273449; background-color: #273449; max-height: 1px; }
QLabel { background: transparent; }
QLabel#authIconBadge {
    background-color: rgba(255, 255, 255, 32);
    border: 1px solid rgba(255, 255, 255, 55);
    border-radius: 35px;
}
QLabel#heroBrand {
    color: #dbeafe;
    font-size: 12pt;
    font-weight: 700;
    letter-spacing: 3px;
}
QLabel#heroTitle {
    color: #ffffff;
    font-size: 21pt;
    font-weight: 700;
}
QLabel#heroText { color: #dbeafe; line-height: 1.4; }
QLabel#privacyLabel {
    color: #bfdbfe;
    font-size: 8pt;
    font-weight: 600;
    letter-spacing: 1px;
}
QLabel#eyebrow {
    color: #60a5fa;
    font-size: 8pt;
    font-weight: 700;
    letter-spacing: 1px;
}
QLabel#authTitle {
    color: #f8fafc;
    font-size: 20pt;
    font-weight: 700;
}
QLabel#dialogIconBadge {
    background-color: #1d4ed8;
    border: 1px solid #3b82f6;
    border-radius: 26px;
}
QLabel#dialogTitle {
    color: #f8fafc;
    font-size: 18pt;
    font-weight: 700;
}
QLabel#dialogSubtitle { color: #94a3b8; }
QLabel#securityNote {
    color: #60a5fa;
    font-size: 9pt;
    font-weight: 600;
}
QLabel#fieldLabel {
    color: #cbd5e1;
    font-weight: 600;
}
QLabel#brand {
    color: #60a5fa;
    font-size: 18pt;
    font-weight: 700;
    letter-spacing: 2px;
}
QLabel#muted { color: #9ca3af; }
QLabel#warning {
    color: #fde68a;
    background-color: #3b2a0b;
    border: 1px solid #713f12;
    border-radius: 9px;
    padding: 10px;
}
QLabel#sessionNotice {
    color: #bfdbfe;
    background-color: #172554;
    border: 1px solid #1d4ed8;
    border-radius: 8px;
    padding: 9px;
}
QLabel#selectedVaultPath {
    color: #bfdbfe;
    background-color: #0f172a;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 10px;
}
QLabel#restoreSafetyNote {
    color: #a7f3d0;
    background-color: #0f2924;
    border: 1px solid #166534;
    border-radius: 8px;
    padding: 10px;
}
QLabel#inlineError { color: #fca5a5; }
QLineEdit, QTextEdit, QSpinBox, QTableWidget {
    background-color: #0f172a;
    border: 1px solid #374151;
    border-radius: 7px;
    padding: 8px;
    selection-background-color: #2563eb;
}
QLineEdit:focus, QTextEdit:focus, QSpinBox:focus { border: 1px solid #60a5fa; }
QPushButton {
    background-color: #374151;
    border: 1px solid transparent;
    border-radius: 7px;
    padding: 8px 13px;
}
QPushButton:hover { background-color: #475569; border-color: #64748b; }
QPushButton:disabled { color: #6b7280; background-color: #1f2937; }
QPushButton#primaryButton { background-color: #2563eb; font-weight: 600; }
QPushButton#primaryButton:hover { background-color: #3b82f6; }
QPushButton#dangerButton { color: #fecaca; background-color: #7f1d1d; }
QPushButton#dangerButton:hover { background-color: #991b1b; border-color: #ef4444; }
QPushButton#secondaryButton { background-color: transparent; border-color: #475569; }
QPushButton#destructiveButton {
    color: #ffffff;
    background-color: #b91c1c;
    font-weight: 600;
}
QPushButton#destructiveButton:hover { background-color: #dc2626; border-color: #f87171; }
QPushButton#compactActionButton { padding: 4px 9px; border-radius: 6px; }
QPushButton[danger="true"] { color: #fecaca; background-color: #7f1d1d; }
QPushButton[danger="true"]:hover { background-color: #991b1b; border-color: #ef4444; }
QMenu {
    color: #e5e7eb;
    background-color: #111b2e;
    border: 1px solid #334155;
    border-radius: 8px;
    padding: 6px;
}
QMenu::item { padding: 9px 28px 9px 10px; border-radius: 6px; }
QMenu::item:selected { background-color: #2563eb; color: #ffffff; }
QFileDialog { background-color: #0f172a; }
QFileDialog QListView, QFileDialog QTreeView {
    color: #e5e7eb;
    background-color: #0b1220;
    border: 1px solid #334155;
    selection-background-color: #2563eb;
    selection-color: #ffffff;
}
QFileDialog QComboBox {
    color: #e5e7eb;
    background-color: #111b2e;
    border: 1px solid #374151;
    border-radius: 7px;
    padding: 7px;
}
QHeaderView::section {
    background-color: #1f2937;
    color: #d1d5db;
    border: 0;
    padding: 10px;
}
QTableWidget {
    gridline-color: #273244;
    alternate-background-color: #162033;
    border-radius: 10px;
}
QTableWidget::item { padding: 7px; border-bottom: 1px solid #273244; }
QTableWidget::item:selected { background-color: #2563eb; color: #ffffff; }
QWidget#tableActions { background: transparent; }
QStatusBar {
    color: #94a3b8;
    background-color: #0f172a;
    border-top: 1px solid #273449;
    padding: 3px 8px;
}
QStatusBar::item { border: 0; }
QScrollArea, QScrollArea > QWidget > QWidget {
    background: transparent;
    border: 0;
}
QScrollBar:vertical {
    background: #0b1220;
    width: 12px;
    margin: 3px 2px 3px 2px;
    border: 0;
    border-radius: 5px;
}
QScrollBar::handle:vertical {
    background: #334155;
    min-height: 32px;
    border-radius: 4px;
}
QScrollBar::handle:vertical:hover { background: #3b82f6; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical { background: transparent; }
QScrollBar:horizontal {
    background: #0b1220;
    height: 12px;
    margin: 2px 3px 2px 3px;
    border: 0;
    border-radius: 5px;
}
QScrollBar::handle:horizontal {
    background: #334155;
    min-width: 32px;
    border-radius: 4px;
}
QScrollBar::handle:horizontal:hover { background: #3b82f6; }
QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal { width: 0; }
QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal { background: transparent; }
QToolTip {
    color: #f8fafc;
    background-color: #1e293b;
    border: 1px solid #475569;
    padding: 5px;
}
"""


class ApplicationController:
    """Troca janelas e conserva somente os serviços necessários."""

    def __init__(self, application: QApplication) -> None:
        self._application = application
        self._vault_service = VaultService(DEFAULT_VAULT_PATH)
        self._backup_service = BackupService(
            DEFAULT_VAULT_PATH,
            BACKUP_DIRECTORY,
            retention=10,
        )
        self._clipboard = ClipboardService(application.clipboard())
        self._auto_lock = AutoLockManager(application, AUTO_LOCK_SECONDS)
        self._auto_lock.timed_out.connect(self._handle_auto_lock)
        self._pending_login_notice: str | None = None
        self._login_window: LoginWindow | None = None
        self._main_window: MainWindow | None = None
        self._shutting_down = False

    def start(self) -> None:
        self.show_login()

    def show_login(self) -> None:
        self._auto_lock.stop()
        if self._main_window is not None:
            self._main_window.close()
            self._main_window = None
        self._login_window = LoginWindow(
            self._vault_service,
            notice=self._pending_login_notice,
        )
        self._pending_login_notice = None
        self._login_window.unlocked.connect(self.show_main)
        self._login_window.show()

    def show_main(self, session_value: object) -> None:
        session = as_vault_session(session_value)
        repository = CredentialRepository(DEFAULT_VAULT_PATH, session)
        self._main_window = MainWindow(
            repository,
            session,
            self._clipboard,
            self._backup_service,
        )
        self._main_window.lock_requested.connect(self.show_login)
        self._main_window.vault_restored.connect(self._handle_vault_restored)
        if not self._main_window.initialize():
            self._main_window = None
            self.show_login()
            return
        self._main_window.show()
        if self._login_window is not None:
            self._login_window.close()
            self._login_window = None
        self._auto_lock.start()
        try:
            backup = self._backup_service.create_if_due()
            if backup is not None:
                self._main_window.notify_backup_created(backup.name)
        except BackupError:
            MessageDialog.warning(
                self._main_window,
                "O cofre abriu normalmente, mas o backup automático não pôde ser criado.",
                title="Backup pendente",
            )

    def _handle_auto_lock(self) -> None:
        if self._main_window is None:
            return
        self._pending_login_notice = "Cofre bloqueado automaticamente após 5 minutos sem atividade."
        self._main_window.lock_vault()

    def _handle_vault_restored(self, notice: str) -> None:
        self._pending_login_notice = notice
        self.show_login()

    def shutdown(self) -> None:
        """Descarta segredos transitórios antes de encerrar o processo."""
        if self._shutting_down:
            return
        self._shutting_down = True
        self._auto_lock.stop()
        self._clipboard.clear_secret()
        if self._main_window is not None:
            window = self._main_window
            self._main_window = None
            window.close()
        if self._login_window is not None:
            window = self._login_window
            self._login_window = None
            window.close()


def main() -> int:
    application = QApplication(sys.argv)
    application.setApplicationName("KeyCiphra")
    application.setApplicationDisplayName("KeyCiphra")
    application.setStyle("Fusion")
    application.setStyleSheet(APP_STYLESHEET)
    application.setWindowIcon(lucide_icon("shield-check", "#60a5fa", 32))
    controller = ApplicationController(application)
    interrupt_poller = install_graceful_interrupt_handler(application)
    application.aboutToQuit.connect(controller.shutdown)
    controller.start()
    try:
        return application.exec()
    except KeyboardInterrupt:
        # Proteção adicional para interrupções recebidas antes do handler do Qt.
        controller.shutdown()
        return 130
    finally:
        interrupt_poller.stop()


if __name__ == "__main__":
    raise SystemExit(main())
