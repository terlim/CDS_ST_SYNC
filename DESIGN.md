# Code Design — CDS_ST_SYNC

> OOP + SOLID | Версия 1.0

---

## 1. SOLID-принципы в проекте

| Принцип | Применение |
|---------|-----------|
| **S** — Single Responsibility | Каждый класс = одна зона ответственности. Экспорт не знает про хранение, GUI не знает про pipe |
| **O** — Open/Closed | Интерфейсы (`ABC`) позволяют добавлять новые типы хранилищ, транспортов, форматов без изменения ядра |
| **L** — Liskov | Реализации интерфейсов взаимозаменяемы: `FileStorage` / `MemoryStorage` / `ZipStorage` |
| **I** — Interface Segregation | Маленькие интерфейсы: `IObjectReader`, `IObjectWriter`, `ITreeBuilder`, `ITransport` |
| **D** — Dependency Inversion | Высокоуровневые модули (`ExportService`) зависят от абстракций (`IObjectReader`), а не от деталей (`CodeSysProject`) |

---

## 2. Архитектура слоёв

```
┌─────────────────────────────────────────────────────────┐
│  Presentation (GUI)                                     │
│  main_window, tree_panel, editor_panel, settings_dialog  │
│  зависит → IApplicationService                          │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Application Services                                   │
│  ExportService, ImportService, LiveSyncService,         │
│  DaemonService                                          │
│  зависит → ICodeSysBridge, IStorage, ITransport          │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Domain Model                                           │
│  ObjectMeta, Manifest, StFile, ProjectTree,             │
│  OperationResult, ProgressEvent                         │
└──────────────────────┬──────────────────────────────────┘
                       │
┌──────────────────────▼──────────────────────────────────┐
│  Infrastructure                                         │
│  CodeSysBridge, FileSystemStorage, PipeTransport,       │
│  TextExtractor, StFormatter                             │
│  зависит → CodeSys API (IronPython) / Win32 API / OS FS │
└─────────────────────────────────────────────────────────┘
```

---

## 3. Интерфейсы (ABC)

```python
# ─── CodeSys Bridge ──────────────────────────────────────
class IObjectReader(ABC):
    """Чтение объектов из CodeSys IDE."""
    def get_all_objects(self) -> list[ICodeSysObject]: ...
    def get_object_by_guid(self, guid: str) -> ICodeSysObject | None: ...
    def get_project_tree(self) -> ProjectTree: ...

class IObjectWriter(ABC):
    """Запись объектов в CodeSys IDE."""
    def update_text(self, guid: str, declaration: str, implementation: str | None) -> OperationResult: ...
    def create_pou(self, name: str, kind: str, container_guid: str, declaration: str) -> ICodeSysObject: ...
    def create_gvl(self, name: str, container_guid: str) -> ICodeSysObject: ...
    def create_dut(self, name: str, container_guid: str, dut_kind: str) -> ICodeSysObject: ...
    def create_folder(self, name: str, parent_guid: str) -> ICodeSysObject: ...

class ITimestampReader(ABC):
    """Чтение меток времени для live sync."""
    def get_timestamps(self) -> dict[str, int]: ...  # guid → timestamp_ms

class ICodeSysBridge(IObjectReader, IObjectWriter, ITimestampReader):
    """Полный интерфейс моста к CodeSys."""
    pass

# ─── Storage ─────────────────────────────────────────────
class IStorage(ABC):
    """Хранение .st файлов и manifest.json."""
    def save_object(self, meta: ObjectMeta, declaration: str, implementation: str | None) -> None: ...
    def load_object(self, meta: ObjectMeta) -> tuple[str, str | None]: ...  # (decl, impl)
    def save_manifest(self, manifest: Manifest) -> None: ...
    def load_manifest(self) -> Manifest: ...
    def watch_changes(self, callback: Callable) -> None: ...  # для live sync

# ─── Transport ───────────────────────────────────────────
class ITransport(ABC):
    """Транспорт для общения с демоном."""
    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def send(self, message: dict) -> dict: ...
    def is_connected(self) -> bool: ...
    @property
    def on_progress(self) -> Signal: ...

# ─── Extractor / Formatter ───────────────────────────────
class ITextExtractor(ABC):
    """Извлечение ST-текста из объекта CodeSys."""
    def extract_declaration(self, obj: ICodeSysObject) -> str: ...
    def extract_implementation(self, obj: ICodeSysObject) -> str | None: ...

class ITextFormatter(ABC):
    """Форматирование ST-текста для записи в файл."""
    def format_st(self, declaration: str, implementation: str | None) -> str: ...
    def parse_st(self, content: str) -> tuple[str, str | None]: ...

# ─── Application Services ────────────────────────────────
class IExportService(ABC):
    def export(self, filter: ObjectFilter) -> OperationResult: ...

class IImportService(ABC):
    def import_(self, filter: ObjectFilter) -> OperationResult: ...

class ILiveSyncService(ABC):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def is_running(self) -> bool: ...
    @property
    def on_sync_event(self) -> Signal: ...
```

