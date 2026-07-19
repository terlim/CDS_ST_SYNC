# Architecture & Design Plan — CDS_ST_SYNC

> Версия: 2.0 | 2026-07-19

---

## 1. Режимы работы

### Режим A: Демон + GUI (интерактивный)

```
1. Пользователь в CodeSys: Tools → Scripting → Scripts → Project_daemon.py
2. Пользователь запускает внешний GUI (python main.py)
3. GUI ↔ Daemon общаются через Named Pipe
4. Все действия — через кнопки GUI
```

### Режим B: Автономные скрипты (без демона, без GUI)

```
Аналог референсного проекта cds-text-sync.
1. Project_options.py — настройка
2. Project_export.py — экспорт ST-кода в файлы
3. Project_import.py — импорт ST-кода из файлов
```

### Режим C: Онлайн-синхронизация (Live Sync) ⚡

```
Демон запущен. GUI запущен.
Система автоматически отслеживает изменения с обеих сторон:

   CodeSys IDE                    Файловая система
   ───────────                    ───────────────
   Изменение POU ────┐               ┌─── Изменение .st файла
                      ▼               ▼
               ┌─────────────────────────┐
               │     Live Sync Engine    │
               │                         │
               │  Daemon poll:           │
               │    object timestamps    │
               │                         │
               │  GUI watch:             │
               │    file mtime           │
               │                         │
               │  ┌───────────────────┐  │
               │  │ Last-Write-Wins   │  │
               │  │ Приоритет у того, │  │
               │  │ кто изменил       │  │
               │  │ ПОСЛЕДНИМ         │  │
               │  └───────────────────┘  │
               └─────────────────────────┘

GUI: кнопка [▶ Live Sync] вкл/выкл, статус синхронизации
```

### Сравнение режимов

| Действие | Режим A | Режим B | Режим C |
|----------|:------:|:------:|:------:|
| Настройка | Кнопка в GUI | `Project_options.py` | Кнопка в GUI |
| Экспорт | Кнопка в GUI | `Project_export.py` | Авто |
| Импорт | Кнопка в GUI | `Project_import.py` | Авто |
| Автосинхронизация | ❌ | ❌ | ✅ |
| Требуется GUI | ✅ | ❌ | ✅ |
| Требуется Pipe | ✅ | ❌ | ✅ |

---

## 2. Общая архитектура

```
┌─────────────────────────────────────────────────────────┐
│                 CodeSys IDE (Windows)                    │
│  ┌───────────────────────────────────────────────────┐  │
│  │           Daemon (IronPython 2.7)                 │  │
│  │  • Polling loop (200ms)                            │  │
│  │  • Named Pipe client                              │  │
│  │  • Команды: export, import, tree, timestamps       │  │
│  └──────────────────┬────────────────────────────────┘  │
└─────────────────────┼───────────────────────────────────┘
                      │  Named Pipe (JSON)
┌─────────────────────┼───────────────────────────────────┐
│  CDS_ST_SYNC GUI     │  (Python 3 + PySide6)            │
│                      │                                   │
│  ┌───────────────────▼──────────────────────────────┐   │
│  │              pipe_client.py                       │   │
│  └────────────────────┬─────────────────────────────┘   │
│                       │                                  │
│  ┌────────────────────▼─────────────────────────────┐   │
│  │              MainWindow                           │   │
│  │                                                    │   │
│  │  Toolbar: [Настройка] [Экспорт] [Импорт]          │   │
│  │           [▶ Live Sync] [🛑 Stop]                  │   │
│  │                                                    │   │
│  │  Прогресс: ████████████░░░░░░░░ 60%               │   │
│  │  Статус:   ● Online | Экспорт: 42/42 объектов      │   │
│  │                                                    │   │
│  │  ┌──────────┐ ┌──────────────────────────────┐    │   │
│  │  │ Project  │ │  ST Editor                    │    │   │
│  │  │ Tree     │ │  • syntax highlight           │    │   │
│  │  │          │ │  • line numbers               │    │   │
│  │  │ POU/GVL  │ │  • modified indicator *       │    │   │
│  │  │ DUT/ITF  │ │                               │    │   │
│  │  └──────────┘ └──────────────────────────────┘    │   │
│  └────────────────────────────────────────────────────┘   │
│                                                           │
│  ┌────────────────────────────────────────────────────┐   │
│  │  live_sync.py  ← QFileSystemWatcher + daemon poll  │   │
│  │  sync_conflict.py ← Last-Write-Wins resolver       │   │
│  └────────────────────────────────────────────────────┘   │
│                                                           │
│  ┌────────────────────────────────────────────────────┐   │
│  │              FileSystem (sync-dir/)                 │   │
│  │  manifest.json  +  *.st  files                     │   │
│  └────────────────────────────────────────────────────┘   │
└───────────────────────────────────────────────────────────┘
```

