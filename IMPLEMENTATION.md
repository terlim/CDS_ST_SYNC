# Implementation Plan — Subagent Workflow v2 (OOP + SOLID)

> Каждый шаг = worker пишет → reviewer проверяет → 👤 пользователь подтверждает

---

## Шаги реализации

### Шаг 1: Domain Models + Interfaces
| Worker | `src/domain/models.py`, `src/interfaces/bridge.py`, `src/interfaces/storage.py`, `src/interfaces/services.py` |
|---------|------------------------------------------------------------------|
| **Что** | `ObjectMeta`, `Manifest`, `ProjectTree`, `ObjectFilter`, `OperationResult`, `SyncSettings`. Интерфейсы: `ICodeSysBridge`, `IStorage`, `IExportService`, `IImportService`, `ITextExtractor`, `ITextFormatter` |
| **Тест** | `test_models.py` — создание Manifest, diff, сериализация |
| 👤 | Подтвердить модели и интерфейсы |

### Шаг 2: Infrastructure — TextExtractor + StFormatter
| Worker | `src/infrastructure/text_extractor.py`, `src/infrastructure/st_formatter.py` |
|---------|------------------------------------------------------------------|
| **Что** | `TextExtractor` — извлечение textual_declaration/implementation. `StFormatter` — формат/парс .st с маркером `// --- implementation ---` |
| **Тест** | `test_st_formatter.py` — roundtrip: format → parse → исходные данные |
| 👤 | Подтвердить экстрактор и форматтер |

### Шаг 3: Infrastructure — FileSystemStorage
| Worker | `src/infrastructure/file_storage.py` |
|---------|------------------------------------------------------------------|
| **Что** | `FileSystemStorage` — запись/чтение .st + manifest.json с иерархией папок |
| **Тест** | `test_file_storage.py` — save/load ObjectMeta, Manifest roundtrip |
| 👤 | Подтвердить хранилище |

### Шаг 4: Infrastructure — CodeSysBridge
| Worker | `src/infrastructure/codesys_bridge.py`, `src/infrastructure/codesys_object.py` |
|---------|------------------------------------------------------------------|
| **Что** | `CodeSysObjectProxy` (тонкая обёртка). `CodeSysBridge` — единый класс, реализующий `ICodeSysBridge` (IObjectReader + IObjectWriter + ITimestampReader). ЕДИНСТВЕННЫЙ модуль, работающий с CodeSys API напрямую |
| **Тест** | ⚠️ Только в CodeSys. Reviewer проверяет код logic-only |
| 👤 | Подтвердить bridge |

### Шаг 5: Services — ExportService
| Worker | `src/services/export_service.py` |
|---------|------------------------------------------------------------------|
| **Что** | `ExportService(bridge, extractor, storage, formatter)` — оркестрация: обход объектов → фильтр → извлечение текста → формат .st → запись в storage. Прогресс-события через callback |
| **Тест** | `test_export_service.py` — с mock_bridge + memory_storage |
| 👤 | Подтвердить экспорт |

### Шаг 6: Services — ImportService
| Worker | `src/services/import_service.py` |
|---------|------------------------------------------------------------------|
| **Что** | `ImportService(bridge, formatter, storage)` — чтение manifest → для каждого объекта: поиск в CodeSys или create → запись textual_*. Прогресс-события |
| **Тест** | `test_import_service.py` — с mock_bridge + memory_storage |
| 👤 | Подтвердить импорт |

### Шаг 7: Консольные скрипты (Режим B)
| Worker | `scripts/Project_options.py`, `scripts/Project_export.py`, `scripts/Project_import.py`, `cds_bootstrap.py` |
|---------|------------------------------------------------------------------|
| **Что** | Тонкие entry points: создают CodeSysBridge, вызывают ExportService/ImportService. `cds_bootstrap.py` — загрузчик модулей |
| **Тест** | Ручной на amosova_v3 |
| 👤 | Подтвердить скрипты |

### Шаг 8: Daemon — state + dispatcher
| Worker | `src/daemon/state.py`, `src/daemon/dispatcher.py` |
|---------|------------------------------------------------------------------|
| **Что** | `state.py`: константы, pipe I/O, логирование. `dispatcher.py`: `DaemonDispatcher(bridge, export_svc, import_svc)` — dispatch таблица из 6 команд, вызывает сервисы |
| 👤 | Подтвердить daemon core |