---

## 4. Доменные модели

```python
@dataclass
class ObjectMeta:
    """Метаданные одного объекта CodeSys."""
    guid: str
    name: str
    type: str              # pou, gvl, dut, interface, persistent, task_local
    pou_kind: str | None   # program, function_block, function
    path: list[str]        # ["Device", "Plc Logic", ..., "PROGRAMS"]
    relative_path: str     # "Device/Plc Logic/.../PROGRAMS/PLC_PRG.st"
    sha1: str | None
    ide_timestamp_ms: int | None
    file_mtime: float | None

@dataclass
class Manifest:
    """Инвентарь всех объектов синхронизации."""
    version: int
    project_name: str
    exported_at: str
    objects: list[ObjectMeta]

    def get_by_guid(self, guid: str) -> ObjectMeta | None: ...
    def get_by_path(self, path: list[str]) -> ObjectMeta | None: ...
    def diff(self, other: "Manifest") -> ManifestDiff: ...

@dataclass
class ManifestDiff:
    added: list[ObjectMeta]
    removed: list[ObjectMeta]
    changed: list[ObjectMeta]
    unchanged: list[ObjectMeta]

@dataclass
class OperationResult:
    success: bool
    total: int
    completed: int
    errors: list[dict]     # [{guid, object, error}, ...]
    messages: list[str]

class ProjectTree:
    """Дерево объектов CodeSys для отображения в GUI."""
    def __init__(self): ...
    def add_node(self, guid: str, name: str, obj_type: str, parent_guid: str | None) -> None: ...
    def to_nested_list(self) -> list[dict]: ...

@dataclass
class ObjectFilter:
    """Фильтр объектов по типам."""
    include_pou: bool = True
    include_gvl: bool = True
    include_dut: bool = True
    include_interface: bool = True
    include_persistent: bool = False
    include_task_local: bool = False
    specific_guids: list[str] | None = None  # None = все

    def matches(self, meta: ObjectMeta) -> bool: ...

@dataclass
class SyncSettings:
    """Настройки синхронизации (из .cds-st-sync.json / QSettings)."""
    sync_dir: str
    filter: ObjectFilter
    pipe_name: str = "cds-st-sync-default"
    pipe_timeout: int = 30
    live_sync_enabled: bool = False
    poll_interval: int = 2
    conflict_strategy: str = "last_write_wins"
```

---

## 5. Конкретные классы (реализации)

### 5.1. Инфраструктура (IronPython 2.7)