---

## 3. Прогресс и статус выполнения

### Прогресс-бар

Каждая длительная операция (экспорт/импорт/live sync) показывает прогресс:

```
┌─────────────────────────────────────────────────────────┐
│ [Настройка] [Экспорт] [Импорт] [▶ Live Sync] [🛑 Stop] │
├─────────────────────────────────────────────────────────┤
│ Прогресс: ████████████████░░░░░░░░░░░░ 60%              │
│ Статус:   Экспорт объектов... 25/42 (PLC_PRG)           │
└─────────────────────────────────────────────────────────┘
```

### Типы индикации

| Индикатор | Где | Что показывает |
|-----------|-----|---------------|
| **Прогресс-бар** | Под toolbar | Процент выполнения операции (0–100%) |
| **Статус-строка** | Низ окна | Текущее действие + счётчик (25/42) + имя объекта |
| **Индикатор подключения** | Справа в toolbar | ● зелёный = демон онлайн, ○ серый = нет связи |
| **Live Sync статус** | Слева от прогресс-бара | ▶ = активно, ⏸ = на паузе, ⚠ = конфликт |
| **Индикатор объекта** | В дереве | * = изменён, ↑ = новее в IDE, ↓ = новее на диске |

### События прогресса (Pipe-сообщения от демона)

```json
// Во время экспорта:
{"event": "progress", "action": "export", "current": 25, "total": 42, "object": "PLC_PRG"}
{"event": "progress", "action": "export", "current": 26, "total": 42, "object": "fb_Menu"}
...
{"event": "complete", "action": "export", "total": 42, "time_sec": 3.2}

// Во время импорта:
{"event": "progress", "action": "import", "current": 10, "total": 42, "object": "GVL_COLOR"}
...
{"event": "complete", "action": "import", "total": 42, "created": 3, "updated": 39}

// Live Sync обнаружено изменение:
{"event": "sync_change", "source": "ide", "guid": "...", "object": "PLC_PRG"}
{"event": "sync_change", "source": "file", "guid": "...", "object": "fb_Menu"}
```

---

## 4. Экран «Настройка»

```
┌─────────────────────────────────────────────┐
│  Настройки CDS_ST_SYNC                      │
├─────────────────────────────────────────────┤
│  Пути                                        │
│  ┌─────────────────────────────────────┐     │
│  │ Sync-директория: [C:\...\sync  ] [▶]│    │
│  └─────────────────────────────────────┘     │
│                                              │
│  Типы объектов для экспорта/импорта          │
│  ┌─────────────────────────────────────┐     │
│  │ ☑ POU (Program, Function Block,    │     │
│  │      Function)                      │     │
│  │ ☑ GVL (Global Variable Lists)      │     │
│  │ ☑ DUT (Data Unit Types)            │     │
│  │ ☑ Interface                        │     │
│  │ ☐ Persistent Variables             │     │
│  │ ☐ Task-local GVL                   │     │
│  └─────────────────────────────────────┘     │
│                                              │
│  Подключение                                 │
│  ┌─────────────────────────────────────┐     │
│  │ Pipe name: [cds-st-sync-...       ] │     │
│  │ Timeout:   [30] сек                 │     │
│  └─────────────────────────────────────┘     │
│                                              │
│  Live Sync                                   │
│  ┌─────────────────────────────────────┐     │
│  │ ☑ Автосинхронизация при старте     │     │
│  │ Интервал опроса IDE: [2] сек        │     │
│  │ ☑ Отслеживать изменения на диске   │     │
│  │ Стратегия конфликтов:              │     │
│  │   ● Last-Write-Wins               │     │
│  │   ○ Ручное разрешение              │     │
│  └─────────────────────────────────────┘     │
│                                              │
│            [Сохранить]  [Отмена]             │
└─────────────────────────────────────────────┘
```

---

## 5. Модули

### 5.1. Скрипты CodeSys (IronPython 2.7)

#### Общие