### Шаг 9: Daemon — loop + entry point
| Worker | `src/daemon/daemon_loop.py`, `scripts/Project_daemon.py` |
|---------|------------------------------------------------------------------|
| **Что** | Polling loop: pipe connect → read JSON → dispatch → write response. `Project_daemon.py` — entry point (exec паттерн) |
| **Тест** | Ручной: запустить daemon, ping из Python |
| 👤 | Подтвердить daemon |

### Шаг 10: PipeTransport (Python 3)
| Worker | `src/infrastructure/pipe_transport.py` |
|---------|------------------------------------------------------------------|
| **Что** | `PipeTransport` реализует `ITransport` для Python 3 GUI. Win32 Named Pipe. Методы: connect, send, disconnect, on_progress |
| **Тест** | Ручной: ping daemon из Python скрипта |
| 👤 | Подтвердить pipe |

### Шаг 11: GUI — MainWindow + Settings
| Worker | `src/gui/main.py`, `src/gui/main_window.py`, `src/gui/settings_dialog.py`, `src/gui/progress_widget.py` |
|---------|------------------------------------------------------------------|
| **Что** | `MainWindow`: toolbar, progress, status. `SettingsDialog`: sync_dir, object filter, pipe, live sync. `ApplicationService` — фасад для GUI |
| 👤 | Подтвердить окно и настройки |

### Шаг 12: GUI — TreePanel + EditorPanel
| Worker | `src/gui/tree_panel.py`, `src/gui/editor_panel.py`, `src/gui/st_highlighter.py` |
|---------|------------------------------------------------------------------|
| **Что** | `TreePanel`: QTreeView + Manifest model + индикаторы статуса. `EditorPanel`: QPlainTextEdit + номера строк + ST-подсветка |
| 👤 | Подтвердить панели |

### Шаг 13: LiveSyncService
| Worker | `src/services/live_sync_service.py`, `src/services/conflict_resolver.py` |
|---------|------------------------------------------------------------------|
| **Что** | `LiveSyncService`: QFileSystemWatcher + daemon poll + ConflictResolver. Стратегия Last-Write-Wins |
| **Тест** | `test_live_sync.py`, `test_conflict_resolver.py` |
| 👤 | Подтвердить live sync |

### Шаг 14: Интеграция и финальное тестирование
| Worker | Интеграционные правки, `requirements.txt`, `install_daemon.py`, `install_gui.bat` |
|---------|------------------------------------------------------------------|
| **Тест** | Все 9 ручных тестов на amosova_v3 |
| 👤 | Финальное подтверждение |

### Шаг 15: .exe (опционально)
| Worker | `build_exe.bat`, `cds_st_sync.spec` |
|---------|------------------------------------------------------------------|
| **Что** | PyInstaller: один .exe без Python |
| 👤 | Подтвердить .exe |

---

## Граф зависимостей

```
Шаг 1 (модели + интерфейсы) ──┬──▶ Шаг 2 (extractor + formatter)
                              │         │
                              │         ▼
                              │    Шаг 3 (storage)
                              │         │
                              │         ├──▶ Шаг 5 (ExportService)
                              │         │         │
                              │         │         ▼
                              ├──▶ Шаг 4 (bridge) ──▶ Шаг 6 (ImportService)
                              │                          │
                              │                    ┌─────┴─────┐
                              │                    ▼           ▼
                              │              Шаг 7         Шаг 8
                              │           (скрипты B)   (dispatcher)
                              │                    │           │
                              │                    │           ▼
                              │                    │      Шаг 9 (daemon)
                              │                    │           │
                              │                    │           ▼
                              │                    │      Шаг 10 (pipe)
                              │                    │           │
                              │                    └─────┬─────┘
                              │                          ▼
                              │                    Шаг 11 (main window)
                              │                          │
                              │                          ▼
                              │                    Шаг 12 (tree + editor)
                              │                          │
                              └──────────────────────────┤
                                                         ▼
                                                   Шаг 13 (live sync)
                                                         │
                                                         ▼
                                                   Шаг 14 (интеграция)
                                                         │
                                                         ▼
                                                   Шаг 15 (.exe)
```