```python
class CodeSysObjectProxy(ICodeSysObject):
    """Тонкая обёртка над объектом CodeSys для отвязки от IronPython API."""
    def __init__(self, native_object): ...
    def _get_attr(self, name: str, default=None): ...   # Безопасный hasattr/getattr/None
    # Свойства
    guid: str
    name: str
    parent: CodeSysObjectProxy | None
    type_guid: str
    declaration_text: str | None        # textual_declaration.text
    implementation_text: str | None     # textual_implementation.text
    children: list[CodeSysObjectProxy]

class CodeSysBridge(ICodeSysBridge):
    """
    ЕДИНСТВЕННЫЙ класс, который напрямую работает с CodeSys API.
    Всё остальное зависит от ICodeSysBridge → можно тестировать на моках.
    
    Реализует IObjectReader + IObjectWriter + ITimestampReader.
    """
    def __init__(self, project): ...
    # --- IObjectReader ---
    def get_all_objects(self) -> list[CodeSysObjectProxy]: ...
    def get_object_by_guid(self, guid: str) -> CodeSysObjectProxy | None: ...
    def get_project_tree(self) -> ProjectTree: ...
    # --- IObjectWriter ---  
    def update_text(self, guid, declaration, implementation) -> OperationResult: ...
    def create_pou(self, name, kind, container_guid, declaration) -> CodeSysObjectProxy: ...
    def create_gvl(self, name, container_guid) -> CodeSysObjectProxy: ...
    def create_dut(self, name, container_guid, dut_kind) -> CodeSysObjectProxy: ...
    def create_folder(self, name, parent_guid) -> CodeSysObjectProxy: ...
    # --- ITimestampReader ---
    def get_timestamps(self) -> dict[str, int]: ...

class TextExtractor(ITextExtractor):
    """Извлекает ST-текст из CodeSysObjectProxy."""
    def extract_declaration(self, obj: CodeSysObjectProxy) -> str: ...
    def extract_implementation(self, obj: CodeSysObjectProxy) -> str | None: ...

class StFormatter(ITextFormatter):
    """Форматирует/парсит .st файлы."""
    MARKER = "// --- implementation ---"
    def format_st(self, declaration: str, implementation: str | None) -> str: ...
    def parse_st(self, content: str) -> tuple[str, str | None]: ...

class FileSystemStorage(IStorage):
    """Хранилище на файловой системе."""
    def __init__(self, sync_dir: str): ...
    def save_object(self, meta, declaration, implementation) -> None: ...
    def load_object(self, meta) -> tuple[str, str | None]: ...
    def save_manifest(self, manifest) -> None: ...
    def load_manifest(self) -> Manifest: ...
    def watch_changes(self, callback) -> None: ...
    # --- Private ---
    def _object_path(self, meta: ObjectMeta) -> str: ...
    def _manifest_path(self) -> str: ...
```

### 5.2. Инфраструктура (Python 3 + Windows)

```python
class PipeTransport(ITransport):
    """
    Named Pipe транспорт для Python 3 GUI.
    Общается с DaemonDispatcher внутри CodeSys.
    """
    def __init__(self, pipe_name: str, timeout: int): ...
    def connect(self) -> bool: ...
    def disconnect(self) -> None: ...
    def send(self, message: dict) -> dict: ...
    def is_connected(self) -> bool: ...

class PipeServerTransport(ITransport):
    """Named Pipe сервер (внутри CodeSys). Реализация — в daemon_loop."""
    pass  # IronPython: системный код daemon_loop.py
```

### 5.3. Сервисы приложения (общие для IronPython и Python 3)

