"""Tela de criação ou desbloqueio do cofre."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt, Signal
from PySide6.QtWidgets import (
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.security.session import VaultSession
from app.services.vault_service import VaultService, VaultUnlockError
from app.ui.icons import lucide_icon
from app.ui.message_dialog import MessageDialog
from app.ui.window_chrome import install_window_chrome


class LoginWindow(QMainWindow):
    """Solicita a senha mestra sem mantê-la após a tentativa."""

    unlocked = Signal(object)

    def __init__(self, vault_service: VaultService, notice: str | None = None) -> None:
        super().__init__()
        self._vault_service = vault_service
        self._notice = notice
        self._is_first_access = not vault_service.exists()
        self._password_visible = False
        self._password_input = QLineEdit()
        self._confirmation_input: QLineEdit | None = None
        self._action_button = QPushButton()

        self.setWindowTitle("KeyCiphra — Cofre local")
        self.setMinimumSize(680, 500 if not self._is_first_access else 580)
        self.resize(840, 570 if not self._is_first_access else 650)
        self._build_ui()

    def _build_ui(self) -> None:
        root = QWidget()
        root.setObjectName("loginRoot")
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(16, 10, 16, 24)
        root_layout.setSpacing(10)
        install_window_chrome(
            self,
            root_layout,
            "KeyCiphra",
            allow_maximize=True,
        )

        shell = QFrame()
        shell.setObjectName("authShell")
        shell.setMaximumWidth(900)
        shell.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        shell_layout = QHBoxLayout(shell)
        shell_layout.setContentsMargins(10, 10, 10, 10)
        shell_layout.setSpacing(0)

        hero = QFrame()
        hero.setObjectName("authHero")
        hero.setMinimumWidth(265)
        hero.setMaximumWidth(315)
        hero_layout = QVBoxLayout(hero)
        hero_layout.setContentsMargins(32, 34, 32, 34)
        hero_layout.setSpacing(14)

        icon_badge = QLabel()
        icon_badge.setObjectName("authIconBadge")
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setFixedSize(72, 72)
        icon_badge.setPixmap(lucide_icon("shield-check", "#eff6ff", 42).pixmap(42, 42))
        hero_layout.addWidget(icon_badge, 0, Qt.AlignmentFlag.AlignLeft)

        brand = QLabel("KEYCIPHRA")
        brand.setObjectName("heroBrand")
        hero_layout.addWidget(brand)

        hero_title = QLabel("Seu cofre.\nSomente seu.")
        hero_title.setObjectName("heroTitle")
        hero_layout.addWidget(hero_title)

        hero_text = QLabel(
            "Credenciais protegidas localmente, sem depender de uma conta na nuvem."
        )
        hero_text.setObjectName("heroText")
        hero_text.setWordWrap(True)
        hero_layout.addWidget(hero_text)
        hero_layout.addStretch()

        privacy = QLabel("LOCAL  •  OFFLINE  •  CRIPTOGRAFADO")
        privacy.setObjectName("privacyLabel")
        privacy.setWordWrap(True)
        hero_layout.addWidget(privacy)
        shell_layout.addWidget(hero)

        form_panel = QFrame()
        form_panel.setObjectName("authForm")
        form_layout = QVBoxLayout(form_panel)
        form_layout.setContentsMargins(42, 38, 42, 36)
        form_layout.setSpacing(11)

        eyebrow = QLabel("PRIMEIRO ACESSO" if self._is_first_access else "BEM-VINDO DE VOLTA")
        eyebrow.setObjectName("eyebrow")
        form_layout.addWidget(eyebrow)

        title = QLabel("Criar cofre seguro" if self._is_first_access else "Desbloquear cofre")
        title.setObjectName("authTitle")
        form_layout.addWidget(title)

        subtitle = QLabel(
            "Crie uma frase-senha longa para proteger este cofre."
            if self._is_first_access
            else "Digite sua frase-senha para acessar suas credenciais."
        )
        subtitle.setObjectName("muted")
        subtitle.setWordWrap(True)
        form_layout.addWidget(subtitle)
        if self._notice:
            notice = QLabel(self._notice)
            notice.setObjectName("sessionNotice")
            notice.setWordWrap(True)
            form_layout.addWidget(notice)
        form_layout.addSpacing(12)

        form_layout.addWidget(self._field_label("Senha mestra"))
        self._prepare_password_input(self._password_input, "Digite sua frase-senha")
        visibility_action = self._password_input.addAction(
            lucide_icon("eye", "#94a3b8", 19),
            QLineEdit.ActionPosition.TrailingPosition,
        )
        visibility_action.setToolTip("Mostrar ou ocultar senha")
        visibility_action.triggered.connect(self._toggle_password_visibility)
        self._visibility_action = visibility_action
        form_layout.addWidget(self._password_input)

        if self._is_first_access:
            form_layout.addWidget(self._field_label("Confirmar senha mestra"))
            self._confirmation_input = QLineEdit()
            self._prepare_password_input(
                self._confirmation_input,
                "Repita sua frase-senha",
            )
            self._confirmation_input.returnPressed.connect(self._submit)
            form_layout.addWidget(self._confirmation_input)

            warning = QLabel(
                "Não há recuperação nesta versão. Se a frase-senha for perdida, "
                "o cofre ficará inacessível."
            )
            warning.setObjectName("warning")
            warning.setWordWrap(True)
            form_layout.addWidget(warning)
            self._action_button.setText("Criar meu cofre")
        else:
            self._password_input.returnPressed.connect(self._submit)
            self._action_button.setText("Desbloquear cofre")

        form_layout.addStretch()
        self._action_button.setIcon(lucide_icon("lock", "#ffffff", 19))
        self._action_button.setIconSize(QSize(19, 19))
        self._action_button.setObjectName("primaryButton")
        self._action_button.setMinimumHeight(
            max(46, self._action_button.fontMetrics().height() + 22)
        )
        self._action_button.clicked.connect(self._submit)
        form_layout.addWidget(self._action_button)
        shell_layout.addWidget(form_panel, 1)

        centered = QHBoxLayout()
        centered.setContentsMargins(26, 10, 26, 14)
        centered.addStretch()
        centered.addWidget(shell, 1)
        centered.addStretch()
        root_layout.addLayout(centered, 1)
        self.setCentralWidget(root)

    @staticmethod
    def _field_label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    @staticmethod
    def _prepare_password_input(input_widget: QLineEdit, placeholder: str) -> None:
        input_widget.setEchoMode(QLineEdit.EchoMode.Password)
        input_widget.setPlaceholderText(placeholder)
        input_widget.setMinimumHeight(max(46, input_widget.fontMetrics().height() + 24))

    def _toggle_password_visibility(self) -> None:
        self._password_visible = not self._password_visible
        mode = QLineEdit.EchoMode.Normal if self._password_visible else QLineEdit.EchoMode.Password
        self._password_input.setEchoMode(mode)
        if self._confirmation_input is not None:
            self._confirmation_input.setEchoMode(mode)
        icon_name = "eye-off" if self._password_visible else "eye"
        self._visibility_action.setIcon(lucide_icon(icon_name, "#94a3b8", 19))

    def _submit(self) -> None:
        password = self._password_input.text()
        self._action_button.setEnabled(False)
        try:
            if self._is_first_access:
                confirmation = self._confirmation_input.text() if self._confirmation_input else ""
                if password != confirmation:
                    MessageDialog.warning(
                        self,
                        "As senhas informadas não coincidem.",
                        title="Confira a confirmação",
                    )
                    return
                session = self._vault_service.create(password)
            else:
                session = self._vault_service.unlock(password)
        except VaultUnlockError:
            MessageDialog.warning(
                self,
                "Não foi possível desbloquear o cofre.",
                title="Cofre bloqueado",
                detail="Confira sua frase-senha e tente novamente.",
            )
            return
        except (TypeError, ValueError, RuntimeError) as exc:
            MessageDialog.warning(self, str(exc))
            return
        finally:
            self._password_input.clear()
            if self._confirmation_input is not None:
                self._confirmation_input.clear()
            self._action_button.setEnabled(True)

        self.unlocked.emit(session)


def as_vault_session(value: object) -> VaultSession:
    """Ajuda de tipagem para consumidores do sinal Qt."""
    if not isinstance(value, VaultSession):
        raise TypeError("Sessão de cofre inválida.")
    return value
