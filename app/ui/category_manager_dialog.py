"""Gerenciamento temático das categorias criptografadas."""

from __future__ import annotations

from collections.abc import Callable

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QComboBox,
    QDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
)

from app.models.category import Category
from app.services.category_service import CategoryService, CategoryValidationError
from app.services.demo_data_service import DemoDataResult
from app.ui.icons import lucide_icon
from app.ui.message_dialog import MessageDialog
from app.ui.window_chrome import install_window_chrome
from app.utils.logging_config import get_logger


class CategoryManagerDialog(QDialog):
    """Cria, renomeia e remove categorias sem expor nomes fora do cofre."""

    def __init__(
        self,
        service: CategoryService,
        parent=None,  # type: ignore[no-untyped-def]
        *,
        populate_demo: Callable[[], DemoDataResult] | None = None,
    ) -> None:
        super().__init__(parent)
        self._service = service
        self._populate_demo_callback = populate_demo
        self._categories: list[Category] = []
        self._changed = False
        self.setObjectName("credentialDialog")
        self.setWindowTitle("Gerenciar categorias")
        self.setMinimumSize(540, 520)
        self.resize(700, 640)

        self._list = QListWidget()
        self._list.setObjectName("categoryList")
        self._list.setAlternatingRowColors(True)
        self._list.currentItemChanged.connect(self._selection_changed)
        self._count = QLabel()
        self._count.setObjectName("muted")
        self._new_name = QLineEdit()
        self._new_name.setPlaceholderText("Ex.: Trabalho, Financeiro, Pessoal")
        self._new_name.setMaxLength(CategoryService.MAX_NAME_LENGTH)
        self._new_name.returnPressed.connect(self._create)
        self._rename_name = QLineEdit()
        self._rename_name.setPlaceholderText("Selecione uma categoria")
        self._rename_name.setMaxLength(CategoryService.MAX_NAME_LENGTH)
        self._replacement = QComboBox()
        self._replacement.setMinimumHeight(42)
        self._rename_button = QPushButton("Renomear")
        self._delete_button = QPushButton("Excluir categoria")

        self._build_ui()
        self._reload()

    @property
    def changed(self) -> bool:
        return self._changed

    @property
    def category_names(self) -> list[str]:
        return [category.name for category in self._categories]

    def _build_ui(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 8, 18, 18)
        outer.setSpacing(18)
        install_window_chrome(self, outer, "Gerenciar categorias", allow_maximize=False)

        header = QHBoxLayout()
        header.setSpacing(15)
        badge = QLabel()
        badge.setObjectName("dialogIconBadge")
        badge.setAlignment(Qt.AlignmentFlag.AlignCenter)
        badge.setFixedSize(54, 54)
        badge.setPixmap(lucide_icon("tags", "#dbeafe", 28).pixmap(28, 28))
        header.addWidget(badge)
        heading = QVBoxLayout()
        heading.setSpacing(3)
        title = QLabel("Organize seu cofre")
        title.setObjectName("dialogTitle")
        heading.addWidget(title)
        subtitle = QLabel(
            "Crie categorias e altere todas as credenciais relacionadas de uma só vez."
        )
        subtitle.setObjectName("dialogSubtitle")
        subtitle.setWordWrap(True)
        heading.addWidget(subtitle)
        header.addLayout(heading, 1)
        outer.addLayout(header)

        create_card = QFrame()
        create_card.setObjectName("dialogCard")
        create_layout = QVBoxLayout(create_card)
        create_layout.setContentsMargins(20, 18, 20, 18)
        create_layout.setSpacing(9)
        create_layout.addWidget(self._label("Nova categoria"))
        create_row = QHBoxLayout()
        create_row.setSpacing(10)
        create_row.addWidget(self._new_name, 1)
        create_button = QPushButton("Criar")
        create_button.setObjectName("primaryButton")
        create_button.setIcon(lucide_icon("folder-plus", "#ffffff", 18))
        create_button.setIconSize(QSize(18, 18))
        self._fit_button(create_button)
        create_button.clicked.connect(self._create)
        create_row.addWidget(create_button)
        create_layout.addLayout(create_row)
        outer.addWidget(create_card)

        content = QFrame()
        content.setObjectName("dialogCard")
        content_layout = QHBoxLayout(content)
        content_layout.setContentsMargins(20, 18, 20, 18)
        content_layout.setSpacing(18)

        list_column = QVBoxLayout()
        list_heading = QHBoxLayout()
        list_heading.addWidget(self._label("Categorias do cofre"))
        list_heading.addStretch()
        list_heading.addWidget(self._count)
        list_column.addLayout(list_heading)
        list_column.addWidget(self._list, 1)
        content_layout.addLayout(list_column, 1)

        editor = QVBoxLayout()
        editor.setSpacing(10)
        editor.addWidget(self._label("Nome selecionado"))
        editor.addWidget(self._rename_name)
        self._rename_button.setIcon(lucide_icon("pencil", "#e5e7eb", 17))
        self._rename_button.setIconSize(QSize(17, 17))
        self._fit_button(self._rename_button)
        self._rename_button.clicked.connect(self._rename)
        editor.addWidget(self._rename_button)
        editor.addSpacing(10)
        editor.addWidget(self._label("Ao excluir, mover acessos para"))
        editor.addWidget(self._replacement)
        helper = QLabel("Escolha “Sem categoria” ou outra pasta antes de excluir.")
        helper.setObjectName("muted")
        helper.setWordWrap(True)
        editor.addWidget(helper)
        self._delete_button.setObjectName("dangerButton")
        self._delete_button.setIcon(lucide_icon("trash", "#fecaca", 17))
        self._delete_button.setIconSize(QSize(17, 17))
        self._fit_button(self._delete_button)
        self._delete_button.clicked.connect(self._delete)
        editor.addWidget(self._delete_button)
        editor.addStretch()
        content_layout.addLayout(editor, 1)
        outer.addWidget(content, 1)

        self._safety = QLabel(
            "Os nomes das categorias são criptografados junto com o restante do cofre."
        )
        self._safety.setObjectName("restoreSafetyNote")
        self._safety.setWordWrap(True)
        outer.addWidget(self._safety)

        footer = QHBoxLayout()
        demo_button = QPushButton("Adicionar exemplos")
        demo_button.setObjectName("secondaryButton")
        demo_button.setIcon(lucide_icon("sparkles", "#dbeafe", 18))
        demo_button.setIconSize(QSize(18, 18))
        demo_button.setToolTip("Criar categorias e credenciais inteiramente fictícias")
        demo_button.setEnabled(self._populate_demo_callback is not None)
        self._fit_button(demo_button)
        demo_button.clicked.connect(self._populate_demo)
        footer.addWidget(demo_button)
        footer.addStretch()
        done = QPushButton("Concluir")
        done.setObjectName("primaryButton")
        done.setIcon(lucide_icon("check", "#ffffff", 18))
        done.setIconSize(QSize(18, 18))
        self._fit_button(done)
        done.clicked.connect(self.accept)
        footer.addWidget(done)
        outer.addLayout(footer)

    def _reload(self, selected_id: str | None = None) -> None:
        self._categories = self._service.list_all()
        self._list.blockSignals(True)
        self._list.clear()
        selected_row = -1
        for row, category in enumerate(self._categories):
            item = QListWidgetItem(lucide_icon("tag", "#93c5fd", 17), category.name)
            item.setData(Qt.ItemDataRole.UserRole, category.id)
            self._list.addItem(item)
            if category.id == selected_id:
                selected_row = row
        self._list.blockSignals(False)
        self._count.setText(str(len(self._categories)))
        if self._categories:
            self._list.setCurrentRow(selected_row if selected_row >= 0 else 0)
        else:
            self._selection_changed(None, None)

    def _selection_changed(
        self,
        current: QListWidgetItem | None,
        previous: QListWidgetItem | None,
    ) -> None:
        del previous
        selected_id = current.data(Qt.ItemDataRole.UserRole) if current else None
        category = next((item for item in self._categories if item.id == selected_id), None)
        self._rename_name.setText(category.name if category else "")
        self._rename_name.setEnabled(category is not None)
        self._rename_button.setEnabled(category is not None)
        self._delete_button.setEnabled(category is not None)
        self._replacement.clear()
        self._replacement.addItem("Sem categoria", "")
        for item in self._categories:
            if category is None or item.id != category.id:
                self._replacement.addItem(item.name, item.name)
        self._replacement.setEnabled(category is not None)

    def _create(self) -> None:
        try:
            created = self._service.create(self._new_name.text())
        except CategoryValidationError as exc:
            MessageDialog.warning(self, str(exc), title="Categoria não criada")
            return
        except Exception as exc:
            get_logger().error("category.create_failed type=%s", type(exc).__name__)
            MessageDialog.error(self, "Não foi possível criar a categoria.")
            return
        self._changed = True
        self._new_name.clear()
        self._reload(created.id)
        get_logger().info("category.created")

    def _populate_demo(self) -> None:
        if self._populate_demo_callback is None:
            return
        if not MessageDialog.confirm(
            self,
            "Adicionar 20 credenciais fictícias distribuídas em 10 categorias?\n\n"
            "Todos os endereços usam o domínio reservado example.invalid e não acessam contas reais.",
            title="Adicionar dados de demonstração",
            confirm_text="Adicionar exemplos",
        ):
            return
        try:
            result = self._populate_demo_callback()
        except Exception as exc:
            get_logger().error("demo_data.populate_failed type=%s", type(exc).__name__)
            MessageDialog.error(
                self,
                "Não foi possível adicionar os dados de demonstração.",
            )
            return
        if result.created_categories or result.created_credentials:
            self._changed = True
            self._safety.setText(
                f"Exemplos adicionados: {result.created_credentials} credenciais e "
                f"{result.created_categories} categorias. Tudo foi criptografado normalmente."
            )
            get_logger().info(
                "demo_data.populated categories=%d credentials=%d",
                result.created_categories,
                result.created_credentials,
            )
        else:
            self._safety.setText(
                "Os dados de demonstração já estão neste cofre; nenhuma duplicata foi criada."
            )
        self._reload()

    def _rename(self) -> None:
        category_id = self._selected_id()
        if category_id is None:
            return
        try:
            updated = self._service.rename(category_id, self._rename_name.text())
        except CategoryValidationError as exc:
            MessageDialog.warning(self, str(exc), title="Categoria não renomeada")
            return
        except Exception as exc:
            get_logger().error("category.rename_failed type=%s", type(exc).__name__)
            MessageDialog.error(self, "Não foi possível renomear a categoria.")
            return
        self._changed = True
        self._reload(updated.id)
        get_logger().info("category.renamed")

    def _delete(self) -> None:
        category_id = self._selected_id()
        if category_id is None:
            return
        category = next(item for item in self._categories if item.id == category_id)
        usage = self._service.usage_count(category.name)
        destination = str(self._replacement.currentData() or "")
        destination_label = destination or "Sem categoria"
        detail = (
            f"{usage} credencial(is) será(ão) movida(s) para “{destination_label}”."
            if usage
            else "Nenhuma credencial utiliza esta categoria."
        )
        if not MessageDialog.confirm(
            self,
            f'Excluir a categoria “{category.name}”?\n\n{detail}',
            title="Excluir categoria",
            confirm_text="Excluir categoria",
        ):
            return
        try:
            self._service.delete(category_id, destination)
        except CategoryValidationError as exc:
            MessageDialog.warning(self, str(exc), title="Categoria não excluída")
            return
        except Exception as exc:
            get_logger().error("category.delete_failed type=%s", type(exc).__name__)
            MessageDialog.error(self, "Não foi possível excluir a categoria.")
            return
        self._changed = True
        self._reload()
        get_logger().info("category.deleted")

    def _selected_id(self) -> str | None:
        current = self._list.currentItem()
        if current is None:
            return None
        value = current.data(Qt.ItemDataRole.UserRole)
        return str(value) if value else None

    @staticmethod
    def _label(text: str) -> QLabel:
        label = QLabel(text)
        label.setObjectName("fieldLabel")
        return label

    @staticmethod
    def _fit_button(button: QPushButton) -> None:
        icon_width = button.iconSize().width() + 8 if not button.icon().isNull() else 0
        button.setMinimumWidth(button.fontMetrics().horizontalAdvance(button.text()) + icon_width + 28)
        button.setMinimumHeight(max(40, button.fontMetrics().height() + 20))
        button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
