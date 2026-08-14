"""Confirmação temática e autenticada para restaurar um cofre."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QVBoxLayout,
)

from app.ui.icons import lucide_icon
from app.ui.window_chrome import install_window_chrome


class VaultRestoreDialog(QDialog):
    """Solicita a senha sem persistir ou registrar seu conteúdo."""

    def __init__(self, backup_path: Path, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self._backup_path = Path(backup_path)
        self._password_visible = False
        self.setObjectName("credentialDialog")
        self.setWindowTitle("Importar cofre")
        self.setMinimumWidth(540)
        self.resize(640, 440)

        self._password = QLineEdit()
        self._password.setObjectName("restorePassword")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Digite a senha mestra deste backup")
        self._password.setMinimumHeight(44)
        self._error = QLabel()
        self._error.setObjectName("inlineError")
        self._error.setWordWrap(True)
        self._error.hide()
        self._build_ui()
        self._password.setFocus()

    @property
    def backup_path(self) -> Path:
        return self._backup_path

    @property
    def master_password(self) -> str:
        return self._password.text()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 8, 18, 18)
        outer.setSpacing(18)
        install_window_chrome(self, outer, "Importar cofre", allow_maximize=False)

        header = QHBoxLayout()
        header.setSpacing(15)
        icon_badge = QLabel()
        icon_badge.setObjectName("dialogIconBadge")
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setFixedSize(54, 54)
        icon_badge.setPixmap(lucide_icon("restore", "#dbeafe", 29).pixmap(29, 29))
        header.addWidget(icon_badge)

        heading = QVBoxLayout()
        heading.setSpacing(3)
        title = QLabel("Restaurar cofre criptografado")
        title.setObjectName("dialogTitle")
        heading.addWidget(title)
        subtitle = QLabel(
            "A senha será usada somente em memória para autenticar o arquivo selecionado."
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        outer.addLayout(header)

        card = QFrame()
        card.setObjectName("dialogCard")
        form = QVBoxLayout(card)
        form.setContentsMargins(24, 22, 24, 22)
        form.setSpacing(11)

        file_label = QLabel("Arquivo selecionado")
        file_label.setObjectName("fieldLabel")
        form.addWidget(file_label)
        selected_file = QLabel(str(self._backup_path))
        selected_file.setObjectName("selectedVaultPath")
        selected_file.setWordWrap(True)
        selected_file.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        form.addWidget(selected_file)

        password_label = QLabel("Senha mestra do backup")
        password_label.setObjectName("fieldLabel")
        form.addWidget(password_label)
        visibility = self._password.addAction(
            lucide_icon("eye", "#94a3b8", 18),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        visibility.setToolTip("Mostrar senha")
        visibility.triggered.connect(self._toggle_password_visibility)
        self._visibility_action = visibility
        self._password.returnPressed.connect(self._validate_and_accept)
        form.addWidget(self._password)
        form.addWidget(self._error)

        safety_note = QLabel(
            "O KeyCiphra validará todas as credenciais e criará um backup do cofre atual antes da troca."
        )
        safety_note.setObjectName("restoreSafetyNote")
        safety_note.setWordWrap(True)
        form.addWidget(safety_note)
        outer.addWidget(card, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel_button = QPushButton("Cancelar")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.setIcon(lucide_icon("x", "#e5e7eb", 18))
        cancel_button.setIconSize(QSize(18, 18))
        self._fit_button(cancel_button)
        cancel_button.clicked.connect(self.reject)
        footer.addWidget(cancel_button)

        restore_button = QPushButton("Validar e restaurar")
        restore_button.setObjectName("primaryButton")
        restore_button.setIcon(lucide_icon("restore", "#ffffff", 18))
        restore_button.setIconSize(QSize(18, 18))
        self._fit_button(restore_button)
        restore_button.setDefault(True)
        restore_button.clicked.connect(self._validate_and_accept)
        footer.addWidget(restore_button)
        outer.addLayout(footer)

    def _toggle_password_visibility(self) -> None:
        self._password_visible = not self._password_visible
        self._password.setEchoMode(
            QLineEdit.EchoMode.Normal
            if self._password_visible
            else QLineEdit.EchoMode.Password
        )
        icon = "eye-off" if self._password_visible else "eye"
        self._visibility_action.setIcon(lucide_icon(icon, "#94a3b8", 18))

    def _validate_and_accept(self) -> None:
        if not self._password.text():
            self._error.setText("Digite a senha mestra usada para proteger este backup.")
            self._error.show()
            self._password.setFocus()
            return
        self._error.hide()
        self.accept()

    @staticmethod
    def _fit_button(button: QPushButton) -> None:
        text_width = button.fontMetrics().horizontalAdvance(button.text())
        button.setMinimumWidth(text_width + button.iconSize().width() + 38)
        button.setMinimumHeight(max(40, button.fontMetrics().height() + 20))
