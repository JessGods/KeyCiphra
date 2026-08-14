"""Alertas e confirmações consistentes com a identidade do KeyCiphra."""

from __future__ import annotations

from enum import Enum

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QDialog,
    QFrame,
    QGraphicsDropShadowEffect,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from app.ui.icons import lucide_icon


class MessageKind(Enum):
    WARNING = "warning"
    ERROR = "error"
    CONFIRMATION = "confirmation"


_KIND_APPEARANCE = {
    MessageKind.WARNING: ("alert-triangle", "#fbbf24", "Atenção"),
    MessageKind.ERROR: ("x-circle", "#f87171", "Não foi possível concluir"),
    MessageKind.CONFIRMATION: ("trash", "#f87171", "Confirmar ação"),
}


class MessageDialog(QDialog):
    """Modal responsivo para avisos, erros e decisões destrutivas."""

    def __init__(
        self,
        message: str,
        *,
        kind: MessageKind = MessageKind.WARNING,
        title: str | None = None,
        detail: str | None = None,
        confirm_text: str = "Entendi",
        cancel_text: str | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent)
        self.setObjectName("messageDialog")
        self.setWindowTitle("KeyCiphra")
        self.setModal(True)
        self.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setMinimumWidth(390)
        self.setMaximumWidth(560)

        icon_name, accent_color, default_title = _KIND_APPEARANCE[kind]

        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 18)
        outer.setSpacing(0)

        panel = QFrame()
        panel.setObjectName("messagePanel")
        panel.setProperty("kind", kind.value)
        shadow = QGraphicsDropShadowEffect(panel)
        shadow.setBlurRadius(34)
        shadow.setOffset(0, 10)
        shadow.setColor(Qt.GlobalColor.black)
        panel.setGraphicsEffect(shadow)

        layout = QVBoxLayout(panel)
        layout.setContentsMargins(26, 22, 26, 22)
        layout.setSpacing(18)

        top_row = QHBoxLayout()
        top_row.setSpacing(16)
        icon_badge = QLabel()
        icon_badge.setObjectName("messageIconBadge")
        icon_badge.setProperty("kind", kind.value)
        icon_badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        icon_badge.setFixedSize(52, 52)
        icon_badge.setPixmap(lucide_icon(icon_name, accent_color, 28).pixmap(28, 28))
        top_row.addWidget(icon_badge, 0, Qt.AlignmentFlag.AlignTop)

        text_column = QVBoxLayout()
        text_column.setSpacing(7)
        heading = QLabel(title or default_title)
        heading.setObjectName("messageTitle")
        heading.setWordWrap(True)
        text_column.addWidget(heading)
        body = QLabel(message)
        body.setObjectName("messageBody")
        body.setWordWrap(True)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        body.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Preferred)
        text_column.addWidget(body)
        if detail:
            detail_label = QLabel(detail)
            detail_label.setObjectName("messageDetail")
            detail_label.setWordWrap(True)
            detail_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            text_column.addWidget(detail_label)
        top_row.addLayout(text_column, 1)
        layout.addLayout(top_row)

        divider = QFrame()
        divider.setObjectName("messageDivider")
        divider.setFrameShape(QFrame.Shape.HLine)
        layout.addWidget(divider)

        actions = QHBoxLayout()
        actions.addStretch()
        if cancel_text is not None:
            cancel_button = QPushButton(cancel_text)
            cancel_button.setObjectName("secondaryButton")
            cancel_button.setIcon(lucide_icon("x", "#e5e7eb", 17))
            cancel_button.setIconSize(QSize(17, 17))
            self._fit_button(cancel_button)
            cancel_button.clicked.connect(self.reject)
            actions.addWidget(cancel_button)

        confirm_button = QPushButton(confirm_text)
        confirm_button.setObjectName(
            "destructiveButton" if kind is MessageKind.CONFIRMATION else "primaryButton"
        )
        confirm_button.setIcon(
            lucide_icon(
                "trash" if kind is MessageKind.CONFIRMATION else "check",
                "#ffffff",
                17,
            )
        )
        confirm_button.setIconSize(QSize(17, 17))
        self._fit_button(confirm_button)
        confirm_button.setDefault(True)
        confirm_button.clicked.connect(self.accept)
        actions.addWidget(confirm_button)
        layout.addLayout(actions)

        outer.addWidget(panel)
        self.adjustSize()

    @staticmethod
    def warning(
        parent: QWidget | None,
        message: str,
        *,
        title: str | None = None,
        detail: str | None = None,
    ) -> None:
        MessageDialog(
            message,
            kind=MessageKind.WARNING,
            title=title,
            detail=detail,
            parent=parent,
        ).exec()

    @staticmethod
    def error(
        parent: QWidget | None,
        message: str,
        *,
        title: str | None = None,
        detail: str | None = None,
    ) -> None:
        MessageDialog(
            message,
            kind=MessageKind.ERROR,
            title=title,
            detail=detail,
            parent=parent,
        ).exec()

    @staticmethod
    def confirm(
        parent: QWidget | None,
        message: str,
        *,
        title: str | None = None,
        confirm_text: str = "Confirmar",
        cancel_text: str = "Cancelar",
    ) -> bool:
        dialog = MessageDialog(
            message,
            kind=MessageKind.CONFIRMATION,
            title=title,
            confirm_text=confirm_text,
            cancel_text=cancel_text,
            parent=parent,
        )
        return dialog.exec() == QDialog.DialogCode.Accepted

    @staticmethod
    def _fit_button(button: QPushButton) -> None:
        width = button.fontMetrics().horizontalAdvance(button.text())
        button.setMinimumWidth(width + button.iconSize().width() + 36)
        button.setMinimumHeight(max(40, button.fontMetrics().height() + 20))

    def mousePressEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_origin = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            event.accept()
            return
        super().mousePressEvent(event)

    def mouseMoveEvent(self, event) -> None:  # type: ignore[no-untyped-def]
        if event.buttons() & Qt.MouseButton.LeftButton and hasattr(self, "_drag_origin"):
            self.move(event.globalPosition().toPoint() - self._drag_origin)
            event.accept()
            return
        super().mouseMoveEvent(event)

    def closeEvent(self, event: QCloseEvent) -> None:
        self.reject()
        event.accept()