| Файл | Назначение |
|------|-----------|
| `cds_bootstrap.py` | Загрузчик runtime-модулей |
| `src/ide_bridge/cds_settings.py` | Чтение/запись `.cds-st-sync.json` |
| `src/ide_bridge/cds_export.py` | Ядро экспорта: обход, textual_* |
| `src/ide_bridge/cds_import.py` | Ядро импорта: поиск, создание, запись |
| `src/ide_bridge/cds_timestamps.py` | Timestamp-ы объектов для live sync |

#### Режимы A + C: Демон

| Файл | Назначение |
|------|-----------|
| `Project_daemon.py` | Точка входа демона |
| `src/ide_daemon/daemon_loop.py` | Цикл: pipe → read → dispatch → response |
| `src/ide_daemon/daemon_state.py` | Константы, хелперы, `sys._daemon` |
| `src/ide_daemon/handlers.py` | Обработчики команд |

**Daemon API:**

| Метод | Параметры | Возврат |
|-------|----------|---------|
| `ping` | — | `{status: "pong"}` |
| `export_text` | `{guids?: [...]}` | `{ok, count, objects[]}` + progress events |
| `import_text` | `{guids?: [...]}` | `{ok, updated, created, errors[]}` + progress events |
| `project_tree` | — | `{ok, tree: [{guid, name, type, path}]}` |
| `read_object` | `{guid}` | `{ok, declaration, implementation}` |
| `timestamps` | — | `{ok, objects: {guid: timestamp_ms}}` |

#### Режим B: Автономные скрипты

| Файл | Назначение |
|------|-----------|
| `Project_options.py` | Настройка (диалог) |
| `Project_export.py` | Экспорт ST-кода |
| `Project_import.py` | Импорт ST-кода |

### 5.2. Python 3 (GUI)

| Файл | Назначение |
|------|-----------|
| `main.py` | Точка входа |
| `pipe_client.py` | Named Pipe сервер, send/receive JSON, progress events |
| `main_window.py` | Главное окно, toolbar, статус, прогресс-бар |
| `settings_dialog.py` | Диалог настроек |
| `tree_panel.py` | Дерево объектов (QTreeView) |
| `editor_panel.py` | Редактор ST (QSyntaxHighlighter + номера строк) |
| `manifest.py` | Модель данных, manifest.json |
| `st_file.py` | Чтение/запись .st файлов |
| `live_sync.py` | **🆕** Движок live sync: QFileSystemWatcher + daemon poll + last-write-wins |
| `sync_conflict.py` | **🆕** Стратегии разрешения конфликтов |
| `progress.py` | **🆕** Модель прогресса: сигналы, состояния, отмена |

---

## 6. Иерархия и структура папок

### Принцип: полное соответствие CodeSys

```
CodeSys IDE                      Файловая система (sync-dir/)
════════════                      ══════════════════════════════
Device/                           Device/
├── Plc Logic/                    ├── Plc Logic/
│   └── Application/              │   └── Application/
│       └── PROGRAMS/             │       └── PROGRAMS/
│           ├── PLC_PRG           │           ├── PLC_PRG.st
│           └── POU_Menu          │           └── POU_Menu.st
├── CORE/                         ├── CORE/
│   └── Abstractions/             │   └── Abstractions/
│       └── MENU/                 │       └── MENU/
│           ├── ITF/I_Menu/       │           ├── ITF/I_Menu/
│           │   └── m_MoveLeft    │           │   └── m_MoveLeft.st
│           └── CLASS/            │           └── CLASS/
│               ├── fb_Menu       │               ├── fb_Menu.st
│               └── fb_MenuItem   │               └── fb_MenuItem.st
└── Global Vars/                  └── Global Vars/
    └── GVL_COLOR                     └── GVL_COLOR.st
```

### Правила
1. Папка CodeSys = директория на диске
2. Текстовый объект = .st файл в своей директории
3. `path: ["Device", "Plc Logic", "Application", "PROGRAMS"]` — в manifest.json
4. Безопасные имена: `<>:"/\\|?*` → `_`
5. Коллизии: `имя__XXXXXXXX.st` (первые 8 символов GUID)

### Сценарий: изменение структуры вне CodeSys

```
1. Пользователь меняет структуру на диске (папки, файлы)
2. Обновляет manifest.json
3. Импорт: сравнение с CodeSys
   a. Новые объекты → create_pou/gvl/dut в папках
   b. Перемещённые → удалить + создать (GUID изменится)
   c. Удалённые → пропускаются (защита от потери)
```

### Ограничения импорта структуры

| Операция | Статус |
|----------|:------:|
| Создать POU/GVL/DUT в папке | ✅ |
| Переместить в другую папку | ⚠️ удалить+создать |
| Переименовать | ✅ |
| Удалить | ⚠️ вручную |

