"""Preferências de segurança com limites que não podem ser desativados."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from app.models.app_settings import (
    MAX_AUTO_LOCK_MINUTES,
    MAX_BACKUP_RETENTION,
    MAX_CLIPBOARD_SECONDS,
    MIN_AUTO_LOCK_MINUTES,
    MIN_BACKUP_RETENTION,
    MIN_CLIPBOARD_SECONDS,
    AppSettings,
)
from app.ui.icons import lucide_icon
from app.ui.window_chrome import install_window_chrome


class SettingsDialog(QDialog):
    def __init__(self, settings: AppSettings, parent=None) -> None:  # type: ignore[no-untyped-def]
        super().__init__(parent)
        self.setObjectName("credentialDialog")
        self.setWindowTitle("Configurações")
        self.setMinimumSize(560, 500)
        self.resize(680, 560)

        self._auto_lock = self._spin_box(
            MIN_AUTO_LOCK_MINUTES,
            MAX_AUTO_LOCK_MINUTES,
            " min",
            settings.auto_lock_minutes,
        )
        self._clipboard = self._spin_box(
            MIN_CLIPBOARD_SECONDS,
            MAX_CLIPBOARD_SECONDS,
            " s",
            settings.clipboard_seconds,
        )
        self._backup_retention = self._spin_box(
            MIN_BACKUP_RETENTION,
            MAX_BACKUP_RETENTION,
            " arquivos",
            settings.backup_retention,
        )
        self._build_ui()

    @property
    def settings(self) -> AppSettings:
        return AppSettings(
            auto_lock_minutes=self._auto_lock.value(),
            clipboard_seconds=self._clipboard.value(),
            backup_retention=self._backup_retention.value(),
        )

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 8, 18, 18)
        outer.setSpacing(18)
        install_window_chrome(self, outer, "Configurações", allow_maximize=False)

        header = QHBoxLayout()
        header.setSpacing(15)
        icon_badge = QLabel()
        icon_badge.setObjectName("dialogIconBadge")
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setFixedSize(54, 54)
        icon_badge.setPixmap(lucide_icon("settings-2", "#dbeafe", 29).pixmap(29, 29))
        header.addWidget(icon_badge)
        heading = QVBoxLayout()
        heading.setSpacing(3)
        title = QLabel("Preferências de segurança")
        title.setObjectName("dialogTitle")
        heading.addWidget(title)
        subtitle = QLabel("Ajuste os tempos sem desativar as proteções essenciais do cofre.")
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        outer.addLayout(header)

        card = QFrame()
        card.setObjectName("dialogCard")
        content = QVBoxLayout(card)
        content.setContentsMargins(24, 22, 24, 22)
        content.setSpacing(13)
        content.addWidget(
            self._setting_row(
                "Bloqueio automático",
                "Tempo máximo sem atividade antes de exigir novamente a senha mestra.",
                self._auto_lock,
            )
        )
        content.addWidget(self._divider())
        content.addWidget(
            self._setting_row(
                "Limpeza do clipboard",
                "Tempo que uma senha copiada permanece disponível para colar.",
                self._clipboard,
            )
        )
        content.addWidget(self._divider())
        content.addWidget(
            self._setting_row(
                "Retenção de backups",
                "Quantidade máxima preservada após a criação do próximo backup.",
                self._backup_retention,
            )
        )
        note = QLabel(
            "As preferências não contêm senhas ou chaves. Alterações nos temporizadores são aplicadas imediatamente."
        )
        note.setObjectName("restoreSafetyNote")
        note.setWordWrap(True)
        content.addWidget(note)
        outer.addWidget(card, 1)

        footer = QHBoxLayout()
        footer.addStretch()
        cancel = QPushButton("Cancelar")
        cancel.setObjectName("secondaryButton")
        cancel.setIcon(lucide_icon("x", "#e5e7eb", 18))
        cancel.setIconSize(QSize(18, 18))
        self._fit_button(cancel)
        cancel.clicked.connect(self.reject)
        footer.addWidget(cancel)
        save = QPushButton("Salvar configurações")
        save.setObjectName("primaryButton")
        save.setIcon(lucide_icon("check", "#ffffff", 18))
        save.setIconSize(QSize(18, 18))
        self._fit_button(save)
        save.setDefault(True)
        save.clicked.connect(self.accept)
        footer.addWidget(save)
        outer.addLayout(footer)

    @staticmethod
    def _spin_box(minimum: int, maximum: int, suffix: str, value: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setRange(minimum, maximum)
        spin.setSuffix(suffix)
        spin.setValue(value)
        spin.setAlignment(Qt.AlignmentFlag.AlignCenter)
        spin.setMinimumWidth(125)
        spin.setMinimumHeight(42)
        return spin

    @staticmethod
    def _setting_row(title: str, description: str, control: QWidget) -> QWidget:
        row = QWidget()
        layout = QHBoxLayout(row)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(18)
        text = QVBoxLayout()
        text.setSpacing(4)
        heading = QLabel(title)
        heading.setObjectName("fieldLabel")
        text.addWidget(heading)
        detail = QLabel(description)
        detail.setObjectName("muted")
        detail.setWordWrap(True)
        text.addWidget(detail)
        layout.addLayout(text, 1)
        control.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        layout.addWidget(control)
        return row

    @staticmethod
    def _divider() -> QFrame:
        divider = QFrame()
        divider.setObjectName("messageDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        return divider

    @staticmethod
    def _fit_button(button: QPushButton) -> None:
        text_width = button.fontMetrics().horizontalAdvance(button.text())
        button.setMinimumWidth(text_width + button.iconSize().width() + 38)
        button.setMinimumHeight(max(40, button.fontMetrics().height() + 20))
