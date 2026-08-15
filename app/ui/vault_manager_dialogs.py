"""Diálogos temáticos para criar, renomear e arquivar cofres."""

from __future__ import annotations

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


class NewVaultDialog(QDialog):
    def __init__(self, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self.setObjectName("credentialDialog")
        self.setWindowTitle("Novo cofre")
        self.setMinimumSize(560, 530)
        self.resize(640, 570)
        self._name = QLineEdit()
        self._password = QLineEdit()
        self._confirmation = QLineEdit()
        self._error = QLabel()
        self._password_visible = False
        self._build_ui()
        self._name.setFocus()

    @property
    def vault_name(self) -> str:
        return self._name.text()

    @property
    def master_password(self) -> str:
        return self._password.text()

    def clear_secrets(self) -> None:
        self._password.clear()
        self._confirmation.clear()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 8, 18, 18)
        outer.setSpacing(18)
        install_window_chrome(self, outer, "Novo cofre", allow_maximize=False)
        self._add_header(
            outer,
            "folder-plus",
            "Criar um cofre independente",
            "Ele terá senha mestra, credenciais e backups próprios.",
        )
        card = QFrame()
        card.setObjectName("dialogCard")
        form = QVBoxLayout(card)
        form.setContentsMargins(26, 24, 26, 24)
        form.setSpacing(10)
        self._name.setObjectName("newVaultName")
        self._name.setPlaceholderText("Ex.: Pessoal, Trabalho ou Família")
        self._name.setMaxLength(48)
        self._prepare_field(form, "Nome do cofre", self._name)

        for field in (self._password, self._confirmation):
            field.setEchoMode(QLineEdit.EchoMode.Password)
            field.setMinimumHeight(44)
        self._password.setObjectName("newVaultPassword")
        self._password.setPlaceholderText("Use pelo menos 12 caracteres")
        visibility = self._password.addAction(
            lucide_icon("eye", "#94a3b8", 18),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        visibility.triggered.connect(self._toggle_visibility)
        self._visibility_action = visibility
        self._prepare_field(form, "Senha mestra", self._password)
        self._confirmation.setObjectName("newVaultConfirmation")
        self._confirmation.setPlaceholderText("Repita a senha mestra")
        self._confirmation.returnPressed.connect(self._accept_if_valid)
        self._prepare_field(form, "Confirmar senha mestra", self._confirmation)

        warning = QLabel(
            "Cada cofre é isolado. Não existe recuperação da senha mestra e o nome "
            "fica visível na tela de seleção — não coloque segredos nele."
        )
        warning.setObjectName("warning")
        warning.setWordWrap(True)
        form.addWidget(warning)
        self._error.setObjectName("inlineError")
        self._error.setWordWrap(True)
        self._error.hide()
        form.addWidget(self._error)
        outer.addWidget(card, 1)
        self._add_footer(self, outer, "Criar cofre", "folder-plus", self._accept_if_valid)

    def _accept_if_valid(self) -> None:
        if not self._name.text().strip():
            self._show_error("Digite um nome para identificar o novo cofre.", self._name)
            return
        if len(self._password.text()) < 12:
            self._show_error("Use uma senha mestra com pelo menos 12 caracteres.", self._password)
            return
        if self._password.text() != self._confirmation.text():
            self._show_error("A confirmação não coincide com a senha mestra.", self._confirmation)
            return
        self._error.hide()
        self.accept()

    def _toggle_visibility(self) -> None:
        self._password_visible = not self._password_visible
        mode = (
            QLineEdit.EchoMode.Normal
            if self._password_visible
            else QLineEdit.EchoMode.Password
        )
        self._password.setEchoMode(mode)
        self._confirmation.setEchoMode(mode)
        self._visibility_action.setIcon(
            lucide_icon("eye-off" if self._password_visible else "eye", "#94a3b8", 18)
        )

    def _show_error(self, message: str, field: QLineEdit) -> None:
        self._error.setText(message)
        self._error.show()
        field.setFocus()

    @staticmethod
    def _prepare_field(layout: QVBoxLayout, text: str, field: QLineEdit) -> None:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        layout.addWidget(label)
        field.setMinimumHeight(44)
        layout.addWidget(field)

    @staticmethod
    def _add_header(
        layout: QVBoxLayout,
        icon: str,
        title_text: str,
        subtitle_text: str,
    ) -> None:
        header = QHBoxLayout()
        header.setSpacing(15)
        badge = QLabel()
        badge.setObjectName("dialogIconBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(54, 54)
        badge.setPixmap(lucide_icon(icon, "#dbeafe", 28).pixmap(28, 28))
        header.addWidget(badge)
        text = QVBoxLayout()
        title = QLabel(title_text)
        title.setObjectName("dialogTitle")
        text.addWidget(title)
        subtitle = QLabel(subtitle_text)
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        text.addWidget(subtitle)
        header.addLayout(text, 1)
        layout.addLayout(header)

    @staticmethod
    def _add_footer(
        dialog: QDialog,
        layout: QVBoxLayout,
        confirm_text: str,
        icon: str,
        callback,  # type: ignore[no-untyped-def]
    ) -> None:
        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("secondaryButton")
        cancel.setIcon(lucide_icon("x", "#e5e7eb", 18))
        cancel.clicked.connect(dialog.reject)
        NewVaultDialog._fit_button(cancel)
        footer.addWidget(cancel)
        confirm = QPushButton(confirm_text)
        confirm.setObjectName("primaryButton")
        confirm.setIcon(lucide_icon(icon, "#ffffff", 18))
        confirm.clicked.connect(callback)
        confirm.setDefault(True)
        NewVaultDialog._fit_button(confirm)
        footer.addWidget(confirm)
        layout.addLayout(footer)

    @staticmethod
    def _fit_button(button: QPushButton) -> None:
        button.setIconSize(QSize(18, 18))
        width = button.fontMetrics().horizontalAdvance(button.text())
        button.setMinimumWidth(width + 56)
        button.setMinimumHeight(42)


class RenameVaultDialog(QDialog):
    def __init__(self, current_name: str, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self.setObjectName("credentialDialog")
        self.setWindowTitle("Renomear cofre")
        self.setMinimumWidth(500)
        self._name = QLineEdit(current_name)
        self._name.setObjectName("renameVaultName")
        self._name.setMaxLength(48)
        self._error = QLabel()
        self._build_ui()
        self._name.selectAll()
        self._name.setFocus()

    @property
    def vault_name(self) -> str:
        return self._name.text()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 8, 18, 18)
        outer.setSpacing(18)
        install_window_chrome(self, outer, "Renomear cofre", allow_maximize=False)
        NewVaultDialog._add_header(
            outer,
            "pencil",
            "Renomear cofre",
            "O nome serve apenas para identificar o cofre antes do desbloqueio.",
        )
        card = QFrame()
        card.setObjectName("dialogCard")
        form = QVBoxLayout(card)
        form.setContentsMargins(24, 22, 24, 22)
        NewVaultDialog._prepare_field(form, "Novo nome", self._name)
        self._error.setObjectName("inlineError")
        self._error.hide()
        form.addWidget(self._error)
        outer.addWidget(card)
        self._name.returnPressed.connect(self._accept_if_valid)
        NewVaultDialog._add_footer(
            self,
            outer,
            "Salvar nome",
            "check",
            self._accept_if_valid,
        )

    def _accept_if_valid(self) -> None:
        if not self._name.text().strip():
            self._error.setText("Digite um nome para o cofre.")
            self._error.show()
            return
        self.accept()


class ArchiveVaultDialog(QDialog):
    def __init__(self, vault_name: str, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self._vault_name = vault_name
        self.setObjectName("credentialDialog")
        self.setWindowTitle("Arquivar cofre")
        self.setMinimumSize(540, 470)
        self._password = QLineEdit()
        self._confirmation_name = QLineEdit()
        self._error = QLabel()
        self._build_ui()

    @property
    def master_password(self) -> str:
        return self._password.text()

    def clear_secrets(self) -> None:
        self._password.clear()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 8, 18, 18)
        outer.setSpacing(18)
        install_window_chrome(self, outer, "Arquivar cofre", allow_maximize=False)
        NewVaultDialog._add_header(
            outer,
            "archive",
            f"Arquivar “{self._vault_name}”",
            "O cofre sairá da lista, mas seus arquivos serão preservados para recuperação.",
        )
        card = QFrame()
        card.setObjectName("dialogCard")
        form = QVBoxLayout(card)
        form.setContentsMargins(24, 22, 24, 22)
        form.setSpacing(10)
        self._password.setObjectName("archiveVaultPassword")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._password.setPlaceholderText("Senha mestra do cofre")
        NewVaultDialog._prepare_field(form, "Confirmar senha mestra", self._password)
        self._confirmation_name.setObjectName("archiveVaultConfirmation")
        self._confirmation_name.setPlaceholderText(self._vault_name)
        NewVaultDialog._prepare_field(
            form,
            f'Digite “{self._vault_name}” para confirmar',
            self._confirmation_name,
        )
        note = QLabel(
            "Credenciais e backups não serão apagados permanentemente. "
            "Eles serão movidos para a área local de cofres arquivados."
        )
        note.setObjectName("warning")
        note.setWordWrap(True)
        form.addWidget(note)
        self._error.setObjectName("inlineError")
        self._error.setWordWrap(True)
        self._error.hide()
        form.addWidget(self._error)
        outer.addWidget(card, 1)
        self._confirmation_name.returnPressed.connect(self._accept_if_valid)
        NewVaultDialog._add_footer(
            self,
            outer,
            "Arquivar cofre",
            "archive",
            self._accept_if_valid,
        )

    def _accept_if_valid(self) -> None:
        if not self._password.text():
            self._error.setText("Digite a senha mestra deste cofre.")
            self._error.show()
            return
        if self._confirmation_name.text() != self._vault_name:
            self._error.setText("O nome de confirmação não coincide exatamente.")
            self._error.show()
            return
        self.accept()