---

## 7. Модель данных

### manifest.json

```json
{
  "version": 1,
  "project": "Amosova_V3",
  "exported_at": "2026-07-19T15:30:00",
  "objects": [
    {
      "guid": "4140366f-...",
      "name": "PLC_PRG",
      "type": "pou",
      "pou_kind": "program",
      "path": ["Device", "Plc Logic", "Application", "PROGRAMS"],
      "file": "Device/Plc Logic/Application/PROGRAMS/PLC_PRG.st",
      "sha1": "d3486ae9...",
      "ide_timestamp_ms": 639200567571029353,
      "file_mtime": 1721395800.0
    }
  ]
}
```

### Формат .st файла

```
{attribute 'qualified_only'}
VAR_GLOBAL CONSTANT
    c_dwBgGray_20: DWORD := 16#FFD5D7DC;
END_VAR

// --- implementation ---

// Только для POU
```

---

## 8. Этапы разработки

### Этап 1: Ядро (общие модули) ✅
- [x] `cds_bootstrap.py` — загрузчик
- [x] `cds_settings.py` — настройки .cds-st-sync.json
- [x] `cds_export.py` — ядро экспорта с сохранением иерархии
- [x] `cds_import.py` — ядро импорта с созданием папок
- [x] `cds_timestamps.py` — timestamp-ы объектов

### Этап 2: Автономные скрипты (режим B) ✅
- [x] `Project_options.py`
- [x] `Project_export.py`
- [x] `Project_import.py`
- [x] Тестирование на amosova_v3
- [ ] **TODO: проверка всех типов текстовых объектов на выгрузку**
- [ ] **TODO: скрытый маркер для виртуальных папок в manifest (для упрощения импорта)**
  - Поле `virtual_folders: list[str]` в ObjectMeta
  - ExportService заполняет при virtual-режиме
  - ImportService._ensure_container() пропускает виртуальные папки
  - Старые манифесты: `[]` по умолчанию

### Этап 3: Демон (режим A)
- [ ] `daemon_loop.py` — цикл, pipe, dispatch
- [ ] `handlers.py` — все обработчики + progress events
- [ ] `Project_daemon.py` — точка входа

### Этап 4: Python 3 core
- [ ] `pipe_client.py` — Pipe + progress events
- [ ] `manifest.py` — модель данных
- [ ] `st_file.py` — чтение/запись .st
- [ ] `progress.py` — модель прогресса

### Этап 5: GUI
- [ ] `main_window.py` — окно, toolbar, прогресс-бар, статус
- [ ] `settings_dialog.py` — настройки + live sync
- [ ] `tree_panel.py` — дерево с индикаторами
- [ ] `editor_panel.py` — редактор с подсветкой

### Этап 6: Live Sync (режим C)
- [ ] `live_sync.py` — QFileSystemWatcher + daemon poll
- [ ] `sync_conflict.py` — last-write-wins resolver
- [ ] Интеграция в main_window

### Этап 7: Интеграция и финализация
- [ ] Полный цикл: export → edit → import
- [ ] Live sync тестирование
- [ ] Тестирование на amosova_v3
- [ ] Установщики: `install_daemon.py`, `install_gui.bat`

### Этап 8: Сборка .exe (фича, опционально)
- [ ] `build_exe.bat` — скрипт сборки через PyInstaller
- [ ] `cds_st_sync.spec` — конфигурация PyInstaller
- [ ] Тестирование .exe на чистой Windows без Python

> **Цель**: один `CDS_ST_SYNC.exe` который пользователь запускает двойным кликом.
> Включает: GUI, pipe_client, все зависимости (PySide6).
> Не включает: daemon (он внутри CodeSys, не требует компиляции).

---

## 9. Технические решения

| Вопрос | Решение |
|--------|---------|
| GUI | **PySide6** (Qt for Python, LGPL) |
| Named Pipe | Win32 API через ctypes |
| Подсветка ST | QSyntaxHighlighter, правила IEC 61131-3 |
| Отслеживание файлов | QFileSystemWatcher |
| Настройки | QSettings (.ini в sync_dir) |
| Прогресс | QProgressBar + pipe events |
| IronPython | `from __future__ import print_function` |
| Упаковка GUI | PyInstaller → .exe (единый файл, без установки Python) |
| Установка демона | Копирование в `%APPDATA%\CODESYS\ScriptDir` |
| Конфликты | Last-Write-Wins (сравнение timestamp_ms vs file_mtime) |