```python
class ExportService(IExportService):
    """
    Оркестрирует экспорт: CodeSys → .st файлы.
    Зависит от ICodeSysBridge + ITextExtractor + IStorage + ITextFormatter.
    
    Не знает ничего про CodeSys API напрямую.
    """
    def __init__(self, bridge: ICodeSysBridge, extractor: ITextExtractor,
                 storage: IStorage, formatter: ITextFormatter): ...
    def export(self, filter: ObjectFilter) -> OperationResult: ...

class ImportService(IImportService):
    """
    Оркестрирует импорт: .st файлы → CodeSys.
    Зависит от ICodeSysBridge + ITextFormatter + IStorage.
    """
    def __init__(self, bridge: ICodeSysBridge, formatter: ITextFormatter,
                 storage: IStorage): ...
    def import_(self, filter: ObjectFilter) -> OperationResult: ...

class LiveSyncService(ILiveSyncService):
    """
    Автосинхронизация.
    Зависит от ICodeSysBridge + IStorage + IExportService + IImportService.
    """
    def __init__(self, bridge: ICodeSysBridge, storage: IStorage,
                 export_svc: IExportService, import_svc: IImportService,
                 conflict_resolver: IConflictResolver): ...
    def start(self) -> None: ...
    def stop(self) -> None: ...

class ConflictResolver(IConflictResolver):
    """Last-write-wins стратегия."""
    def resolve(self, meta: ObjectMeta, ide_ts: int, file_ts: float) -> SyncAction: ...

class SyncAction(Enum):
    EXPORT_TO_FILE = "export_to_file"
    IMPORT_TO_IDE = "import_to_ide"
    SKIP = "skip"
```

### 5.4. Демон (IronPython)

```python
class DaemonDispatcher:
    """
    Диспетчер команд демона.
    Принимает JSON-команды через PipeServerTransport,
    вызывает сервисы приложения.
    
    НЕ зависит от GUI. НЕ зависит от конкретных обработчиков.
    """
    def __init__(self, bridge: ICodeSysBridge, export_svc: IExportService,
                 import_svc: IImportService): ...
    def dispatch(self, method: str, params: dict) -> dict: ...
    def _handle_ping(self) -> dict: ...
    def _handle_status(self) -> dict: ...
    def _handle_export(self, params) -> dict: ...
    def _handle_import(self, params) -> dict: ...
    def _handle_project_tree(self) -> dict: ...
    def _handle_read_object(self, params) -> dict: ...
    def _handle_timestamps(self) -> dict: ...
```

### 5.5. GUI (Python 3 + PySide6)

```python
class MainWindow(QMainWindow):
    """Главное окно. Собирает все панели вместе."""
    def __init__(self, app_svc: IApplicationService): ...
    # Панели
    tree_panel: TreePanel
    editor_panel: EditorPanel
    # Toolbar actions
    def on_export_clicked(self): ...
    def on_import_clicked(self): ...
    def on_live_sync_toggled(self, enabled: bool): ...
    def on_settings_clicked(self): ...

class TreePanel(QWidget):
    """Панель дерева объектов."""
    def __init__(self): ...
    def load_tree(self, tree: ProjectTree) -> None: ...
    def set_object_status(self, guid: str, status: ObjectStatus) -> None: ...
    object_selected = Signal(str)  # guid

class EditorPanel(QWidget):
    """Панель редактора ST-кода."""
    def __init__(self): ...
    def load_object(self, meta: ObjectMeta, declaration: str, implementation: str | None) -> None: ...
    def get_modified_text(self) -> tuple[str, str | None]: ...
    def is_modified(self) -> bool: ...
    object_saved = Signal(str)  # guid

class SettingsDialog(QDialog):
    """Диалог настроек."""
    def __init__(self, settings: SyncSettings): ...
    def get_settings(self) -> SyncSettings: ...

class ApplicationService(IApplicationService):
    """
    Фасад для GUI. Связывает GUI с pipe transport и сервисами.
    
    В режиме демона — команды уходят через pipe.
    В автономном режиме — команды работают напрямую с IStorage.
    """
    def __init__(self, transport: ITransport | None, storage: IStorage): ...
    def export(self, filter: ObjectFilter) -> OperationResult: ...
    def import_(self, filter: ObjectFilter) -> OperationResult: ...
    def get_tree(self) -> ProjectTree: ...
    def read_object(self, guid: str) -> tuple[str, str | None]: ...
    def start_live_sync(self) -> None: ...
    def stop_live_sync(self) -> None: ...
```

