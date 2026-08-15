"""Moldura sem decoração nativa para as janelas do KeyCiphra."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPoint, QSize, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizePolicy,
    QWidget,
)

from app.ui.icons import lucide_icon

Window = QMainWindow | QDialog


class WindowChrome(QWidget):
    """Barra de título própria com controles e movimentação nativa."""

    def __init__(self, target: Window, title: str, *, allow_maximize: bool) -> None:
        super().__init__(target)
        self.setObjectName("windowChrome")
        self._target = target
        self._allow_maximize = allow_maximize
        target.installEventFilter(self)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(4, 0, 2, 0)
        layout.setSpacing(4)

        logo = QLabel()
        logo.setPixmap(lucide_icon("shield-check", "#60a5fa", 17).pixmap(17, 17))
        layout.addWidget(logo)
        title_label = QLabel(title)
        title_label.setObjectName("windowChromeTitle")
        layout.addWidget(title_label)
        layout.addStretch()

        minimize = self._control("minimize", "Minimizar")
        minimize.clicked.connect(target.showMinimized)
        layout.addWidget(minimize)

        self._maximize_button: QPushButton | None = None
        if allow_maximize:
            self._maximize_button = self._control("maximize", "Maximizar")
            self._maximize_button.clicked.connect(self._toggle_maximize)
            layout.addWidget(self._maximize_button)

        close = self._control("x", "Fechar", close=True)
        close.clicked.connect(target.close)
        layout.addWidget(close)

        height = max(32, self.fontMetrics().height() + 16)
        self.setFixedHeight(height)

    def _control(self, icon: str, accessible_name: str, *, close: bool = False) -> QPushButton:
        button = QPushButton()
        button.setObjectName("windowCloseButton" if close else "windowControlButton")
        button.setAccessibleName(accessible_name)
        button.setToolTip(accessible_name)
        button.setIcon(lucide_icon(icon, "#cbd5e1", 15))
        button.setIconSize(QSize(15, 15))
        size = max(28, self.fontMetrics().height() + 12)
        button.setFixedSize(size, size)
        return button

    def _toggle_maximize(self) -> None:
        if self._target.isMaximized():
            self._target.showNormal()
        else:
            self._target.showMaximized()
        self._update_maximize_icon()

    def _update_maximize_icon(self) -> None:
        if self._maximize_button is None:
            return
        maximized = self._target.isMaximized()
        self._maximize_button.setIcon(
            lucide_icon("restore" if maximized else "maximize", "#cbd5e1", 15)
        )
        self._maximize_button.setAccessibleName("Restaurar" if maximized else "Maximizar")
        self._maximize_button.setToolTip("Restaurar" if maximized else "Maximizar")

    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self._target.windowHandle()
            if handle is not None:
                handle.startSystemMove()
                event.accept()
                return
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event: QMouseEvent) -> None:
        if self._allow_maximize and event.button() == Qt.MouseButton.LeftButton:
            self._toggle_maximize()
            event.accept()
            return
        super().mouseDoubleClickEvent(event)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        if watched is getattr(self, "_target", None) and event.type() == QEvent.Type.WindowStateChange:
            self._update_maximize_icon()
        return super().eventFilter(watched, event)


class BorderResizeController(QObject):
    """Inicia redimensionamento nativo ao arrastar a borda sem moldura."""

    MARGIN = 6

    def __init__(self, target: Window) -> None:
        super().__init__(target)
        self._target = target
        target.setMouseTracking(True)
        target.installEventFilter(self)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:
        target = getattr(self, "_target", None)
        if target is not None and watched is target and isinstance(event, QMouseEvent):
            edges = self._edges_at(event.position().toPoint())
            if event.type() == QEvent.Type.MouseMove and not event.buttons():
                target.setCursor(self._cursor_for(edges))
            elif event.type() == QEvent.Type.MouseButtonPress and edges:
                handle = target.windowHandle()
                if handle is not None and handle.startSystemResize(edges):
                    return True
        return super().eventFilter(watched, event)

    def _edges_at(self, point: QPoint) -> Qt.Edges:
        if self._target.isMaximized():
            return Qt.Edge(0)
        rect = self._target.rect()
        edges = Qt.Edge(0)
        if point.x() <= self.MARGIN:
            edges |= Qt.Edge.LeftEdge
        elif point.x() >= rect.width() - self.MARGIN:
            edges |= Qt.Edge.RightEdge
        if point.y() <= self.MARGIN:
            edges |= Qt.Edge.TopEdge
        elif point.y() >= rect.height() - self.MARGIN:
            edges |= Qt.Edge.BottomEdge
        return edges

    @staticmethod
    def _cursor_for(edges: Qt.Edges) -> Qt.CursorShape:
        if edges in (
            Qt.Edge.LeftEdge | Qt.Edge.TopEdge,
            Qt.Edge.RightEdge | Qt.Edge.BottomEdge,
        ):
            return Qt.CursorShape.SizeFDiagCursor
        if edges in (
            Qt.Edge.RightEdge | Qt.Edge.TopEdge,
            Qt.Edge.LeftEdge | Qt.Edge.BottomEdge,
        ):
            return Qt.CursorShape.SizeBDiagCursor
        if edges & (Qt.Edge.LeftEdge | Qt.Edge.RightEdge):
            return Qt.CursorShape.SizeHorCursor
        if edges & (Qt.Edge.TopEdge | Qt.Edge.BottomEdge):
            return Qt.CursorShape.SizeVerCursor
        return Qt.CursorShape.ArrowCursor


def install_window_chrome(
    target: Window,
    layout,  # type: ignore[no-untyped-def]
    title: str,
    *,
    allow_maximize: bool,
) -> WindowChrome:
    """Remove a moldura do sistema e insere a barra visual do produto."""
    target.setWindowFlag(Qt.WindowType.FramelessWindowHint, True)
    chrome = WindowChrome(target, title, allow_maximize=allow_maximize)
    layout.insertWidget(0, chrome)
    target._resize_controller = BorderResizeController(target)  # type: ignore[attr-defined]
    return chrome
