"""Diálogo de opções do gerador de senhas."""

from __future__ import annotations

from PySide6.QtCore import QSize
from PySide6.QtWidgets import (
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
)

from app.services.password_generator import PasswordOptions, generate_password
from app.ui.icons import lucide_icon
from app.ui.message_dialog import MessageDialog
from app.ui.window_chrome import install_window_chrome


class PasswordGeneratorDialog(QDialog):
    """Permite configurar, gerar e aceitar uma senha segura."""

    def __init__(self, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self.setWindowTitle("Gerar senha")
        self.setMinimumWidth(360)

        self._length = QSpinBox()
        self._length.setRange(8, 128)
        self._length.setValue(20)
        self._uppercase = QCheckBox("Letras maiúsculas")
        self._lowercase = QCheckBox("Letras minúsculas")
        self._digits = QCheckBox("Números")
        self._symbols = QCheckBox("Símbolos")
        for checkbox in (self._uppercase, self._lowercase, self._digits, self._symbols):
            checkbox.setChecked(True)

        self._result = QLineEdit()
        self._result.setReadOnly(True)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(14, 8, 14, 14)
        install_window_chrome(
            self,
            layout,
            "Gerador de senha",
            allow_maximize=False,
        )
        form = QFormLayout()
        form.addRow("Comprimento", self._length)
        options = QVBoxLayout()
        options.addWidget(self._uppercase)
        options.addWidget(self._lowercase)
        options.addWidget(self._digits)
        options.addWidget(self._symbols)
        form.addRow("Caracteres", options)
        layout.addLayout(form)
        layout.addWidget(QLabel("Senha gerada"))

        result_row = QHBoxLayout()
        result_row.addWidget(self._result)
        generate_button = QPushButton("Gerar")
        generate_button.setIcon(lucide_icon("sparkles", "#e5e7eb", 18))
        generate_button.setIconSize(QSize(18, 18))
        generate_button.setMinimumWidth(
            generate_button.fontMetrics().horizontalAdvance(generate_button.text()) + 58
        )
        generate_button.setMinimumHeight(max(38, generate_button.fontMetrics().height() + 20))
        generate_button.clicked.connect(self._generate)
        result_row.addWidget(generate_button)
        layout.addLayout(result_row)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("Usar senha")
        buttons.accepted.connect(self._accept_if_valid)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self._generate()

    @property
    def password(self) -> str:
        return self._result.text()

    def _options(self) -> PasswordOptions:
        return PasswordOptions(
            length=self._length.value(),
            uppercase=self._uppercase.isChecked(),
            lowercase=self._lowercase.isChecked(),
            digits=self._digits.isChecked(),
            symbols=self._symbols.isChecked(),
        )

    def _generate(self) -> None:
        try:
            self._result.setText(generate_password(self._options()))
        except ValueError as exc:
            self._result.clear()
            MessageDialog.warning(self, str(exc), title="Opções inválidas")

    def _accept_if_valid(self) -> None:
        if not self._result.text():
            self._generate()
        if self._result.text():
            self.accept()