---

## 6. Фабрики и DI

```python
# ─── IronPython (CodeSys) ────────────────────────────────
def build_daemon(project) -> DaemonDispatcher:
    """Собирает daemon с настоящим CodeSys API."""
    bridge = CodeSysBridge(project)
    extractor = TextExtractor()
    formatter = StFormatter()
    storage = FileSystemStorage(sync_dir=load_settings().sync_dir)
    export_svc = ExportService(bridge, extractor, storage, formatter)
    import_svc = ImportService(bridge, formatter, storage)
    dispatcher = DaemonDispatcher(bridge, export_svc, import_svc)
    return dispatcher

# ─── Python 3 (GUI) ──────────────────────────────────────
def build_gui_app(settings: SyncSettings) -> MainWindow:
    """Собирает GUI с pipe-транспортом."""
    transport = PipeTransport(settings.pipe_name, settings.pipe_timeout)
    storage = FileSystemStorage(settings.sync_dir)
    app_svc = ApplicationService(transport, storage)
    window = MainWindow(app_svc)
    return window

# ─── Тесты (Python 3) ────────────────────────────────────
def build_test_export_service(mock_bridge: ICodeSysBridge) -> ExportService:
    """Собирает ExportService с замоканным bridge для тестов."""
    extractor = TextExtractor()
    formatter = StFormatter()
    storage = MemoryStorage()  # In-memory для тестов
    return ExportService(mock_bridge, extractor, storage, formatter)
```

---

## 7. Структура директорий

```
cds-st-sync/                          # корень проекта
│
├── cds_bootstrap.py                  # загрузчик (IronPython)
│
├── src/
│   ├── domain/                       # ДОМЕН (нет зависимостей от API)
│   │   ├── __init__.py
│   │   ├── models.py                 # ObjectMeta, Manifest, ManifestDiff
│   │   ├── tree.py                   # ProjectTree
│   │   ├── filter.py                 # ObjectFilter
│   │   ├── result.py                 # OperationResult
│   │   └── settings.py               # SyncSettings
│   │
│   ├── interfaces/                   # ИНТЕРФЕЙСЫ (ABC)
│   │   ├── __init__.py
│   │   ├── bridge.py                 # ICodeSysBridge, IObjectReader, IObjectWriter
│   │   ├── storage.py                # IStorage
│   │   ├── transport.py              # ITransport
│   │   ├── extractor.py              # ITextExtractor, ITextFormatter
│   │   └── services.py               # IExportService, IImportService, ILiveSyncService
│   │
│   ├── infrastructure/               # ИНФРАСТРУКТУРА (IronPython + Python 3)
│   │   ├── __init__.py
│   │   ├── codesys_bridge.py         # CodeSysBridge (IronPython)
│   │   ├── codesys_object.py         # CodeSysObjectProxy (IronPython)
│   │   ├── text_extractor.py         # TextExtractor (общий)
│   │   ├── st_formatter.py           # StFormatter (общий)
│   │   ├── file_storage.py           # FileSystemStorage (общий)
│   │   ├── pipe_transport.py         # PipeTransport (Python 3 + Win32)
│   │   └── pipe_server.py            # PipeServerTransport (IronPython)
│   │
│   ├── services/                     # СЕРВИСЫ ПРИЛОЖЕНИЯ
│   │   ├── __init__.py
│   │   ├── export_service.py         # ExportService
│   │   ├── import_service.py         # ImportService
│   │   ├── live_sync_service.py      # LiveSyncService
│   │   ├── conflict_resolver.py      # ConflictResolver + LastWriteWins
│   │   └── application_service.py    # ApplicationService (фасад для GUI)
│   │
│   ├── daemon/                       # ДЕМОН (IronPython)
│   │   ├── __init__.py
│   │   ├── daemon_loop.py            # Главный цикл (pipe poll + dispatch)
│   │   ├── dispatcher.py             # DaemonDispatcher
│   │   └── state.py                  # Константы, хелперы, логирование
│   │
│   └── gui/                          # GUI (Python 3 + PySide6)
│       ├── __init__.py
│       ├── main.py                   # QApplication + entry point
│       ├── main_window.py            # MainWindow
│       ├── tree_panel.py             # TreePanel
│       ├── editor_panel.py           # EditorPanel
│       ├── settings_dialog.py        # SettingsDialog
│       ├── progress_widget.py        # ProgressWidget (progress bar + status)
│       └── st_highlighter.py         # StSyntaxHighlighter (IEC 61131-3)
│
├── scripts/                          # ТОЧКИ ВХОДА
│   ├── Project_options.py            # Режим B: настройка
│   ├── Project_export.py             # Режим B: экспорт
│   ├── Project_import.py             # Режим B: импорт
│   └── Project_daemon.py             # Режим A+C: демон
│
├── tests/                            # ТЕСТЫ (Python 3)
│   ├── __init__.py
│   ├── conftest.py                   # Фикстуры: mock_bridge, memory_storage, ...
│   ├── test_models.py                # ObjectMeta, Manifest, ManifestDiff
│   ├── test_filter.py                # ObjectFilter
│   ├── test_st_formatter.py          # parse_st → format_st roundtrip
│   ├── test_export_service.py        # ExportService с mock bridge
│   ├── test_import_service.py        # ImportService с mock bridge
│   ├── test_conflict_resolver.py     # Last-write-wins
│   └── test_live_sync.py             # LiveSyncService с моками
│
├── requirements.txt                  # PySide6, pytest
├── README.md
└── .gitignore
```

