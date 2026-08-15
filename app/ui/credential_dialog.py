"""Cadastro e edição de credenciais."""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import replace

from PySide6.QtCore import QSize, Qt, QTimer
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from app.models.credential import Credential
from app.ui.icons import lucide_icon
from app.ui.message_dialog import MessageDialog
from app.ui.password_generator_dialog import PasswordGeneratorDialog
from app.ui.window_chrome import install_window_chrome


class CredentialDialog(QDialog):
    """Edita dados apenas em memória até o usuário confirmar."""

    def __init__(
        self,
        credential: Credential | None = None,
        parent=None,  # type: ignore[no-untyped-def]
        *,
        categories: Iterable[str] = (),
        manage_categories: Callable[[QWidget], list[str]] | None = None,
    ) -> None:
        super().__init__(parent)
        self._original = credential
        self._manage_categories_callback = manage_categories
        self._password_visible = False
        self.setObjectName("credentialDialog")
        self.setWindowTitle("Editar credencial" if credential else "Nova credencial")
        self.setMinimumSize(520, 500)
        self.resize(760, 700)

        self._title = self._line_edit("Ex.: E-mail pessoal")
        self._username = self._line_edit("usuario@exemplo.com")
        self._password = self._line_edit("Digite ou gere uma senha")
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._url = self._line_edit("https://exemplo.com/login")
        self._category = QComboBox()
        self._category.setObjectName("credentialCategory")
        self._category.setMinimumHeight(max(44, self._category.fontMetrics().height() + 24))
        self._refresh_categories(categories, credential.category if credential else "")
        self._notes = QTextEdit()
        self._notes.setPlaceholderText("Informações adicionais sobre esta credencial...")
        self._notes.setMinimumHeight(145)
        self._reveal_timer = QTimer(self)
        self._reveal_timer.setSingleShot(True)
        self._reveal_timer.timeout.connect(self._hide_password)

        self._build_ui()
        if credential is not None:
            self._fill(credential)
        self._title.setFocus()

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 8, 18, 18)
        outer.setSpacing(20)
        install_window_chrome(
            self,
            outer,
            "Editar credencial" if self._original else "Nova credencial",
            allow_maximize=False,
        )

        header = QHBoxLayout()
        header.setSpacing(15)
        icon_badge = QLabel()
        icon_badge.setObjectName("dialogIconBadge")
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setFixedSize(54, 54)
        icon_badge.setPixmap(lucide_icon("shield-check", "#dbeafe", 29).pixmap(29, 29))
        header.addWidget(icon_badge)

        heading = QVBoxLayout()
        heading.setSpacing(3)
        title = QLabel("Editar credencial" if self._original else "Adicionar credencial")
        title.setObjectName("dialogTitle")
        heading.addWidget(title)
        subtitle = QLabel(
            "Atualize os dados protegidos deste acesso."
            if self._original
            else "Os campos abaixo serão criptografados antes de chegar ao banco."
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
        form.setSpacing(15)

        form.addWidget(self._field("Título *", self._title))

        form.addWidget(self._field("Usuário", self._username))
        form.addWidget(self._category_field())

        password_field = QWidget()
        password_layout = QVBoxLayout(password_field)
        password_layout.setContentsMargins(0, 0, 0, 0)
        password_layout.setSpacing(7)
        password_layout.addWidget(self._field_label("Senha"))
        password_row = QHBoxLayout()
        password_row.setSpacing(10)
        visibility_action = self._password.addAction(
            lucide_icon("eye", "#94a3b8", 18),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        visibility_action.setToolTip("Mostrar por 10 segundos")
        visibility_action.triggered.connect(self._toggle_password_visibility)
        self._visibility_action = visibility_action
        password_row.addWidget(self._password, 1)
        generate_button = QPushButton("Gerar senha")
        generate_button.setIcon(lucide_icon("sparkles", "#e5e7eb", 18))
        generate_button.setIconSize(QSize(18, 18))
        self._fit_button(generate_button)
        generate_button.clicked.connect(self._open_generator)
        password_row.addWidget(generate_button)
        password_layout.addLayout(password_row)
        form.addWidget(password_field)

        form.addWidget(self._field("Endereço do site", self._url))
        form.addWidget(self._field("Notas", self._notes))
        scroll_area = QScrollArea()
        scroll_area.setObjectName("formScroll")
        scroll_area.setWidgetResizable(True)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setWidget(card)
        outer.addWidget(scroll_area, 1)

        footer = QHBoxLayout()
        security_note = QLabel("Protegido com AES-256-GCM")
        security_note.setObjectName("securityNote")
        footer.addWidget(security_note)
        footer.addStretch()

        cancel_button = QPushButton("Cancelar")
        cancel_button.setObjectName("secondaryButton")
        cancel_button.setIcon(lucide_icon("x", "#e5e7eb", 18))
        cancel_button.setIconSize(QSize(18, 18))
        self._fit_button(cancel_button)
        cancel_button.clicked.connect(self.reject)
        footer.addWidget(cancel_button)

        save_button = QPushButton("Salvar credencial")
        save_button.setObjectName("primaryButton")
        save_button.setIcon(lucide_icon("check", "#ffffff", 18))
        save_button.setIconSize(QSize(18, 18))
        self._fit_button(save_button)
        save_button.setDefault(True)
        save_button.clicked.connect(self._validate_and_accept)
        footer.addWidget(save_button)
        outer.addLayout(footer)

    @staticmethod
    def _line_edit(placeholder: str) -> QLineEdit:
        widget = QLineEdit()
        widget.setPlaceholderText(placeholder)
        widget.setClearButtonEnabled(True)
        widget.setMinimumHeight(max(44, widget.fontMetrics().height() + 24))
        return widget

    @classmethod
    def _field(cls, label_text: str, widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        layout.addWidget(cls._field_label(label_text))
        layout.addWidget(widget)
        return container

    def _category_field(self) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(7)
        layout.addWidget(self._field_label("Categoria"))
        row = QHBoxLayout()
        row.setSpacing(10)
        row.addWidget(self._category, 1)
        manage_button = QPushButton("Gerenciar")
        manage_button.setIcon(lucide_icon("tags", "#e5e7eb", 17))
        manage_button.setIconSize(QSize(17, 17))
        self._fit_button(manage_button)
        manage_button.setEnabled(self._manage_categories_callback is not None)
        manage_button.setToolTip("Criar, renomear ou excluir categorias")
        manage_button.clicked.connect(self._open_category_manager)
        row.addWidget(manage_button)
        layout.addLayout(row)
        return container

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    def credential(self) -> Credential:
        values = {
            "title": self._title.text().strip(),
            "username": self._username.text(),
            "password": self._password.text(),
            "url": self._url.text().strip(),
            "category": str(self._category.currentData() or ""),
            "notes": self._notes.toPlainText(),
        }
        if self._original is None:
            return Credential.create(**values)
        return replace(self._original, **values)

    def _fill(self, credential: Credential) -> None:
        self._title.setText(credential.title)
        self._username.setText(credential.username)
        self._password.setText(credential.password)
        self._url.setText(credential.url)
        index = self._category.findData(credential.category)
        self._category.setCurrentIndex(max(0, index))
        self._notes.setPlainText(credential.notes)

    def _refresh_categories(self, categories: Iterable[str], selected: str = "") -> None:
        names = sorted(
            {name.strip() for name in categories if name.strip()},
            key=str.casefold,
        )
        if selected and selected not in names:
            names.append(selected)
            names.sort(key=str.casefold)
        self._category.clear()
        self._category.addItem("Sem categoria", "")
        for name in names:
            self._category.addItem(name, name)
        index = self._category.findData(selected)
        self._category.setCurrentIndex(max(0, index))

    def _open_category_manager(self) -> None:
        if self._manage_categories_callback is None:
            return
        selected = str(self._category.currentData() or "")
        categories = self._manage_categories_callback(self)
        self._refresh_categories(categories, selected)

    def _open_generator(self) -> None:
        dialog = PasswordGeneratorDialog(self)
        if dialog.exec() == QDialog.DialogCode.Accepted:
            self._password.setText(dialog.password)

    def _toggle_password_visibility(self) -> None:
        self._password_visible = not self._password_visible
        if self._password_visible:
            self._password.setEchoMode(QLineEdit.EchoMode.Normal)
            self._visibility_action.setIcon(lucide_icon("eye-off", "#94a3b8", 18))
            self._reveal_timer.start(10_000)
        else:
            self._hide_password()

    def _hide_password(self) -> None:
        self._password_visible = False
        self._password.setEchoMode(QLineEdit.EchoMode.Password)
        self._visibility_action.setIcon(lucide_icon("eye", "#94a3b8", 18))
        self._reveal_timer.stop()

    @staticmethod
    def _fit_button(button: QPushButton) -> None:
        icon_width = button.iconSize().width() + 8 if not button.icon().isNull() else 0
        button.setMinimumWidth(button.fontMetrics().horizontalAdvance(button.text()) + icon_width + 30)
        button.setMinimumHeight(max(40, button.fontMetrics().height() + 20))
        button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)

    def _validate_and_accept(self) -> None:
        if not self._title.text().strip():
            MessageDialog.warning(
                self,
                "Informe um título para identificar esta credencial.",
                title="Título obrigatório",
            )
            self._title.setFocus()
            return
        self.accept()