---

## 8. Диаграмма зависимостей (слои)

```
┌──────────────────────────────────────────────────────────┐
│                     Presentation                         │
│                      src/gui/                            │
│                          │                               │
│               зависит от IApplicationService             │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                  Application Services                     │
│                    src/services/                          │
│   ExportService, ImportService, LiveSyncService           │
│                          │                               │
│   зависит от ICodeSysBridge, IStorage, ITextExtractor,   │
│              ITextFormatter, IConflictResolver            │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                       Domain                             │
│                    src/domain/                            │
│   ObjectMeta, Manifest, ProjectTree, ObjectFilter, ...    │
│                                                          │
│   НЕ зависит ни от чего (чистые данные)                  │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                     Interfaces                            │
│                  src/interfaces/                          │
│   ICodeSysBridge, IStorage, ITransport, ...               │
│                                                          │
│   НЕ зависит от инфраструктуры (только ABC)              │
└──────────────────────────┬───────────────────────────────┘
                           │
┌──────────────────────────▼───────────────────────────────┐
│                    Infrastructure                         │
│                 src/infrastructure/                       │
│   CodeSysBridge, FileSystemStorage, PipeTransport, ...    │
│                                                          │
│   Реализует интерфейсы. Зависит от CodeSys API / Win32    │
└──────────────────────────────────────────────────────────┘
```

---

## 9. Что даёт такая архитектура

| Преимущество | Как достигнуто |
|-------------|---------------|
| **Тестируемость** | Сервисы зависят от ABC → мокаем bridge/storage → тесты без CodeSys |
| **Расширяемость** | Новый тип хранилища (`ZipStorage`, `GitStorage`) — просто реализовать `IStorage` |
| **Переиспользование** | `ExportService` один и тот же в демоне и в автономных скриптах |
| **Замена транспорта** | `PipeTransport` → `HttpTransport` / `LoopbackTransport` (для тестов) |
| **Независимость от CodeSys** | Только `CodeSysBridge` знает про IronPython API. При смене версии CodeSys — меняем только его |
| **Чистый GUI** | GUI ничего не знает про pipe, GUID-ы, CodeSys. Только `IApplicationService` |
