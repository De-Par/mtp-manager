#!/usr/bin/env python3
from __future__ import annotations

import dataclasses
import datetime as dt
import fcntl
import os
import re
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import textwrap
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

APP_NAME = "MTProxy Manager"
APP_VERSION = "6.0"

DEFAULT_SELF_INSTALL_PATH = Path("/usr/local/bin/mtproxy-manager.py")
DEFAULT_MT_DIR = Path("/opt/MTProxy")
DEFAULT_CONF_DIR = Path("/etc/mtproxy-manager")
DEFAULT_DATA_DIR = Path("/var/lib/mtproxy-manager")
DEFAULT_LOCK_FILE = Path("/var/lock/mtproxy-manager.lock")
DEFAULT_EXPORT_FILE = Path("/root/mtproxy-links.txt")
DEFAULT_SERVICE_FILE = Path("/etc/systemd/system/mtproxy.service")
DEFAULT_REFRESH_SERVICE_FILE = Path("/etc/systemd/system/mtproxy-config-update.service")
DEFAULT_REFRESH_TIMER_FILE = Path("/etc/systemd/system/mtproxy-config-update.timer")
DEFAULT_CLEANUP_SERVICE_FILE = Path("/etc/systemd/system/mtproxy-cleanup.service")
DEFAULT_CLEANUP_TIMER_FILE = Path("/etc/systemd/system/mtproxy-cleanup.timer")
DEFAULT_SYSCTL_FILE = Path("/etc/sysctl.d/99-mtproxy-vps.conf")
DEFAULT_SWAP_MARKER = DEFAULT_DATA_DIR / "managed_swap_1g"
DEFAULT_SWAP_FILE = Path("/swapfile")
DEFAULT_INVENTORY_FILE = DEFAULT_CONF_DIR / "inventory.tsv"
DEFAULT_CONFIG_FILE = DEFAULT_CONF_DIR / "mtproxy.conf"
DEFAULT_SECRETS_FILE = DEFAULT_CONF_DIR / "secrets.txt"
DEFAULT_PROXY_SECRET_FILE = DEFAULT_MT_DIR / "objs/bin/proxy-secret"
DEFAULT_PROXY_CONFIG_FILE = DEFAULT_MT_DIR / "objs/bin/proxy-multi.conf"
DEFAULT_BINARY_FILE = DEFAULT_MT_DIR / "objs/bin/mtproto-proxy"

PROXY_SECRET_URL = "https://core.telegram.org/getProxySecret"
PROXY_CONFIG_URL = "https://core.telegram.org/getProxyConfig"
IP_DISCOVERY_URL = "https://api.ipify.org"

LABEL_RE = re.compile(r"^[A-Za-z0-9._@-]{1,64}$")
DOMAIN_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?(?:\.[A-Za-z0-9](?:[A-Za-z0-9-]{0,61}[A-Za-z0-9])?)+$")
PORT_MIN = 1
PORT_MAX = 65535


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


class AppError(RuntimeError):
    def __init__(self, message: str | None = None, *, key: str | None = None, **kwargs: object) -> None:
        self.message = message
        self.key = key
        self.kwargs = kwargs
        super().__init__(message or key or self.__class__.__name__)


class ValidationError(AppError):
    pass


class CancelledError(AppError):
    pass


@dataclass(frozen=True)
class MenuAction:
    key: str
    label: str
    handler: Callable[[], object | None]
    pause_after: bool = True


@dataclass(frozen=True)
class Paths:
    self_install_path: Path = DEFAULT_SELF_INSTALL_PATH
    mt_dir: Path = DEFAULT_MT_DIR
    conf_dir: Path = DEFAULT_CONF_DIR
    data_dir: Path = DEFAULT_DATA_DIR
    lock_file: Path = DEFAULT_LOCK_FILE
    export_file: Path = DEFAULT_EXPORT_FILE
    service_file: Path = DEFAULT_SERVICE_FILE
    refresh_service_file: Path = DEFAULT_REFRESH_SERVICE_FILE
    refresh_timer_file: Path = DEFAULT_REFRESH_TIMER_FILE
    cleanup_service_file: Path = DEFAULT_CLEANUP_SERVICE_FILE
    cleanup_timer_file: Path = DEFAULT_CLEANUP_TIMER_FILE
    sysctl_file: Path = DEFAULT_SYSCTL_FILE
    swap_marker: Path = DEFAULT_SWAP_MARKER
    swap_file: Path = DEFAULT_SWAP_FILE
    inventory_file: Path = DEFAULT_INVENTORY_FILE
    config_file: Path = DEFAULT_CONFIG_FILE
    secrets_file: Path = DEFAULT_SECRETS_FILE

    @property
    def bin_dir(self) -> Path:
        return self.mt_dir / "objs/bin"

    @property
    def binary_file(self) -> Path:
        return self.mt_dir / "objs/bin/mtproto-proxy"

    @property
    def proxy_secret_file(self) -> Path:
        return self.mt_dir / "objs/bin/proxy-secret"

    @property
    def proxy_config_file(self) -> Path:
        return self.mt_dir / "objs/bin/proxy-multi.conf"


@dataclass
class Settings:
    mt_port: int = 443
    stats_port: int = 8888
    workers: int = 1
    tls_domain: str = ""
    ad_tag: str = ""
    ui_lang: str = "en"

    @classmethod
    def from_mapping(cls, mapping: dict[str, str]) -> "Settings":
        def _int(name: str, default: int) -> int:
            value = str(mapping.get(name, default)).strip()
            if not value.isdigit():
                return default
            number = int(value)
            return default if not (PORT_MIN <= number <= PORT_MAX) else number

        ui_lang = str(mapping.get("UI_LANG", "en")).strip().lower()
        if ui_lang not in {"ru", "en"}:
            ui_lang = "en"

        workers_raw = str(mapping.get("WORKERS", "1")).strip()
        workers = int(workers_raw) if workers_raw.isdigit() and int(workers_raw) >= 0 else 1
        tls_domain = str(mapping.get("TLS_DOMAIN", "")).strip()
        if tls_domain and not DOMAIN_RE.fullmatch(tls_domain):
            tls_domain = ""

        return cls(
            mt_port=_int("MT_PORT", 443),
            stats_port=_int("STATS_PORT", 8888),
            workers=workers,
            tls_domain=tls_domain,
            ad_tag=str(mapping.get("AD_TAG", "")).strip(),
            ui_lang=ui_lang,
        )

    def to_mapping(self) -> dict[str, str]:
        return {
            "MT_PORT": str(self.mt_port),
            "STATS_PORT": str(self.stats_port),
            "WORKERS": str(self.workers),
            "TLS_DOMAIN": self.tls_domain,
            "AD_TAG": self.ad_tag,
            "UI_LANG": self.ui_lang,
        }

    def validate(self) -> None:
        validate_port(self.mt_port, "MT_PORT")
        validate_port(self.stats_port, "STATS_PORT")
        if self.workers < 0:
            raise ValidationError(key="workers_positive")
        if self.ui_lang not in {"ru", "en"}:
            raise ValidationError(key="ui_lang_invalid")
        if self.tls_domain and not DOMAIN_RE.fullmatch(self.tls_domain):
            raise ValidationError(key="tls_domain_invalid")


@dataclass
class SecretRecord:
    id: int
    enabled: bool
    user: str
    secret: str
    created_at: str
    note: str = ""

    def masked_secret(self) -> str:
        secret = self.secret
        if len(secret) <= 12:
            return secret
        return f"{secret[:6]}...{secret[-6:]}"

    def validate(self) -> None:
        if self.id <= 0:
            raise ValidationError(key="record_id_positive")
        validate_label(self.user)
        if not self.secret or any(ch.isspace() for ch in self.secret):
            raise ValidationError(key="secret_invalid_user", user=self.user)


class I18N:
    STRINGS: dict[str, dict[str, str]] = {
        "ru": {
            "section_setup": "Установка и обновления",
            "section_secrets": "Пользователи и секреты",
            "section_service": "Сервис",
            "section_monitoring": "Статус и отчёты",
            "section_maintenance": "Обслуживание",
            "section_danger": "Опасная зона",
            "back": "Назад",
            "exit": "Выход",
            "yes": "Да",
            "no": "Нет",
            "select": "Выбрать",
            "save_action": "Сохранить",
            "continue_action": "Продолжить",
            "close_action": "Закрыть",
            "delete_action": "Удалить",
            "reset_action": "Сбросить",
            "main_menu": "Главное меню",
            "exit_back": "Выход/Назад",
            "invalid_choice": "Неверный выбор",
            "service_state_active": "активен",
            "service_state_inactive": "не активен",
            "service_state_failed": "ошибка",
            "service_state_activating": "запускается",
            "service_state_deactivating": "останавливается",
            "service_state_not_installed": "не установлен",
            "service_state_unknown": "неизвестно",
            "language_changed": "Язык интерфейса обновлён",
            "saved": "Сохранено",
            "done": "Готово",
            "cancelled": "Отменено",
            "warning": "Предупреждение",
            "error": "Ошибка",
            "choose": "Выберите действие",
            "press_enter": "Нажмите Enter, чтобы продолжить...",
            "need_root": "Скрипт нужно запускать от root",
            "platform_ok": "Поддерживается только Debian/Ubuntu",
            "no_records": "Записей пока нет",
            "no_users": "Пользователей пока нет",
            "no_enabled_secrets": "Нет включённых секретов. Сервис будет остановлен.",
            "welcome": "Добро пожаловать в {app} v{version}",
            "lang_name_ru": "Русский",
            "lang_name_en": "Английский",
            "state_on": "ВКЛ",
            "state_off": "ВЫКЛ",
            "value_ok": "в порядке",
            "value_missing": "отсутствует",
            "value_unknown": "неизвестно",
            "value_disabled": "отключено",
            "table_id": "ID",
            "table_state": "состояние",
            "table_user": "пользователь",
            "table_secret": "секрет",
            "table_created_at": "создан",
            "table_note": "заметка",
            "table_check": "проверка",
            "table_value": "значение",
            "user_card_title": "Карточка пользователя: {user}",
            "enabled_total": "Активно: {enabled} / Всего: {total}",
            "welcome_platform": "Платформа: {distro} {version}",
            "welcome_public_ip": "Публичный IP: {ip}",
            "welcome_service_state": "Состояние сервиса: {state}",
            "welcome_enabled_users": "Активных пользователей: {count}",
            "welcome_enabled_secrets": "Активных секретов: {count}",
            "welcome_total_secrets": "Всего секретов: {count}",
            "welcome_ui_language": "Язык интерфейса: {language}",
            "menu_change_language": "Сменить язык интерфейса",
            "panel_service_summary": "Сервис: {state}",
            "panel_ip_summary": "Публичный IP: {ip}",
            "panel_ports_summary": "Порты: клиентский {client_port} / статистика {stats_port}",
            "panel_workers_summary": "Рабочих процессов: {workers}",
            "panel_tls_summary": "Маскировка TLS: {domain}",
            "panel_tls_off": "Маскировка TLS: выключена",
            "panel_source_summary": "Исходники: репозиторий={git_state}, бинарник={binary_state}",
            "panel_no_active_keys": "Активных ключей пока нет",
            "panel_more_keys": "Ещё ключей: {count}",
            "panel_key_line": "#{record_id} {user} | raw={raw} | dd={padded}",
            "panel_key_line_fake": "#{record_id} {user} | raw={raw} | dd={padded} | ee={fake}",
            "setup_install": "Первичная настройка",
            "setup_update": "Обновить MTProxy",
            "setup_weak": "Оптимизация слабого VPS",
            "setup_refresh": "Обновить proxy config",
            "setup_installed_script": "Установлено. Сервисный скрипт: {path}",
            "setup_updated": "MTProxy обновлён",
            "setup_weak_applied": "Применено. рабочих процессов={workers}",
            "setup_proxy_config_updated": "Файл proxy-multi.conf обновлён",
            "setup_proxy_config_unchanged": "Файл proxy-multi.conf уже актуален",
            "source_management_existing": "Управление исходниками: найден текущий репозиторий MTProxy",
            "source_management_repo_no_binary": "Найден репозиторий без собранного бинарника",
            "source_management_no_git": "Каталог /opt/MTProxy существует без Git-репозитория",
            "source_use_current": "Использовать текущую сборку без изменений",
            "source_pull_rebuild": "Подтянуть изменения из репозитория и пересобрать",
            "source_rebuild": "Пересобрать текущий репозиторий",
            "source_fresh_clone": "Удалить и клонировать заново",
            "source_build_current": "Собрать текущий репозиторий",
            "source_use_existing_binary": "Использовать существующий бинарник",
            "source_try_build_current": "Попробовать собрать текущий каталог",
            "select_secret": "Выберите секрет",
            "select_user": "Выберите пользователя",
            "record_summary": "[{state}] пользователь={user} секрет={secret} создан={created_at} заметка={note}",
            "user_summary": "активно={enabled} всего={total}",
            "add_secret": "Добавить секрет",
            "enable_one_secret": "Включить секрет",
            "disable_one_secret": "Отключить секрет",
            "enable_user_secrets": "Включить всё у пользователя",
            "disable_user_secrets": "Отключить всё у пользователя",
            "rotate_one_secret": "Сменить секрет",
            "rotate_user_secrets": "Сменить у пользователя",
            "rotate_all_secrets": "Сменить все активные",
            "delete_one_secret": "Удалить секрет",
            "delete_user_secrets": "Удалить всё у пользователя",
            "show_inventory": "Инвентарь",
            "show_keys_panel": "Показать ключи",
            "show_user_keys_panel": "Ключи пользователя",
            "export_all_links": "Экспорт ключей",
            "export_user_links": "Экспорт пользователя",
            "user_card": "Карточка",
            "user_label": "Метка пользователя",
            "optional_note": "Необязательная заметка",
            "added_secret_id": "Добавлен секрет id={record_id}",
            "secret_enabled": "Секрет включён",
            "secret_disabled": "Секрет отключён",
            "enabled_count": "Включено секретов: {count}",
            "disabled_count": "Отключено секретов: {count}",
            "rotated_secret_id": "Секрет id={record_id} обновлён",
            "rotated_count": "Обновлено секретов: {count}",
            "delete_secret_confirm": "Удалить секрет id={record_id}?",
            "secret_deleted": "Секрет удалён",
            "delete_user_confirm": "Удалить все секреты пользователя {user}?",
            "deleted_count": "Удалено секретов: {count}",
            "exported_to": "Экспортировано в {path}",
            "service_start": "Запустить сервис",
            "service_stop": "Остановить сервис",
            "service_restart": "Перезапустить сервис",
            "service_status": "Статус",
            "service_logs": "Логи",
            "service_started": "Сервис запущен",
            "service_stopped": "Сервис остановлен",
            "service_restarted": "Сервис перезапущен",
            "service_status_title": "Статус сервиса",
            "service_logs_title": "Логи сервиса",
            "service_not_installed": "Сервис ещё не установлен",
            "monitor_show_status": "Статус сервиса",
            "monitor_health": "Проверить состояние",
            "monitor_inventory": "Инвентарь",
            "maintenance_config": "Параметры MTProxy",
            "maintenance_cleanup": "Очистка",
            "maintenance_rewrite": "Перезаписать unit-файлы",
            "client_port": "Клиентский порт",
            "stats_port": "Порт статистики",
            "worker_count": "Количество рабочих процессов",
            "fake_tls_domain": "Домен для маскировки TLS (пусто = выключить, пример: cloudflare.com)",
            "setup_fake_tls_prompt": "Настройте домен Fake TLS для первичной установки (пусто = выключить, пример: cloudflare.com)",
            "section_secret_access": "Вкл / выкл",
            "section_secret_rotate": "Ротация",
            "section_secret_delete": "Удаление",
            "section_secret_view": "Ключи и экспорт",
            "section_secret_browse": "Пользователи",
            "ad_tag_prompt": "Необязательный тег @MTProxyBot",
            "runtime_config_updated": "Рабочая конфигурация обновлена",
            "cleanup_finished": "Очистка завершена",
            "units_rewritten": "Управляемые unit-файлы перезаписаны",
            "choose_interface_language": "Выберите язык интерфейса",
            "language_ru": "Русский",
            "language_en": "Английский",
            "choose_key_variant": "Выберите набор ключей",
            "key_variant_all": "Все варианты",
            "key_variant_raw": "Обычный секрет",
            "key_variant_padded": "С дополнением (dd)",
            "key_variant_fake": "С маскировкой TLS (ee)",
            "keys_panel_title": "Активные ключи",
            "keys_user_panel_title": "Ключи пользователя: {user}",
            "keys_panel_empty": "Нет активных ключей для отображения",
            "card_keys_title": "Ключи",
            "factory_reset_action": "Полный сброс",
            "factory_reset_confirm": "Будут удалены управляемые файлы, unit-файлы, inventory, конфиг и при необходимости дерево исходников. Продолжить?",
            "factory_reset_complete": "Полный сброс завершён",
            "health_binary": "бинарник",
            "health_proxy-secret": "файл proxy-secret",
            "health_proxy-config": "файл proxy-multi.conf",
            "health_service": "сервис",
            "health_enabled-secrets": "включённые секреты",
            "health_public-ip": "публичный IP",
            "health_client-port": "клиентский порт",
            "health_stats-port": "порт статистики",
            "health_workers": "рабочие процессы",
            "health_fake-tls-domain": "домен маскировки TLS",
            "export_header": "[пользователь={user}] [id={record_id}] заметка={note}",
            "export_raw_secret": "  raw        : {value}",
            "export_padded_secret": "  padded     : {value}",
            "export_fake_tls": "  fake tls   : {value}",
            "workers_positive": "WORKERS должен быть неотрицательным целым числом",
            "ui_lang_invalid": "UI_LANG должен быть 'ru' или 'en'",
            "tls_domain_invalid": "TLS_DOMAIN некорректен",
            "record_id_positive": "id записи должен быть положительным",
            "secret_invalid_user": "секрет пользователя '{user}' некорректен",
            "expected_integer": "{prompt}: ожидается целое число",
            "terminal_ui_requires_terminal": "Терминальный UI требует интерактивный терминал и установленный dialog или whiptail",
            "already_running": "Уже запущен другой экземпляр {app}",
            "legacy_import_note": "Импортировано из старого файла secrets.txt",
            "duplicate_id": "Дублирующийся id {record_id}",
            "duplicate_secret_user": "Дублирующийся секрет для пользователя {user}",
            "label_invalid": "Метка должна соответствовать [A-Za-z0-9._@-]{1,64}",
            "port_range": "{field_name} должен быть в диапазоне {min_port}..{max_port}",
            "secret_exists": "Такой секрет уже существует",
            "record_not_found": "Запись id {record_id} не найдена",
            "user_not_found": "Пользователь '{user}' не найден",
            "no_matching_records_user": "Для пользователя '{user}' нет подходящих записей",
            "os_release_missing": "Файл /etc/os-release отсутствует",
            "unsupported_distribution": "Неподдерживаемый дистрибутив: {distro}. Поддерживаются Debian и Ubuntu.",
            "binary_not_found": "Бинарник не найден: {path}",
            "source_dir_not_found": "Каталог исходников не найден: {path}",
            "git_checkout_not_found": "Git-репозиторий не найден: {path}",
            "mtproto_binary_not_found": "Бинарник mtproto-proxy не найден",
            "unsupported_source_mode": "Неподдерживаемый режим подготовки исходников: {mode}",
            "missing_proxy_secret_file": "Отсутствует файл proxy-secret: {path}",
            "missing_proxy_config_file": "Отсутствует файл proxy-multi.conf: {path}",
            "secrets_file_empty": "Файл secrets пуст: {path}",
            "interactive_terminal_required": "Менеджер нужно запускать из интерактивного терминала",
            "need_root_install_dialog": "Запустите скрипт от root, чтобы установить whiptail",
            "unsupported_internal_command": "Неподдерживаемая внутренняя команда: {command}",
        },
        "en": {
            "section_setup": "Setup & Updates",
            "section_secrets": "Users & Secrets",
            "section_service": "Service",
            "section_monitoring": "Status & Reports",
            "section_maintenance": "Maintenance",
            "section_danger": "Danger Zone",
            "back": "Back",
            "exit": "Exit",
            "yes": "Yes",
            "no": "No",
            "select": "Select",
            "save_action": "Save",
            "continue_action": "Continue",
            "close_action": "Close",
            "delete_action": "Delete",
            "reset_action": "Reset",
            "main_menu": "Main Menu",
            "exit_back": "Exit/Back",
            "invalid_choice": "Invalid choice",
            "service_state_active": "active",
            "service_state_inactive": "inactive",
            "service_state_failed": "failed",
            "service_state_activating": "activating",
            "service_state_deactivating": "deactivating",
            "service_state_not_installed": "not installed",
            "service_state_unknown": "unknown",
            "language_changed": "Interface language updated",
            "saved": "Saved",
            "done": "Done",
            "cancelled": "Cancelled",
            "warning": "Warning",
            "error": "Error",
            "choose": "Choose an action",
            "press_enter": "Press Enter to continue...",
            "need_root": "Please run this script as root",
            "platform_ok": "Only Debian/Ubuntu are supported",
            "no_records": "No records yet",
            "no_users": "No users yet",
            "no_enabled_secrets": "No enabled secrets left. The service will be stopped.",
            "welcome": "Welcome to {app} v{version}",
            "lang_name_ru": "Russian",
            "lang_name_en": "English",
            "state_on": "ON",
            "state_off": "OFF",
            "value_ok": "ok",
            "value_missing": "missing",
            "value_unknown": "unknown",
            "value_disabled": "disabled",
            "table_id": "id",
            "table_state": "state",
            "table_user": "user",
            "table_secret": "secret",
            "table_created_at": "created_at",
            "table_note": "note",
            "table_check": "check",
            "table_value": "value",
            "user_card_title": "User card: {user}",
            "enabled_total": "Enabled: {enabled} / Total: {total}",
            "welcome_platform": "Platform: {distro} {version}",
            "welcome_public_ip": "Public IP: {ip}",
            "welcome_service_state": "Service state: {state}",
            "welcome_enabled_users": "Enabled users: {count}",
            "welcome_enabled_secrets": "Enabled secrets: {count}",
            "welcome_total_secrets": "Total secrets: {count}",
            "welcome_ui_language": "UI language: {language}",
            "menu_change_language": "Change interface language",
            "panel_service_summary": "Service: {state}",
            "panel_ip_summary": "Public IP: {ip}",
            "panel_ports_summary": "Ports: client {client_port} / stats {stats_port}",
            "panel_workers_summary": "Workers: {workers}",
            "panel_tls_summary": "Fake TLS: {domain}",
            "panel_tls_off": "Fake TLS: off",
            "panel_source_summary": "Source: git={git_state}, binary={binary_state}",
            "panel_no_active_keys": "No active keys yet",
            "panel_more_keys": "More keys: {count}",
            "panel_key_line": "#{record_id} {user} | raw={raw} | dd={padded}",
            "panel_key_line_fake": "#{record_id} {user} | raw={raw} | dd={padded} | ee={fake}",
            "setup_install": "Initial setup",
            "setup_update": "Update MTProxy",
            "setup_weak": "Weak VPS tuning",
            "setup_refresh": "Refresh proxy config",
            "setup_installed_script": "Installed. Service script: {path}",
            "setup_updated": "MTProxy updated",
            "setup_weak_applied": "Applied. workers={workers}",
            "setup_proxy_config_updated": "proxy-multi.conf updated",
            "setup_proxy_config_unchanged": "proxy-multi.conf already up to date",
            "source_management_existing": "Source Management: existing MTProxy checkout found",
            "source_management_repo_no_binary": "Repository found without a built binary",
            "source_management_no_git": "/opt/MTProxy exists without .git",
            "source_use_current": "Use the current build as-is",
            "source_pull_rebuild": "Pull from git and rebuild",
            "source_rebuild": "Rebuild the current checkout",
            "source_fresh_clone": "Delete and clone a fresh copy",
            "source_build_current": "Build the current checkout",
            "source_use_existing_binary": "Use the existing binary",
            "source_try_build_current": "Try to build the current directory",
            "select_secret": "Select a secret",
            "select_user": "Select a user",
            "record_summary": "[{state}] user={user} secret={secret} created={created_at} note={note}",
            "user_summary": "enabled={enabled} total={total}",
            "add_secret": "Add secret",
            "enable_one_secret": "Enable secret",
            "disable_one_secret": "Disable secret",
            "enable_user_secrets": "Enable all for user",
            "disable_user_secrets": "Disable all for user",
            "rotate_one_secret": "Rotate secret",
            "rotate_user_secrets": "Rotate user secrets",
            "rotate_all_secrets": "Rotate all active",
            "delete_one_secret": "Delete secret",
            "delete_user_secrets": "Delete all for user",
            "show_inventory": "Inventory",
            "show_keys_panel": "Show keys",
            "show_user_keys_panel": "User keys",
            "export_all_links": "Export keys",
            "export_user_links": "Export user",
            "user_card": "User card",
            "user_label": "User label",
            "optional_note": "Optional note",
            "added_secret_id": "Added secret id={record_id}",
            "secret_enabled": "Secret enabled",
            "secret_disabled": "Secret disabled",
            "enabled_count": "Enabled {count} secret(s)",
            "disabled_count": "Disabled {count} secret(s)",
            "rotated_secret_id": "Rotated secret id={record_id}",
            "rotated_count": "Rotated {count} secret(s)",
            "delete_secret_confirm": "Delete secret id={record_id}?",
            "secret_deleted": "Secret deleted",
            "delete_user_confirm": "Delete all secrets for {user}?",
            "deleted_count": "Deleted {count} secret(s)",
            "exported_to": "Exported to {path}",
            "service_start": "Start service",
            "service_stop": "Stop service",
            "service_restart": "Restart service",
            "service_status": "Status",
            "service_logs": "Logs",
            "service_started": "Service started",
            "service_stopped": "Service stopped",
            "service_restarted": "Service restarted",
            "service_status_title": "Service status",
            "service_logs_title": "Service logs",
            "service_not_installed": "Service is not installed yet",
            "monitor_show_status": "Service status",
            "monitor_health": "Run health check",
            "monitor_inventory": "Inventory",
            "maintenance_config": "MTProxy settings",
            "maintenance_cleanup": "Cleanup",
            "maintenance_rewrite": "Rewrite unit files",
            "client_port": "Client port",
            "stats_port": "Stats port",
            "worker_count": "Worker count",
            "fake_tls_domain": "Fake TLS domain (empty to disable, example: cloudflare.com)",
            "setup_fake_tls_prompt": "Configure the Fake TLS domain for the initial setup (empty to disable, example: cloudflare.com)",
            "section_secret_access": "Enable / disable",
            "section_secret_rotate": "Rotate",
            "section_secret_delete": "Delete secrets",
            "section_secret_view": "Keys & export",
            "section_secret_browse": "Users",
            "ad_tag_prompt": "Optional @MTProxyBot tag",
            "runtime_config_updated": "Runtime configuration updated",
            "cleanup_finished": "Cleanup finished",
            "units_rewritten": "Managed unit files rewritten",
            "choose_interface_language": "Choose interface language",
            "language_ru": "Russian",
            "language_en": "English",
            "choose_key_variant": "Choose key set",
            "key_variant_all": "All variants",
            "key_variant_raw": "Raw secret",
            "key_variant_padded": "Padded secret (dd)",
            "key_variant_fake": "Fake TLS secret (ee)",
            "keys_panel_title": "Active keys",
            "keys_user_panel_title": "Keys for user: {user}",
            "keys_panel_empty": "No active keys to display",
            "card_keys_title": "Keys",
            "factory_reset_action": "Factory reset",
            "factory_reset_confirm": "This will destroy managed files, service units, inventory, config and optionally the source tree. Continue?",
            "factory_reset_complete": "Factory reset complete",
            "health_binary": "binary",
            "health_proxy-secret": "proxy-secret",
            "health_proxy-config": "proxy-config",
            "health_service": "service",
            "health_enabled-secrets": "enabled secrets",
            "health_public-ip": "public IP",
            "health_client-port": "client port",
            "health_stats-port": "stats port",
            "health_workers": "workers",
            "health_fake-tls-domain": "fake TLS domain",
            "export_header": "[user={user}] [id={record_id}] note={note}",
            "export_raw_secret": "  raw secret : {value}",
            "export_padded_secret": "  padded     : {value}",
            "export_fake_tls": "  fake tls   : {value}",
            "workers_positive": "WORKERS must be a non-negative integer",
            "ui_lang_invalid": "UI_LANG must be 'ru' or 'en'",
            "tls_domain_invalid": "TLS_DOMAIN is invalid",
            "record_id_positive": "record id must be positive",
            "secret_invalid_user": "secret for user '{user}' is invalid",
            "expected_integer": "{prompt}: expected an integer",
            "terminal_ui_requires_terminal": "Terminal UI requires an interactive terminal with dialog or whiptail installed",
            "already_running": "Another instance of {app} is already running",
            "legacy_import_note": "Imported from legacy secrets.txt",
            "duplicate_id": "duplicate id {record_id}",
            "duplicate_secret_user": "duplicate secret for user {user}",
            "label_invalid": "Label must match [A-Za-z0-9._@-]{1,64}",
            "port_range": "{field_name} must be in range {min_port}..{max_port}",
            "secret_exists": "This secret already exists",
            "record_not_found": "Record id {record_id} not found",
            "user_not_found": "User '{user}' not found",
            "no_matching_records_user": "No matching records for user '{user}'",
            "os_release_missing": "/etc/os-release is missing",
            "unsupported_distribution": "Unsupported distribution: {distro}. Supported: Debian, Ubuntu.",
            "binary_not_found": "Binary not found: {path}",
            "source_dir_not_found": "Source directory not found: {path}",
            "git_checkout_not_found": "Git checkout not found: {path}",
            "mtproto_binary_not_found": "The mtproto-proxy binary was not found",
            "unsupported_source_mode": "Unsupported source preparation mode: {mode}",
            "missing_proxy_secret_file": "Missing proxy secret file: {path}",
            "missing_proxy_config_file": "Missing proxy config file: {path}",
            "secrets_file_empty": "secrets file is empty: {path}",
            "interactive_terminal_required": "This manager must be started from an interactive terminal",
            "need_root_install_dialog": "Please run this script as root so dialog/whiptail can be installed",
            "unsupported_internal_command": "Unsupported internal command: {command}",
        },
    }

    def __init__(self, get_lang: Callable[[], str]) -> None:
        self._get_lang = get_lang

    def tr(self, key: str, **kwargs: object) -> str:
        lang = self._get_lang()
        mapping = self.STRINGS.get(lang) or self.STRINGS["en"]
        template = mapping.get(key, key)
        if not kwargs:
            return template
        try:
            return template.format(**kwargs)
        except (IndexError, KeyError, ValueError):
            return template


def config_ui_lang(paths: Paths) -> str:
    try:
        if not paths.config_file.exists():
            return "en"
        for raw_line in paths.config_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == "UI_LANG":
                lang = value.strip().lower()
                if lang in {"ru", "en"}:
                    return lang
    except Exception:
        pass
    return "en"


def resolve_app_error(exc: BaseException, i18n: I18N) -> str:
    if isinstance(exc, AppError):
        if exc.key:
            return i18n.tr(exc.key, **exc.kwargs)
        if exc.message:
            return exc.message
    return str(exc)


def shorten_text(text: str, max_len: int) -> str:
    if max_len <= 0:
        return ""
    if len(text) <= max_len:
        return text
    if max_len <= 3:
        return text[:max_len]
    return text[: max_len - 3] + "..."


class PlainConsole:
    def __init__(self, i18n: I18N) -> None:
        self.i18n = i18n
        self.icons = self._pick_icons()

    @staticmethod
    def _terminal_size() -> os.terminal_size:
        return shutil.get_terminal_size((100, 32))

    @staticmethod
    def _pick_icons() -> dict[str, str]:
        encoding = (sys.stdout.encoding or "").upper()
        utf8 = "UTF" in encoding
        if utf8:
            return {
                "main": "🧭",
                "setup": "🔧",
                "users": "👥",
                "service": "🚀",
                "monitor": "📈",
                "maint": "🧰",
                "danger": "⛔",
                "ok": "✅",
                "err": "❌",
                "warn": "⚠️",
                "link": "🔑",
                "lang": "🌍",
                "rotate": "🔄",
                "delete": "🗑️",
                "export": "📤",
                "status": "📋",
                "logs": "🧾",
                "info": "💡",
                "ip": "📡",
                "port": "🔌",
                "tls": "🔒",
                "worker": "⚙️",
                "source": "📦",
                "user": "👤",
                "secret": "🔐",
            }
        return {
            "main": "[#]",
            "setup": "[+]",
            "users": "[U]",
            "service": "[>]",
            "monitor": "[=]",
            "maint": "[~]",
            "danger": "[X]",
            "ok": "[v]",
            "err": "[x]",
            "warn": "[!]",
            "link": "[K]",
            "lang": "[LANG]",
            "rotate": "[R]",
            "delete": "[D]",
            "export": "[E]",
            "status": "[S]",
            "logs": "[L]",
            "info": "[i]",
            "ip": "[IP]",
            "port": "[P]",
            "tls": "[TLS]",
            "worker": "[W]",
            "source": "[SRC]",
            "user": "[USR]",
            "secret": "[KEY]",
        }

    def title(self, text: str) -> None:
        width = self._terminal_size().columns
        line_width = max(36, min(max(44, width - 2), 110))
        utf8 = "UTF" in (sys.stdout.encoding or "").upper()
        top = "╭" + ("─" * (line_width - 2)) + "╮" if utf8 else "+" + ("-" * (line_width - 2)) + "+"
        bottom = "╰" + ("─" * (line_width - 2)) + "╯" if utf8 else "+" + ("-" * (line_width - 2)) + "+"
        body = shorten_text(text, line_width - 4)
        print(f"\n{top}")
        print(("│ " if utf8 else "| ") + body.ljust(line_width - 4) + (" │" if utf8 else " |"))
        print(bottom)

    def info(self, text: str) -> None:
        print(f"{self.icons['info']} {text}")

    def ok(self, text: str) -> None:
        print(f"{self.icons['ok']} {text}")

    def warn(self, text: str) -> None:
        print(f"{self.icons['warn']} {text}")

    def error(self, text: str) -> None:
        print(f"{self.icons['err']} {text}", file=sys.stderr)

    def ask(
        self,
        prompt: str,
        default: str | None = None,
        *,
        ok_label: str | None = None,
        cancel_label: str | None = None,
    ) -> str:
        suffix = f" [{default}]" if default not in {None, ""} else ""
        button_hint = ""
        if ok_label or cancel_label:
            button_hint = f" ({ok_label or self.i18n.tr('save_action')}/{cancel_label or self.i18n.tr('back')})"
        value = input(f"{prompt}{suffix}{button_hint}: ").strip()
        if value:
            return value
        return default or ""

    def ask_int(
        self,
        prompt: str,
        default: int,
        *,
        ok_label: str | None = None,
        cancel_label: str | None = None,
    ) -> int:
        value = self.ask(prompt, str(default), ok_label=ok_label, cancel_label=cancel_label)
        if not value.isdigit():
            raise ValidationError(key="expected_integer", prompt=prompt)
        return int(value)

    def confirm(
        self,
        prompt: str,
        default: bool = False,
        *,
        yes_label: str | None = None,
        no_label: str | None = None,
    ) -> bool:
        tail = "[Y/n]" if self.i18n._get_lang() == "en" else "[Д/н]"
        if not default:
            tail = "[y/N]" if self.i18n._get_lang() == "en" else "[д/Н]"
        hint = f" ({yes_label or self.i18n.tr('yes')}/{no_label or self.i18n.tr('no')})"
        raw = input(f"{prompt}{hint} {tail}: ").strip().lower()
        if not raw:
            return default
        return raw in {"y", "yes", "д", "да"}

    def pause(self) -> None:
        input(self.i18n.tr("press_enter"))

    def text(self, title: str, text: str, *, ok_label: str | None = None) -> None:
        self.title(title)
        print(text)

    def _print_panel(self, lines: Sequence[str]) -> None:
        width = max(48, min(self._terminal_size().columns - 2, 120))
        border = "-" * width
        print(border)
        for line in lines:
            print(shorten_text(line, width))
        print(border)

    def menu(
        self,
        title: str,
        items: Sequence[tuple[str, str]],
        *,
        prompt: str | None = None,
        panel_lines: Sequence[str] | None = None,
        ok_label: str | None = None,
        cancel_label: str | None = None,
    ) -> str | None:
        self.title(title)
        if panel_lines:
            self._print_panel(panel_lines)
        for index, (_, label) in enumerate(items, start=1):
            print(f" {index}) {label}")
        print(f" 0) {cancel_label or self.i18n.tr('exit_back')}")
        while True:
            raw = input(f"{prompt or self.i18n.tr('choose')}: ").strip()
            if raw in {"", "0"}:
                return None
            if raw.isdigit():
                idx = int(raw)
                if 1 <= idx <= len(items):
                    return items[idx - 1][0]
            self.warn(f"{self.i18n.tr('error')}: {self.i18n.tr('invalid_choice')}")

    @staticmethod
    def render_table(headers: Sequence[str], rows: Sequence[Sequence[object]]) -> str:
        widths = [len(h) for h in headers]
        rendered: list[list[str]] = []
        for row in rows:
            items = [str(cell) for cell in row]
            rendered.append(items)
            for i, cell in enumerate(items):
                widths[i] = max(widths[i], len(cell))
        fmt = " | ".join("{:<" + str(w) + "}" for w in widths)
        lines = [fmt.format(*headers), "-+-".join("-" * w for w in widths)]
        for row in rendered:
            lines.append(fmt.format(*row))
        return "\n".join(lines)

    def print_table(self, headers: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
        print(self.render_table(headers, rows))


class WhiptailUI:
    MIN_BOX_HEIGHT = 12
    MIN_BOX_WIDTH = 72
    MIN_MENU_HEIGHT = 18
    MIN_MENU_WIDTH = 84
    MIN_MENU_LIST_HEIGHT = 8

    def __init__(self, i18n: I18N) -> None:
        self.i18n = i18n
        self.icons = PlainConsole._pick_icons()
        self._page_title: str | None = None
        self._page_lines: list[str] = []

    @staticmethod
    def is_available() -> bool:
        return bool(shutil.which("whiptail")) and sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM", "") not in {"", "dumb"}

    @staticmethod
    def _terminal_size() -> os.terminal_size:
        return shutil.get_terminal_size((120, 36))

    def _fit_box(self, desired_height: int, desired_width: int, *, min_height: int, min_width: int) -> tuple[int, int]:
        term = self._terminal_size()
        max_height = max(8, term.lines - 4)
        max_width = max(40, term.columns - 4)
        height = min(max(desired_height, min_height), max_height) if max_height >= min_height else max_height
        width = min(max(desired_width, min_width), max_width) if max_width >= min_width else max_width
        return height, width

    def _short_menu_label(self, label: str, width: int) -> str:
        return shorten_text(label, max(20, width - 18))

    def _run(self, *args: str) -> tuple[int, str]:
        # whiptail draws its UI directly in the terminal and returns the
        # selected value on stderr by default. If both stdout and stderr are
        # redirected to PIPE, the dialog is not rendered and the process looks
        # frozen while still waiting for user input.
        proc = subprocess.run(
            ["whiptail", *args],
            text=True,
            stdout=None,
            stderr=subprocess.PIPE,
        )
        output = (proc.stderr or "").strip()
        return proc.returncode, output

    def _show_text(self, title: str, text: str) -> None:
        lines = text.splitlines() or [""]
        longest = max((len(line) for line in lines), default=0)
        height, width = self._fit_box(len(lines) + 8, longest + 8, min_height=self.MIN_BOX_HEIGHT, min_width=self.MIN_BOX_WIDTH)
        if len(lines) <= 10 and longest <= width - 10:
            self._run("--title", title, "--msgbox", text, str(height), str(width))
            return
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            tmp_path = fh.name
        try:
            self._run("--title", title, "--scrolltext", "--textbox", tmp_path, str(height), str(width))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def _flush_page(self) -> None:
        if self._page_title is None:
            return
        body = "\n".join(self._page_lines).strip() or " "
        self._show_text(self._page_title, body)
        self._page_title = None
        self._page_lines = []

    def title(self, text: str) -> None:
        self._flush_page()
        self._page_title = text
        self._page_lines = []

    def info(self, text: str) -> None:
        if self._page_title is not None:
            self._page_lines.append(text)
        else:
            self._show_text(APP_NAME, text)

    def ok(self, text: str) -> None:
        self._flush_page()
        self._show_text(APP_NAME, text)

    def warn(self, text: str) -> None:
        self._flush_page()
        self._show_text(APP_NAME, text)

    def error(self, text: str) -> None:
        self._flush_page()
        self._show_text(APP_NAME, text)

    def ask(
        self,
        prompt: str,
        default: str | None = None,
        *,
        ok_label: str | None = None,
        cancel_label: str | None = None,
    ) -> str | None:
        self._flush_page()
        height, width = self._fit_box(12, max(self.MIN_BOX_WIDTH, len(prompt) + 12), min_height=self.MIN_BOX_HEIGHT, min_width=self.MIN_BOX_WIDTH)
        rc, out = self._run(
            "--title",
            APP_NAME,
            "--ok-button",
            ok_label or self.i18n.tr("save_action"),
            "--cancel-button",
            cancel_label or self.i18n.tr("back"),
            "--inputbox",
            prompt,
            str(height),
            str(width),
            default or "",
        )
        if rc != 0:
            return None
        return out or default or ""

    def ask_int(
        self,
        prompt: str,
        default: int,
        *,
        ok_label: str | None = None,
        cancel_label: str | None = None,
    ) -> int | None:
        value = self.ask(prompt, str(default), ok_label=ok_label, cancel_label=cancel_label)
        if value is None:
            return None
        if not value.isdigit():
            raise ValidationError(key="expected_integer", prompt=prompt)
        return int(value)

    def text(self, title: str, text: str, *, ok_label: str | None = None) -> None:
        self._flush_page()
        lines = text.splitlines() or [""]
        longest = max((len(line) for line in lines), default=0)
        height, width = self._fit_box(len(lines) + 8, longest + 8, min_height=self.MIN_BOX_HEIGHT, min_width=self.MIN_BOX_WIDTH)
        if len(lines) <= 10 and longest <= width - 10:
            self._run("--title", title, "--ok-button", ok_label or self.i18n.tr("close_action"), "--msgbox", text, str(height), str(width))
            return
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            tmp_path = fh.name
        try:
            self._run("--title", title, "--ok-button", ok_label or self.i18n.tr("close_action"), "--scrolltext", "--textbox", tmp_path, str(height), str(width))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def confirm(
        self,
        prompt: str,
        default: bool = False,
        *,
        yes_label: str | None = None,
        no_label: str | None = None,
    ) -> bool:
        self._flush_page()
        args = ["--title", APP_NAME]
        if not default:
            args.append("--defaultno")
        height, width = self._fit_box(12, max(self.MIN_BOX_WIDTH, len(prompt) + 12), min_height=self.MIN_BOX_HEIGHT, min_width=self.MIN_BOX_WIDTH)
        args.extend(
            [
                "--yes-button",
                yes_label or self.i18n.tr("continue_action"),
                "--no-button",
                no_label or self.i18n.tr("back"),
                "--yesno",
                prompt,
                str(height),
                str(width),
            ]
        )
        rc, _ = self._run(*args)
        return rc == 0

    def pause(self) -> None:
        self._flush_page()

    def menu(
        self,
        title: str,
        items: Sequence[tuple[str, str]],
        *,
        prompt: str | None = None,
        panel_lines: Sequence[str] | None = None,
        ok_label: str | None = None,
        cancel_label: str | None = None,
    ) -> str | None:
        self._flush_page()
        mapping: dict[str, str] = {}
        payload: list[str] = []
        panel_text = "\n".join(panel_lines or []).strip()
        prompt_text = panel_text if panel_text else (prompt or self.i18n.tr("choose"))
        desired_width = max(
            self.MIN_MENU_WIDTH,
            max((len(label) for _, label in items), default=0) + 18,
            max((len(line) for line in prompt_text.splitlines()), default=0) + 8,
        )
        desired_height = max(self.MIN_MENU_HEIGHT, len(prompt_text.splitlines()) + len(items) + 10)
        height, width = self._fit_box(desired_height, desired_width, min_height=self.MIN_MENU_HEIGHT, min_width=self.MIN_MENU_WIDTH)
        list_height = min(max(self.MIN_MENU_LIST_HEIGHT, len(items) + 1), max(self.MIN_MENU_LIST_HEIGHT, height - len(prompt_text.splitlines()) - 9))
        for index, (key, label) in enumerate(items, start=1):
            tag = str(index)
            mapping[tag] = key
            payload.extend([tag, self._short_menu_label(label, width)])
        rc, out = self._run(
            "--title",
            title,
            "--ok-button",
            ok_label or self.i18n.tr("select"),
            "--cancel-button",
            cancel_label or self.i18n.tr("back"),
            "--menu",
            prompt_text,
            str(height),
            str(width),
            str(list_height),
            *payload,
        )
        if rc != 0:
            return None
        return mapping.get(out)

    def print_table(self, headers: Sequence[str], rows: Sequence[Sequence[object]]) -> None:
        table = PlainConsole.render_table(headers, rows)
        if self._page_title is not None:
            self._page_lines.append(table)
            self._flush_page()
        else:
            self._show_text(APP_NAME, table)


class DialogUI(WhiptailUI):
    @staticmethod
    def is_available() -> bool:
        return bool(shutil.which("dialog")) and sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM", "") not in {"", "dumb"}

    def _run(self, *args: str) -> tuple[int, str]:
        proc = subprocess.run(
            ["dialog", "--stdout", "--colors", "--mouse", *args],
            text=True,
            stdout=subprocess.PIPE,
            stderr=None,
        )
        output = (proc.stdout or "").strip()
        return proc.returncode, output

    def ask(
        self,
        prompt: str,
        default: str | None = None,
        *,
        ok_label: str | None = None,
        cancel_label: str | None = None,
    ) -> str | None:
        self._flush_page()
        height, width = self._fit_box(12, max(self.MIN_BOX_WIDTH, len(prompt) + 12), min_height=self.MIN_BOX_HEIGHT, min_width=self.MIN_BOX_WIDTH)
        rc, out = self._run(
            "--title",
            APP_NAME,
            "--ok-label",
            ok_label or self.i18n.tr("save_action"),
            "--cancel-label",
            cancel_label or self.i18n.tr("back"),
            "--inputbox",
            prompt,
            str(height),
            str(width),
            default or "",
        )
        if rc != 0:
            return None
        return out or default or ""

    def text(self, title: str, text: str, *, ok_label: str | None = None) -> None:
        self._flush_page()
        lines = text.splitlines() or [""]
        longest = max((len(line) for line in lines), default=0)
        height, width = self._fit_box(len(lines) + 8, longest + 8, min_height=self.MIN_BOX_HEIGHT, min_width=self.MIN_BOX_WIDTH)
        if len(lines) <= 10 and longest <= width - 10:
            self._run("--title", title, "--ok-label", ok_label or self.i18n.tr("close_action"), "--msgbox", text, str(height), str(width))
            return
        with tempfile.NamedTemporaryFile("w", delete=False, encoding="utf-8") as fh:
            fh.write(text)
            tmp_path = fh.name
        try:
            self._run("--title", title, "--textbox", tmp_path, str(height), str(width))
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def confirm(
        self,
        prompt: str,
        default: bool = False,
        *,
        yes_label: str | None = None,
        no_label: str | None = None,
    ) -> bool:
        self._flush_page()
        args = ["--title", APP_NAME]
        if not default:
            args.append("--defaultno")
        height, width = self._fit_box(12, max(self.MIN_BOX_WIDTH, len(prompt) + 12), min_height=self.MIN_BOX_HEIGHT, min_width=self.MIN_BOX_WIDTH)
        args.extend([
            "--yes-label",
            yes_label or self.i18n.tr("continue_action"),
            "--no-label",
            no_label or self.i18n.tr("back"),
            "--yesno",
            prompt,
            str(height),
            str(width),
        ])
        rc, _ = self._run(*args)
        return rc == 0

    def menu(
        self,
        title: str,
        items: Sequence[tuple[str, str]],
        *,
        prompt: str | None = None,
        panel_lines: Sequence[str] | None = None,
        ok_label: str | None = None,
        cancel_label: str | None = None,
    ) -> str | None:
        self._flush_page()
        mapping: dict[str, str] = {}
        payload: list[str] = []
        panel_text = "\n".join(panel_lines or []).strip()
        prompt_text = panel_text if panel_text else (prompt or self.i18n.tr("choose"))
        desired_width = max(
            self.MIN_MENU_WIDTH,
            max((len(label) for _, label in items), default=0) + 18,
            max((len(line) for line in prompt_text.splitlines()), default=0) + 8,
        )
        desired_height = max(self.MIN_MENU_HEIGHT, len(prompt_text.splitlines()) + len(items) + 10)
        height, width = self._fit_box(desired_height, desired_width, min_height=self.MIN_MENU_HEIGHT, min_width=self.MIN_MENU_WIDTH)
        list_height = min(max(self.MIN_MENU_LIST_HEIGHT, len(items) + 1), max(self.MIN_MENU_LIST_HEIGHT, height - len(prompt_text.splitlines()) - 9))
        for index, (key, label) in enumerate(items, start=1):
            tag = str(index)
            mapping[tag] = key
            payload.extend([tag, self._short_menu_label(label, width)])
        rc, out = self._run(
            "--title",
            title,
            "--ok-label",
            ok_label or self.i18n.tr("select"),
            "--cancel-label",
            cancel_label or self.i18n.tr("back"),
            "--menu",
            prompt_text,
            str(height),
            str(width),
            str(list_height),
            *payload,
        )
        if rc != 0:
            return None
        return mapping.get(out)


def build_ui(i18n: I18N) -> PlainConsole | WhiptailUI | DialogUI:
    if DialogUI.is_available():
        return DialogUI(i18n)
    if WhiptailUI.is_available():
        return WhiptailUI(i18n)
    if sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM", "") not in {"", "dumb"}:
        return PlainConsole(i18n)
    raise AppError(key="terminal_ui_requires_terminal")


class FileLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self._fh: object | None = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        fh = open(self.path, "a+")
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError as exc:
            fh.close()
            raise AppError(key="already_running", app=APP_NAME) from exc
        self._fh = fh

    def release(self) -> None:
        fh = self._fh
        if fh is None:
            return
        try:
            fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
        finally:
            fh.close()
            self._fh = None

    def __enter__(self) -> "FileLock":
        self.acquire()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.release()


class Shell:
    def __init__(self, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def run(
        self,
        args: Sequence[str],
        *,
        check: bool = True,
        capture_output: bool = False,
        text: bool = True,
        cwd: Path | None = None,
    ) -> subprocess.CompletedProcess[str]:
        if self.dry_run:
            return subprocess.CompletedProcess(args=list(args), returncode=0, stdout="", stderr="")
        return subprocess.run(
            list(args),
            check=check,
            capture_output=capture_output,
            text=text,
            cwd=str(cwd) if cwd else None,
        )

    def check_call(self, *args: str, cwd: Path | None = None) -> None:
        self.run(args, cwd=cwd)

    def get_output(self, *args: str, cwd: Path | None = None, check: bool = True) -> str:
        result = self.run(args, check=check, capture_output=True, cwd=cwd)
        return (result.stdout or "").strip()

    def which(self, name: str) -> str | None:
        return shutil.which(name)


class Storage:
    def __init__(self, paths: Paths) -> None:
        self.paths = paths

    def ensure_dirs(self) -> None:
        self.paths.conf_dir.mkdir(parents=True, exist_ok=True)
        self.paths.data_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(self.paths.conf_dir, 0o700)

    def atomic_write_text(self, target: Path, content: str, mode: int = 0o600) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile("w", delete=False, dir=str(target.parent), encoding="utf-8") as tmp:
            tmp.write(content)
            tmp_path = Path(tmp.name)
        os.chmod(tmp_path, mode)
        tmp_path.replace(target)

    def load_settings(self) -> Settings:
        if not self.paths.config_file.exists():
            settings = Settings()
            self.save_settings(settings)
            return settings
        mapping: dict[str, str] = {}
        for raw_line in self.paths.config_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            mapping[key.strip()] = value.strip()
        settings = Settings.from_mapping(mapping)
        settings.validate()
        return settings

    def save_settings(self, settings: Settings) -> None:
        settings.validate()
        lines = [f"{key}={value}" for key, value in settings.to_mapping().items()]
        self.atomic_write_text(self.paths.config_file, "\n".join(lines) + "\n", 0o600)

    def load_inventory(self) -> list[SecretRecord]:
        if not self.paths.inventory_file.exists():
            self.atomic_write_text(
                self.paths.inventory_file,
                "# id\tenabled\tuser\tsecret\tcreated_at\tnote\n",
                0o600,
            )
            return self._load_from_legacy_secrets_if_needed([])

        records: list[SecretRecord] = []
        for raw_line in self.paths.inventory_file.read_text(encoding="utf-8").splitlines():
            if not raw_line.strip() or raw_line.lstrip().startswith("#"):
                continue
            parts = raw_line.split("\t")
            if len(parts) < 6:
                parts += [""] * (6 - len(parts))
            try:
                record = SecretRecord(
                    id=int(parts[0]),
                    enabled=parts[1].strip() == "1",
                    user=parts[2].strip(),
                    secret=parts[3].strip(),
                    created_at=parts[4].strip() or utc_now(),
                    note=parts[5].strip(),
                )
                record.validate()
            except (ValueError, ValidationError):
                continue
            records.append(record)
        return self._load_from_legacy_secrets_if_needed(records)

    def _load_from_legacy_secrets_if_needed(self, records: list[SecretRecord]) -> list[SecretRecord]:
        if records or not self.paths.secrets_file.exists() or self.paths.secrets_file.stat().st_size == 0:
            return sorted(records, key=lambda item: item.id)
        migrated: list[SecretRecord] = []
        next_id = 1
        for raw_line in self.paths.secrets_file.read_text(encoding="utf-8").splitlines():
            secret = raw_line.strip()
            if not secret:
                continue
            migrated.append(
                SecretRecord(
                    id=next_id,
                    enabled=True,
                    user=f"legacy-{next_id}",
                    secret=secret,
                    created_at=utc_now(),
                    note="legacy secrets.txt",
                )
            )
            next_id += 1
        self.save_inventory(migrated)
        return migrated

    def save_inventory(self, records: Sequence[SecretRecord]) -> None:
        lines = ["# id\tenabled\tuser\tsecret\tcreated_at\tnote"]
        seen_ids: set[int] = set()
        seen_secrets: set[str] = set()
        for record in sorted(records, key=lambda item: item.id):
            record.validate()
            if record.id in seen_ids:
                raise ValidationError(key="duplicate_id", record_id=record.id)
            if record.secret in seen_secrets:
                raise ValidationError(key="duplicate_secret_user", user=record.user)
            seen_ids.add(record.id)
            seen_secrets.add(record.secret)
            lines.append(
                "\t".join(
                    [
                        str(record.id),
                        "1" if record.enabled else "0",
                        sanitize_field(record.user),
                        sanitize_field(record.secret),
                        sanitize_field(record.created_at),
                        sanitize_field(record.note),
                    ]
                )
            )
        self.atomic_write_text(self.paths.inventory_file, "\n".join(lines) + "\n", 0o600)

    def rebuild_secrets_file(self, records: Sequence[SecretRecord]) -> None:
        enabled_secrets = [record.secret for record in records if record.enabled]
        body = "\n".join(enabled_secrets)
        if body:
            body += "\n"
        self.atomic_write_text(self.paths.secrets_file, body, 0o600)


def sanitize_field(value: str) -> str:
    return value.replace("\t", " ").replace("\n", " ").replace("\r", " ")


def validate_label(value: str) -> None:
    if not LABEL_RE.fullmatch(value):
        raise ValidationError(key="label_invalid")


def validate_port(value: int, field_name: str) -> None:
    if not (PORT_MIN <= int(value) <= PORT_MAX):
        raise ValidationError(key="port_range", field_name=field_name, min_port=PORT_MIN, max_port=PORT_MAX)


class InventoryService:
    def __init__(self, storage: Storage) -> None:
        self.storage = storage

    def list_records(self) -> list[SecretRecord]:
        return self.storage.load_inventory()

    def list_users(self) -> list[str]:
        return sorted({record.user for record in self.list_records()})

    def next_id(self, records: Sequence[SecretRecord]) -> int:
        return max((record.id for record in records), default=0) + 1

    def ensure_unique_secret(self, records: Sequence[SecretRecord], secret: str, *, ignore_id: int | None = None) -> None:
        for record in records:
            if ignore_id is not None and record.id == ignore_id:
                continue
            if record.secret == secret:
                raise ValidationError(key="secret_exists")

    def add(self, user: str, note: str = "", enabled: bool = True, secret: str | None = None) -> SecretRecord:
        validate_label(user)
        records = self.list_records()
        if secret is None:
            secret = generate_secret32()
        secret = sanitize_field(secret).strip()
        self.ensure_unique_secret(records, secret)
        record = SecretRecord(
            id=self.next_id(records),
            enabled=enabled,
            user=user,
            secret=secret,
            created_at=utc_now(),
            note=note,
        )
        updated = [*records, record]
        self.storage.save_inventory(updated)
        return record

    def update_enabled(self, record_id: int, enabled: bool) -> None:
        records = self.list_records()
        found = False
        updated: list[SecretRecord] = []
        for record in records:
            if record.id == record_id:
                updated.append(dataclasses.replace(record, enabled=enabled))
                found = True
            else:
                updated.append(record)
        if not found:
            raise AppError(key="record_not_found", record_id=record_id)
        self.storage.save_inventory(updated)

    def set_user_enabled(self, user: str, enabled: bool) -> int:
        records = self.list_records()
        changed = 0
        updated: list[SecretRecord] = []
        for record in records:
            if record.user == user:
                updated.append(dataclasses.replace(record, enabled=enabled))
                changed += 1
            else:
                updated.append(record)
        if changed == 0:
            raise AppError(key="user_not_found", user=user)
        self.storage.save_inventory(updated)
        return changed

    def rotate_one(self, record_id: int) -> SecretRecord:
        records = self.list_records()
        updated: list[SecretRecord] = []
        result: SecretRecord | None = None
        for record in records:
            if record.id == record_id:
                new_secret = generate_secret32()
                self.ensure_unique_secret(records, new_secret, ignore_id=record.id)
                replaced = dataclasses.replace(record, secret=new_secret, created_at=utc_now())
                updated.append(replaced)
                result = replaced
            else:
                updated.append(record)
        if result is None:
            raise AppError(key="record_not_found", record_id=record_id)
        self.storage.save_inventory(updated)
        return result

    def rotate_user(self, user: str, only_enabled: bool = True) -> int:
        records = self.list_records()
        updated: list[SecretRecord] = []
        changed = 0
        existing = {record.secret for record in records}
        for record in records:
            should_rotate = record.user == user and (record.enabled or not only_enabled)
            if should_rotate:
                while True:
                    candidate = generate_secret32()
                    if candidate not in existing:
                        break
                existing.discard(record.secret)
                existing.add(candidate)
                updated.append(dataclasses.replace(record, secret=candidate, created_at=utc_now()))
                changed += 1
            else:
                updated.append(record)
        if changed == 0:
            raise AppError(key="no_matching_records_user", user=user)
        self.storage.save_inventory(updated)
        return changed

    def rotate_all_enabled(self) -> int:
        records = self.list_records()
        updated: list[SecretRecord] = []
        changed = 0
        existing = {record.secret for record in records}
        for record in records:
            if record.enabled:
                while True:
                    candidate = generate_secret32()
                    if candidate not in existing:
                        break
                existing.discard(record.secret)
                existing.add(candidate)
                updated.append(dataclasses.replace(record, secret=candidate, created_at=utc_now()))
                changed += 1
            else:
                updated.append(record)
        self.storage.save_inventory(updated)
        return changed

    def delete_one(self, record_id: int) -> None:
        records = self.list_records()
        updated = [record for record in records if record.id != record_id]
        if len(updated) == len(records):
            raise AppError(key="record_not_found", record_id=record_id)
        self.storage.save_inventory(updated)

    def delete_user(self, user: str) -> int:
        records = self.list_records()
        updated = [record for record in records if record.user != user]
        removed = len(records) - len(updated)
        if removed == 0:
            raise AppError(key="user_not_found", user=user)
        self.storage.save_inventory(updated)
        return removed

    def get_user_card(self, user: str) -> dict[str, object]:
        records = [record for record in self.list_records() if record.user == user]
        if not records:
            raise AppError(key="user_not_found", user=user)
        return {
            "user": user,
            "total": len(records),
            "enabled": sum(1 for record in records if record.enabled),
            "records": records,
        }

    def rebuild_runtime(self) -> list[SecretRecord]:
        records = self.list_records()
        self.storage.rebuild_secrets_file(records)
        return records


class SystemService:
    def __init__(self, paths: Paths, shell: Shell, storage: Storage) -> None:
        self.paths = paths
        self.shell = shell
        self.storage = storage

    def require_root(self) -> None:
        if os.geteuid() != 0:
            raise AppError(key="need_root")

    def detect_platform(self) -> tuple[str, str]:
        os_release = Path("/etc/os-release")
        if not os_release.exists():
            raise AppError(key="os_release_missing")
        values: dict[str, str] = {}
        for raw_line in os_release.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            values[key] = value.strip().strip('"')
        distro = values.get("ID", "")
        version = values.get("VERSION_ID", "unknown")
        if distro not in {"debian", "ubuntu"}:
            raise AppError(key="unsupported_distribution", distro=distro or "unknown")
        return distro, version

    def apt_install(self, *packages: str) -> None:
        env = os.environ.copy()
        env["DEBIAN_FRONTEND"] = "noninteractive"
        if self.shell.dry_run:
            return
        subprocess.run(["apt-get", "update"], check=True, env=env)
        subprocess.run(["apt-get", "install", "-y", *packages], check=True, env=env)

    def install_dependencies(self) -> None:
        self.apt_install("curl", "git", "build-essential", "libssl-dev", "zlib1g-dev", "ca-certificates", "ufw", "locales", "dialog", "whiptail")

    def fix_locale(self) -> None:
        locale_defaults = "LANG=C.UTF-8\nLC_CTYPE=C.UTF-8\n"
        try:
            self.storage.atomic_write_text(Path("/etc/default/locale"), locale_defaults, 0o644)
        except Exception:
            pass
        for cmd in (("update-locale", "LANG=C.UTF-8", "LC_CTYPE=C.UTF-8"),):
            try:
                self.shell.check_call(*cmd)
            except Exception:
                pass

    def ensure_self_installed(self, current_script: Path) -> Path:
        current_script = current_script.resolve()
        target = self.paths.self_install_path
        if current_script == target and current_script.exists():
            os.chmod(current_script, 0o755)
            return current_script
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(current_script, target)
        os.chmod(target, 0o755)
        return target

    def _git_clone_or_update(self, fresh: bool = False) -> None:
        mt_dir = self.paths.mt_dir
        if fresh and mt_dir.exists():
            shutil.rmtree(mt_dir)
        if (mt_dir / ".git").exists():
            self.shell.check_call("git", "-C", str(mt_dir), "fetch", "--all", "--tags")
            self.shell.check_call("git", "-C", str(mt_dir), "pull", "--ff-only")
        elif mt_dir.exists():
            if self.paths.binary_file.exists():
                return
            self.shell.check_call("make", "clean", cwd=mt_dir)
            self.shell.check_call("make", "-j1", cwd=mt_dir)
            return
        else:
            self.shell.check_call("git", "clone", "https://github.com/TelegramMessenger/MTProxy", str(mt_dir))
        self.shell.check_call("make", "clean", cwd=mt_dir)
        self.shell.check_call("make", "-j1", cwd=mt_dir)

    def prepare_mtproxy_source(self, fresh: bool = False) -> None:
        self._git_clone_or_update(fresh=fresh)

    def mtproxy_exists(self) -> bool:
        return self.paths.mt_dir.exists()

    def mtproxy_binary_exists(self) -> bool:
        return self.paths.binary_file.exists()

    def run_make_build(self) -> None:
        self.shell.check_call("make", "clean", cwd=self.paths.mt_dir)
        self.shell.check_call("make", "-j1", cwd=self.paths.mt_dir)

    def prepare_mtproxy_source_mode(self, mode: str) -> None:
        mt_dir = self.paths.mt_dir
        if mode == "reuse":
            if not self.mtproxy_binary_exists():
                raise AppError(key="binary_not_found", path=self.paths.binary_file)
            return
        if mode == "build":
            if not mt_dir.exists():
                raise AppError(key="source_dir_not_found", path=mt_dir)
            self.run_make_build()
            return
        if mode == "update":
            if not (mt_dir / ".git").exists():
                raise AppError(key="git_checkout_not_found", path=mt_dir)
            self.shell.check_call("git", "-C", str(mt_dir), "fetch", "--all", "--tags")
            self.shell.check_call("git", "-C", str(mt_dir), "pull", "--ff-only")
            self.run_make_build()
            return
        if mode == "rebuild":
            if not mt_dir.exists():
                raise AppError(key="source_dir_not_found", path=mt_dir)
            self.run_make_build()
            return
        if mode == "fresh":
            if mt_dir.exists():
                shutil.rmtree(mt_dir)
            self.shell.check_call("git", "clone", "https://github.com/TelegramMessenger/MTProxy", str(mt_dir))
            self.run_make_build()
            return
        if mode == "reusebin":
            if not self.mtproxy_binary_exists():
                raise AppError(key="mtproto_binary_not_found")
            return
        if mode == "trybuild":
            if not mt_dir.exists():
                raise AppError(key="source_dir_not_found", path=mt_dir)
            self.run_make_build()
            return
        raise AppError(key="unsupported_source_mode", mode=mode)

    def download_file(self, url: str, target: Path, mode: int) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(url, timeout=30) as response:
            body = response.read()
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(target.parent)) as tmp:
            tmp.write(body)
            tmp_path = Path(tmp.name)
        os.chmod(tmp_path, mode)
        tmp_path.replace(target)

    def download_telegram_files(self) -> None:
        self.download_file(PROXY_SECRET_URL, self.paths.proxy_secret_file, 0o600)
        self.download_file(PROXY_CONFIG_URL, self.paths.proxy_config_file, 0o644)

    def refresh_proxy_config(self) -> bool:
        self.paths.bin_dir.mkdir(parents=True, exist_ok=True)
        with urllib.request.urlopen(PROXY_CONFIG_URL, timeout=30) as response:
            new_body = response.read()
        current_body = self.paths.proxy_config_file.read_bytes() if self.paths.proxy_config_file.exists() else b""
        if new_body == current_body:
            return False
        with tempfile.NamedTemporaryFile("wb", delete=False, dir=str(self.paths.proxy_config_file.parent)) as tmp:
            tmp.write(new_body)
            tmp_path = Path(tmp.name)
        os.chmod(tmp_path, 0o644)
        tmp_path.replace(self.paths.proxy_config_file)
        if self.is_service_installed():
            self.try_restart_service()
        return True

    def memory_mb(self) -> int:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("MemTotal:"):
                return int(line.split()[1]) // 1024
        return 0

    def swap_mb(self) -> int:
        for line in Path("/proc/meminfo").read_text(encoding="utf-8").splitlines():
            if line.startswith("SwapTotal:"):
                return int(line.split()[1]) // 1024
        return 0

    def create_swap_if_needed(self, auto_confirm: bool = False) -> bool:
        if self.swap_mb() > 0:
            return False
        if self.memory_mb() >= 1400 and not auto_confirm:
            return False
        if self.paths.swap_file.exists():
            return False
        try:
            self.shell.check_call("fallocate", "-l", "1G", str(self.paths.swap_file))
        except Exception:
            self.shell.check_call("dd", "if=/dev/zero", f"of={self.paths.swap_file}", "bs=1M", "count=1024", "status=progress")
        os.chmod(self.paths.swap_file, 0o600)
        self.shell.check_call("mkswap", str(self.paths.swap_file))
        self.shell.check_call("swapon", str(self.paths.swap_file))
        fstab = Path("/etc/fstab")
        row = "/swapfile none swap sw 0 0"
        content = fstab.read_text(encoding="utf-8") if fstab.exists() else ""
        if row not in content:
            with fstab.open("a", encoding="utf-8") as fh:
                fh.write(row + "\n")
        self.paths.swap_marker.parent.mkdir(parents=True, exist_ok=True)
        self.paths.swap_marker.touch(exist_ok=True)
        return True

    def apply_safe_optimizations(self, settings: Settings) -> Settings:
        self.create_swap_if_needed(auto_confirm=False)
        self.storage.atomic_write_text(self.paths.sysctl_file, "vm.swappiness=10\n", 0o644)
        try:
            self.shell.check_call("sysctl", "-p", str(self.paths.sysctl_file))
        except Exception:
            pass
        if self.memory_mb() < 1000 and settings.workers != 1:
            settings.workers = 1
            self.storage.save_settings(settings)
        return settings

    def write_service_units(self, script_path: Path) -> None:
        service_body = textwrap.dedent(
            f"""\
            [Unit]
            Description=MTProxy
            After=network-online.target
            Wants=network-online.target

            [Service]
            Type=simple
            WorkingDirectory={self.paths.mt_dir}
            ExecStart=/usr/bin/python3 {script_path} __run_proxy
            Restart=on-failure
            RestartSec=2
            NoNewPrivileges=true
            LimitNOFILE=65535
            OOMScoreAdjust=-250

            [Install]
            WantedBy=multi-user.target
            """
        )
        refresh_service_body = textwrap.dedent(
            f"""\
            [Unit]
            Description=Refresh MTProxy proxy-multi.conf

            [Service]
            Type=oneshot
            ExecStart=/usr/bin/python3 {script_path} __refresh_proxy_config
            """
        )
        refresh_timer_body = textwrap.dedent(
            """\
            [Unit]
            Description=Daily MTProxy config refresh

            [Timer]
            OnBootSec=10m
            OnUnitActiveSec=1d
            Persistent=true

            [Install]
            WantedBy=timers.target
            """
        )
        cleanup_service_body = textwrap.dedent(
            f"""\
            [Unit]
            Description=Daily cleanup for MTProxy Manager artifacts

            [Service]
            Type=oneshot
            ExecStart=/usr/bin/python3 {script_path} __run_cleanup
            """
        )
        cleanup_timer_body = textwrap.dedent(
            """\
            [Unit]
            Description=Daily cleanup timer for MTProxy Manager

            [Timer]
            OnBootSec=15m
            OnUnitActiveSec=1d
            Persistent=true

            [Install]
            WantedBy=timers.target
            """
        )
        self.storage.atomic_write_text(self.paths.service_file, service_body, 0o644)
        self.storage.atomic_write_text(self.paths.refresh_service_file, refresh_service_body, 0o644)
        self.storage.atomic_write_text(self.paths.refresh_timer_file, refresh_timer_body, 0o644)
        self.storage.atomic_write_text(self.paths.cleanup_service_file, cleanup_service_body, 0o644)
        self.storage.atomic_write_text(self.paths.cleanup_timer_file, cleanup_timer_body, 0o644)
        self.shell.check_call("systemctl", "daemon-reload")
        self.shell.check_call("systemctl", "enable", "--now", self.paths.refresh_timer_file.name)
        self.shell.check_call("systemctl", "enable", "--now", self.paths.cleanup_timer_file.name)

    def is_service_installed(self) -> bool:
        return self.paths.service_file.exists()

    def service_state(self) -> str:
        if not self.is_service_installed():
            return "not-installed"
        try:
            return self.shell.get_output("systemctl", "is-active", "mtproxy.service") or "unknown"
        except subprocess.CalledProcessError as exc:
            return (exc.stdout or exc.stderr or "inactive").strip() or "inactive"

    def start_service(self) -> None:
        if not self.is_service_installed():
            raise AppError(key="service_not_installed")
        self.shell.check_call("systemctl", "start", "mtproxy.service")

    def stop_service(self) -> None:
        if self.is_service_installed():
            self.shell.check_call("systemctl", "stop", "mtproxy.service")

    def restart_service(self) -> None:
        if not self.is_service_installed():
            raise AppError(key="service_not_installed")
        self.shell.check_call("systemctl", "restart", "mtproxy.service")

    def try_restart_service(self) -> None:
        if self.is_service_installed():
            self.shell.check_call("systemctl", "try-restart", "mtproxy.service")

    def show_service_status(self) -> str:
        result = self.shell.run(("systemctl", "status", "mtproxy.service", "--no-pager", "--full"), check=False, capture_output=True)
        output = (result.stdout or result.stderr or "").strip()
        return output or "mtproxy.service"

    def show_logs(self, lines: int = 100) -> str:
        result = self.shell.run(("journalctl", "-u", "mtproxy.service", "-n", str(lines), "--no-pager"), check=False, capture_output=True)
        output = (result.stdout or result.stderr or "").strip()
        return output or "mtproxy.service"

    def setup_firewall(self, new_port: int, old_port: int | None = None) -> None:
        if shutil.which("ufw") is None:
            return
        self._ufw_allow(22)
        if old_port is not None and old_port != new_port:
            self._ufw_delete(old_port)
        self._ufw_allow(new_port)

    def _ufw_allow(self, port: int) -> None:
        try:
            self.shell.check_call("ufw", "allow", f"{port}/tcp")
        except Exception:
            pass

    def _ufw_delete(self, port: int) -> None:
        try:
            proc = subprocess.Popen(["ufw", "delete", "allow", f"{port}/tcp"], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
            proc.communicate(input="y\n")
        except Exception:
            pass

    def detect_public_ip(self) -> str:
        try:
            with urllib.request.urlopen(IP_DISCOVERY_URL, timeout=8) as response:
                return response.read().decode("utf-8").strip()
        except Exception:
            pass
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                candidate = sock.getsockname()[0].strip()
                if candidate and not candidate.startswith("127."):
                    return candidate
        except Exception:
            pass
        try:
            hostname = socket.gethostname()
            candidate = socket.gethostbyname(hostname).strip()
            if candidate.startswith("127."):
                return ""
            return candidate
        except Exception:
            return ""

    def cleanup(self) -> None:
        for cmd in (
            ("journalctl", "--vacuum-time=1d", "--vacuum-size=50M"),
            ("apt-get", "clean"),
        ):
            try:
                self.shell.check_call(*cmd)
            except Exception:
                pass
        self._cleanup_dir(Path("/tmp"), prefixes=("mtproxy-manager", "mtproxy-export", "mtproxy-run"), suffixes=())
        self._cleanup_dir(self.paths.data_dir, prefixes=(), suffixes=(".tmp", ".bak", ".old"))
        self._cleanup_dir(Path("/root"), prefixes=(), suffixes=("mtproxy-links.txt.old", "mtproxy-links.txt.bak"))

    def _cleanup_dir(self, directory: Path, prefixes: Sequence[str], suffixes: Sequence[str]) -> None:
        if not directory.exists():
            return
        cutoff = dt.datetime.now() - dt.timedelta(days=1)
        for item in directory.iterdir():
            try:
                stat = item.stat()
            except OSError:
                continue
            if dt.datetime.fromtimestamp(stat.st_mtime) > cutoff:
                continue
            name = item.name
            if prefixes and any(name.startswith(prefix) for prefix in prefixes):
                if item.is_file():
                    item.unlink(missing_ok=True)
            elif suffixes and any(name.endswith(suffix) for suffix in suffixes):
                if item.is_file():
                    item.unlink(missing_ok=True)

    def factory_reset(self, delete_source: bool = True, delete_swap: bool = False) -> None:
        service_names = [
            "mtproxy.service",
            self.paths.refresh_timer_file.name,
            self.paths.cleanup_timer_file.name,
        ]
        for name in service_names:
            try:
                self.shell.check_call("systemctl", "disable", "--now", name)
            except Exception:
                pass
        try:
            settings = self.storage.load_settings()
            self._ufw_delete(settings.mt_port)
        except Exception:
            pass
        for target in (
            self.paths.service_file,
            self.paths.refresh_service_file,
            self.paths.refresh_timer_file,
            self.paths.cleanup_service_file,
            self.paths.cleanup_timer_file,
            self.paths.sysctl_file,
            self.paths.export_file,
            self.paths.config_file,
            self.paths.inventory_file,
            self.paths.secrets_file,
        ):
            if target.exists():
                target.unlink()
        for directory in (self.paths.conf_dir, self.paths.data_dir):
            if directory.exists():
                shutil.rmtree(directory)
        if delete_source and self.paths.mt_dir.exists():
            shutil.rmtree(self.paths.mt_dir)
        if delete_swap and self.paths.swap_marker.exists() and self.paths.swap_file.exists():
            try:
                self.shell.check_call("swapoff", str(self.paths.swap_file))
            except Exception:
                pass
            self.paths.swap_file.unlink(missing_ok=True)
            self.paths.swap_marker.unlink(missing_ok=True)
        try:
            self.shell.check_call("systemctl", "daemon-reload")
        except Exception:
            pass

    def health_check(self, settings: Settings, records: Sequence[SecretRecord]) -> list[tuple[str, str]]:
        enabled_count = sum(1 for record in records if record.enabled)
        checks = [
            ("binary", "ok" if self.paths.binary_file.exists() else "missing"),
            ("proxy-secret", "ok" if self.paths.proxy_secret_file.exists() else "missing"),
            ("proxy-config", "ok" if self.paths.proxy_config_file.exists() else "missing"),
            ("service", self.service_state()),
            ("enabled-secrets", str(enabled_count)),
            ("public-ip", self.detect_public_ip() or "unknown"),
            ("client-port", str(settings.mt_port)),
            ("stats-port", str(settings.stats_port)),
            ("workers", str(settings.workers)),
            ("fake-tls-domain", settings.tls_domain or "disabled"),
        ]
        return checks


class LinkExporter:
    def __init__(self, paths: Paths, i18n: I18N) -> None:
        self.paths = paths
        self.i18n = i18n

    @staticmethod
    def fake_tls_secret(base_secret: str, domain: str) -> str:
        domain_hex = domain.encode("utf-8").hex()
        return f"ee{base_secret}{domain_hex}"

    @staticmethod
    def padded_secret(base_secret: str) -> str:
        return f"dd{base_secret}"

    def key_variants(self, settings: Settings) -> list[tuple[str, str]]:
        variants = [
            ("all", self.i18n.tr("key_variant_all")),
            ("raw", self.i18n.tr("key_variant_raw")),
            ("padded", self.i18n.tr("key_variant_padded")),
        ]
        if settings.tls_domain:
            variants.append(("fake", self.i18n.tr("key_variant_fake")))
        return variants

    @staticmethod
    def _detect_public_ip() -> str:
        try:
            with urllib.request.urlopen(IP_DISCOVERY_URL, timeout=8) as response:
                return response.read().decode("utf-8").strip()
        except Exception:
            return ""

    @staticmethod
    def _tg_link(host: str, port: int, secret: str) -> str:
        return f"tg://proxy?server={host}&port={port}&secret={secret}"

    @staticmethod
    def _tme_link(host: str, port: int, secret: str) -> str:
        return f"https://t.me/proxy?server={host}&port={port}&secret={secret}"

    def export_lines(self, settings: Settings, records: Sequence[SecretRecord], user: str | None = None, variant: str = "all") -> list[str]:
        selected = [record for record in records if record.enabled and (user is None or record.user == user)]
        host = self._detect_public_ip() or "<public-ip>"
        port = settings.mt_port
        lines: list[str] = []
        for record in selected:
            lines.append(self.i18n.tr("export_header", user=record.user, record_id=record.id, note=record.note or "-"))
            lines.append(f"  endpoint   : {host}:{port}")
            lines.append(f"  server     : {host}")
            lines.append(f"  port       : {port}")
            normal = record.secret
            padded = self.padded_secret(record.secret)
            if variant in {"all", "raw"}:
                lines.append(self.i18n.tr("export_raw_secret", value=normal))
                lines.append(f"  tg raw     : {self._tg_link(host, port, normal)}")
                lines.append(f"  t.me raw   : {self._tme_link(host, port, normal)}")
            if variant in {"all", "padded"}:
                lines.append(self.i18n.tr("export_padded_secret", value=padded))
                lines.append(f"  tg padded  : {self._tg_link(host, port, padded)}")
                lines.append(f"  t.me padded: {self._tme_link(host, port, padded)}")
            if settings.tls_domain and variant in {"all", "fake"}:
                fake = self.fake_tls_secret(record.secret, settings.tls_domain)
                lines.append(self.i18n.tr("export_fake_tls", value=fake))
                lines.append(f"  fake host  : {settings.tls_domain}")
                lines.append(f"  tg fake    : {self._tg_link(host, port, fake)}")
                lines.append(f"  t.me fake  : {self._tme_link(host, port, fake)}")
            lines.append("")
        return lines

    def export_to_file(self, settings: Settings, records: Sequence[SecretRecord], user: str | None = None, variant: str = "all") -> Path:
        lines = self.export_lines(settings, records, user=user, variant=variant)
        body = "\n".join(lines).rstrip() + ("\n" if lines else "")
        self.paths.export_file.parent.mkdir(parents=True, exist_ok=True)
        self.paths.export_file.write_text(body, encoding="utf-8")
        os.chmod(self.paths.export_file, 0o600)
        return self.paths.export_file


class App:
    def __init__(self, paths: Paths, dry_run: bool = False) -> None:
        self.paths = paths
        self.shell = Shell(dry_run=dry_run)
        self.storage = Storage(paths)
        self.inventory = InventoryService(self.storage)
        self.system = SystemService(paths, self.shell, self.storage)
        self._settings = Settings()
        self.i18n = I18N(lambda: self._settings.ui_lang)
        self.console = build_ui(self.i18n)
        self.exporter = LinkExporter(self.paths, self.i18n)

    @property
    def settings(self) -> Settings:
        self._settings = self.storage.load_settings()
        return self._settings

    def _error_text(self, exc: BaseException) -> str:
        return resolve_app_error(exc, self.i18n)

    def _state_label(self, enabled: bool) -> str:
        return self.i18n.tr("state_on" if enabled else "state_off")

    def _service_state_label(self, state: str) -> str:
        key = {
            "active": "service_state_active",
            "inactive": "service_state_inactive",
            "failed": "service_state_failed",
            "activating": "service_state_activating",
            "deactivating": "service_state_deactivating",
            "not-installed": "service_state_not_installed",
            "unknown": "service_state_unknown",
        }.get(state)
        return self.i18n.tr(key) if key else state

    def _language_label(self, lang: str) -> str:
        return self.i18n.tr("lang_name_en" if lang == "en" else "lang_name_ru")

    def _health_icon_key(self, name: str) -> str:
        return {
            "binary": "source",
            "proxy-secret": "secret",
            "proxy-config": "source",
            "service": "service",
            "enabled-secrets": "secret",
            "public-ip": "ip",
            "client-port": "port",
            "stats-port": "status",
            "workers": "worker",
            "fake-tls-domain": "tls",
        }.get(name, "info")

    def _service_state_icon(self, state: str) -> str:
        return {
            "active": "ok",
            "inactive": "warn",
            "failed": "err",
            "activating": "rotate",
            "deactivating": "warn",
            "not-installed": "err",
            "unknown": "warn",
        }.get(state, "info")

    def _health_label(self, name: str) -> str:
        return self._icon_text(self._health_icon_key(name), self.i18n.tr(f"health_{name}"))

    def _health_value(self, name: str, value: str) -> str:
        if name == "service":
            return self._icon_text(self._service_state_icon(value), self._service_state_label(value))
        if value == "ok":
            return self._icon_text("ok", self.i18n.tr("value_ok"))
        if value == "missing":
            return self._icon_text("err", self.i18n.tr("value_missing"))
        if value == "unknown":
            return self._icon_text("warn", self.i18n.tr("value_unknown"))
        if value == "disabled":
            return self._icon_text("warn", self.i18n.tr("value_disabled"))
        return value

    def _menu_label(self, icon_key: str, text: str) -> str:
        return self._icon_text(icon_key, text)

    def _icon_text(self, icon_key: str, text: str) -> str:
        return f"{self.console.icons.get(icon_key, self.console.icons['info'])} {text}"

    def _screen_title(self, icon_key: str, text: str) -> str:
        return text

    @staticmethod
    def _report_text(summary_lines: Sequence[str], body: str) -> str:
        parts: list[str] = []
        if summary_lines:
            parts.append("\n".join(summary_lines).strip())
        body_text = body.strip()
        if body_text:
            parts.append(body_text)
        return "\n\n".join(part for part in parts if part)

    def _status_report_lines(self) -> list[str]:
        settings = self.settings
        records = self.inventory.list_records()
        enabled_users = len({record.user for record in records if record.enabled})
        enabled_secrets = sum(1 for record in records if record.enabled)
        return [
            self._icon_text("service", self.i18n.tr("panel_service_summary", state=self._service_state_label(self.system.service_state()))),
            self._icon_text("ip", self.i18n.tr("panel_ip_summary", ip=self.system.detect_public_ip() or self.i18n.tr("value_unknown"))),
            self._icon_text("port", self.i18n.tr("panel_ports_summary", client_port=settings.mt_port, stats_port=settings.stats_port)),
            self._icon_text("worker", self.i18n.tr("panel_workers_summary", workers=settings.workers)),
            self._icon_text("user", self.i18n.tr("welcome_enabled_users", count=enabled_users)),
            self._icon_text("secret", self.i18n.tr("welcome_enabled_secrets", count=enabled_secrets)),
            self._icon_text("tls", self.i18n.tr("panel_tls_summary", domain=settings.tls_domain)) if settings.tls_domain else self._icon_text("tls", self.i18n.tr("panel_tls_off")),
        ]

    def _source_state_summary(self) -> str:
        git_state = self.i18n.tr("value_ok") if (self.paths.mt_dir / ".git").exists() else self.i18n.tr("value_missing")
        binary_state = self.i18n.tr("value_ok") if self.paths.binary_file.exists() else self.i18n.tr("value_missing")
        return self._icon_text("source", self.i18n.tr("panel_source_summary", git_state=git_state, binary_state=binary_state))

    def _active_key_preview_lines(self, settings: Settings, records: Sequence[SecretRecord], limit: int = 2) -> list[str]:
        active = [record for record in records if record.enabled]
        if not active:
            return [self._icon_text("secret", self.i18n.tr("panel_no_active_keys"))]
        lines: list[str] = []
        for record in active[:limit]:
            padded = self.exporter.padded_secret(record.secret)
            if settings.tls_domain:
                fake = self.exporter.fake_tls_secret(record.secret, settings.tls_domain)
                lines.append(
                    self._icon_text(
                        "secret",
                        self.i18n.tr(
                            "panel_key_line_fake",
                            record_id=record.id,
                            user=record.user,
                            raw=record.secret,
                            padded=padded,
                            fake=fake,
                        ),
                    )
                )
            else:
                lines.append(
                    self._icon_text(
                        "secret",
                        self.i18n.tr(
                            "panel_key_line",
                            record_id=record.id,
                            user=record.user,
                            raw=record.secret,
                            padded=padded,
                        ),
                    )
                )
        if len(active) > limit:
            lines.append(self._icon_text("info", self.i18n.tr("panel_more_keys", count=len(active) - limit)))
        return lines

    def _main_menu_panel(self) -> list[str]:
        settings = self.settings
        public_ip = self.system.detect_public_ip() or self.i18n.tr("value_unknown")
        state = self._service_state_label(self.system.service_state())
        lines = [
            self._icon_text("main", self.i18n.tr("welcome", app=APP_NAME, version=APP_VERSION)),
            self._icon_text("service", self.i18n.tr("panel_service_summary", state=state)),
            self._icon_text("ip", self.i18n.tr("panel_ip_summary", ip=public_ip)),
            self._icon_text("port", self.i18n.tr("panel_ports_summary", client_port=settings.mt_port, stats_port=settings.stats_port)),
            self._icon_text("worker", self.i18n.tr("panel_workers_summary", workers=settings.workers)),
            self._icon_text("tls", self.i18n.tr("panel_tls_summary", domain=settings.tls_domain)) if settings.tls_domain else self._icon_text("tls", self.i18n.tr("panel_tls_off")),
        ]
        return lines

    def _setup_panel(self) -> list[str]:
        return [
            self._source_state_summary(),
            self._icon_text("service", self.i18n.tr("panel_service_summary", state=self._service_state_label(self.system.service_state()))),
        ]

    def _secrets_panel(self) -> list[str]:
        settings = self.settings
        records = self.inventory.list_records()
        return [
            self._icon_text("user", self.i18n.tr("welcome_enabled_users", count=len({record.user for record in records if record.enabled}))),
            self._icon_text("secret", self.i18n.tr("welcome_enabled_secrets", count=sum(1 for record in records if record.enabled))),
            self._icon_text("status", self.i18n.tr("welcome_total_secrets", count=len(records))),
            self._icon_text("tls", self.i18n.tr("panel_tls_summary", domain=settings.tls_domain)) if settings.tls_domain else self._icon_text("tls", self.i18n.tr("panel_tls_off")),
        ]

    def _service_panel(self) -> list[str]:
        settings = self.settings
        return [
            self._icon_text("service", self.i18n.tr("panel_service_summary", state=self._service_state_label(self.system.service_state()))),
            self._icon_text("port", self.i18n.tr("panel_ports_summary", client_port=settings.mt_port, stats_port=settings.stats_port)),
            self._icon_text("ip", self.i18n.tr("panel_ip_summary", ip=self.system.detect_public_ip() or self.i18n.tr("value_unknown"))),
        ]

    def _monitor_panel(self) -> list[str]:
        return self._service_panel()

    def _maintenance_panel(self) -> list[str]:
        settings = self.settings
        return [
            self._icon_text("port", self.i18n.tr("panel_ports_summary", client_port=settings.mt_port, stats_port=settings.stats_port)),
            self._icon_text("worker", self.i18n.tr("panel_workers_summary", workers=settings.workers)),
            self._icon_text("lang", self.i18n.tr("welcome_ui_language", language=self._language_label(settings.ui_lang))),
            self._icon_text("tls", self.i18n.tr("panel_tls_summary", domain=settings.tls_domain)) if settings.tls_domain else self._icon_text("tls", self.i18n.tr("panel_tls_off")),
        ]

    def _run_menu(
        self,
        title: str | Callable[[], str],
        actions: Sequence[MenuAction] | Callable[[], Sequence[MenuAction]],
        *,
        panel_builder: Callable[[], Sequence[str]] | None = None,
        cancel_label: str | Callable[[], str] | None = None,
    ) -> object | None:
        while True:
            current_title = title() if callable(title) else title
            current_actions = list(actions() if callable(actions) else actions)
            mapping = {action.key: action for action in current_actions}
            current_cancel_label = cancel_label() if callable(cancel_label) else cancel_label
            panel_lines = list(panel_builder()) if panel_builder else None
            choice = self.console.menu(
                current_title,
                [(action.key, action.label) for action in current_actions],
                prompt=self.i18n.tr("choose"),
                panel_lines=panel_lines,
                ok_label=self.i18n.tr("select"),
                cancel_label=current_cancel_label or self.i18n.tr("back"),
            )
            if choice is None:
                return None
            action = mapping[choice]
            try:
                result = action.handler()
            except CancelledError:
                continue
            except (AppError, subprocess.CalledProcessError) as exc:
                self.console.error(self._error_text(exc))
                self.console.pause()
                continue
            if action.pause_after:
                self.console.pause()
            if result == "close":
                return result

    def _choose_key_variant(self) -> str:
        options = self.exporter.key_variants(self.settings)
        choice = self.console.menu(
            self._screen_title("secret", self.i18n.tr("choose_key_variant")),
            options,
            prompt=self.i18n.tr("choose"),
            ok_label=self.i18n.tr("select"),
            cancel_label=self.i18n.tr("back"),
        )
        if choice is None:
            raise CancelledError(key="cancelled")
        return choice

    def ensure_bootstrap(self) -> None:
        self.storage.ensure_dirs()
        self._settings = self.storage.load_settings()
        self.inventory.rebuild_runtime()

    def reconcile_runtime(self, *, restart: bool = True) -> list[SecretRecord]:
        records = self.inventory.rebuild_runtime()
        enabled_count = sum(1 for record in records if record.enabled)
        if self.system.is_service_installed():
            if enabled_count == 0:
                self.system.stop_service()
            elif restart:
                self.system.restart_service()
        return records

    def perform_install(self, current_script: Path, *, source_mode: str = "fresh") -> Path:
        self.system.require_root()
        self.system.detect_platform()
        self.storage.ensure_dirs()
        installed_script = self.system.ensure_self_installed(current_script)
        self.system.install_dependencies()
        self.system.fix_locale()
        settings = self.settings
        self.system.prepare_mtproxy_source_mode(source_mode)
        self.system.download_telegram_files()
        self.reconcile_runtime(restart=False)
        self.system.setup_firewall(settings.mt_port)
        self.system.write_service_units(installed_script)
        if sum(1 for record in self.inventory.list_records() if record.enabled) > 0:
            self.system.start_service()
        return installed_script

    def update_mtproxy(self, current_script: Path, *, source_mode: str = "update") -> Path:
        return self.perform_install(current_script, source_mode=source_mode)

    def configure(self, *, mt_port: int | None = None, stats_port: int | None = None, workers: int | None = None, tls_domain: str | None = None, ad_tag: str | None = None, ui_lang: str | None = None) -> Settings:
        old = self.settings
        new = dataclasses.replace(old)
        if mt_port is not None:
            new.mt_port = mt_port
        if stats_port is not None:
            new.stats_port = stats_port
        if workers is not None:
            new.workers = workers
        if tls_domain is not None:
            new.tls_domain = tls_domain.strip()
        if ad_tag is not None:
            new.ad_tag = ad_tag.strip()
        if ui_lang is not None:
            new.ui_lang = ui_lang.strip().lower()
        if self.system.memory_mb() < 1000 and new.workers != 1:
            new.workers = 1
        new.validate()
        self.storage.save_settings(new)
        self._settings = new
        service_settings_changed = (
            new.mt_port != old.mt_port
            or new.stats_port != old.stats_port
            or new.workers != old.workers
            or new.tls_domain != old.tls_domain
            or new.ad_tag != old.ad_tag
        )
        if new.mt_port != old.mt_port:
            self.system.setup_firewall(new.mt_port, old.mt_port)
        if service_settings_changed and self.system.is_service_installed() and sum(1 for record in self.inventory.list_records() if record.enabled) > 0:
            self.system.restart_service()
        return new

    def show_inventory(self) -> None:
        records = self.inventory.list_records()
        if not records:
            self.console.warn(self.i18n.tr("no_records"))
            return
        rows = [
            [record.id, self._state_label(record.enabled), record.user, record.masked_secret(), record.created_at, record.note or "-"]
            for record in records
        ]
        table = PlainConsole.render_table(
            [
                self.i18n.tr("table_id"),
                self.i18n.tr("table_state"),
                self.i18n.tr("table_user"),
                self.i18n.tr("table_secret"),
                self.i18n.tr("table_created_at"),
                self.i18n.tr("table_note"),
            ],
            rows,
        )
        self.console.text(
            self._screen_title("secret", self.i18n.tr("show_inventory")),
            self._report_text(self._secrets_panel(), table),
            ok_label=self.i18n.tr("close_action"),
        )

    def show_user_card(self, user: str) -> None:
        card = self.inventory.get_user_card(user)
        records: list[SecretRecord] = card["records"]  # type: ignore[assignment]
        rows = [[record.id, self._state_label(record.enabled), record.masked_secret(), record.created_at, record.note or "-"] for record in records]
        table = PlainConsole.render_table(
            [
                self.i18n.tr("table_id"),
                self.i18n.tr("table_state"),
                self.i18n.tr("table_secret"),
                self.i18n.tr("table_created_at"),
                self.i18n.tr("table_note"),
            ],
            rows,
        )
        key_lines = self.exporter.export_lines(self.settings, records, user=user, variant="all")
        body = [
            self._icon_text("user", self.i18n.tr("enabled_total", enabled=card["enabled"], total=card["total"])),
            "",
            table,
            "",
            self._icon_text("secret", self.i18n.tr("card_keys_title")),
            "",
            "\n".join(key_lines).strip() if key_lines else self.i18n.tr("keys_panel_empty"),
        ]
        self.console.text(self._screen_title("user", self.i18n.tr("user_card_title", user=user)), "\n".join(body).strip(), ok_label=self.i18n.tr("close_action"))

    def show_health(self) -> None:
        checks = self.system.health_check(self.settings, self.inventory.list_records())
        rows = [[self._health_label(name), self._health_value(name, value)] for name, value in checks]
        table = PlainConsole.render_table([self.i18n.tr("table_check"), self.i18n.tr("table_value")], rows)
        self.console.text(
            self._screen_title("status", self.i18n.tr("monitor_health")),
            self._report_text(self._status_report_lines(), table),
            ok_label=self.i18n.tr("close_action"),
        )

    def _show_keys_panel(self, user: str | None = None) -> None:
        variant = self._choose_key_variant()
        lines = self.exporter.export_lines(self.settings, self.inventory.list_records(), user=user, variant=variant)
        if not lines:
            self.console.warn(self.i18n.tr("keys_panel_empty"))
            return
        title = self.i18n.tr("keys_user_panel_title", user=user) if user else self.i18n.tr("keys_panel_title")
        self.console.text(self._screen_title("secret", title), "\n".join(lines).strip(), ok_label=self.i18n.tr("close_action"))

    def _choose_source_mode(self, *, for_update: bool) -> str | None:
        mt_dir = self.paths.mt_dir
        has_git = (mt_dir / ".git").exists()
        has_binary = self.paths.binary_file.exists()
        if has_git and has_binary:
            items = [
                ("reuse", self.i18n.tr("source_use_current")),
                ("update", self.i18n.tr("source_pull_rebuild")),
                ("rebuild", self.i18n.tr("source_rebuild")),
                ("fresh", self.i18n.tr("source_fresh_clone")),
            ]
            title = self.i18n.tr("source_management_existing")
        elif has_git and not has_binary:
            items = [
                ("build", self.i18n.tr("source_build_current")),
                ("update", self.i18n.tr("source_pull_rebuild")),
                ("fresh", self.i18n.tr("source_fresh_clone")),
            ]
            title = self.i18n.tr("source_management_repo_no_binary")
        elif mt_dir.exists() and not has_git:
            items = [
                ("reusebin", self.i18n.tr("source_use_existing_binary")),
                ("trybuild", self.i18n.tr("source_try_build_current")),
                ("fresh", self.i18n.tr("source_fresh_clone")),
            ]
            title = self.i18n.tr("source_management_no_git")
        else:
            return "fresh"

        if not for_update and has_git and has_binary:
            items = [("reuse", self.i18n.tr("source_use_current"))] + [item for item in items if item[0] != "reuse"]
        choice = self.console.menu(
            self._screen_title("source", title),
            items,
            prompt=self.i18n.tr("choose"),
            ok_label=self.i18n.tr("select"),
            cancel_label=self.i18n.tr("back"),
        )
        return choice

    def interactive_menu(self, current_script: Path) -> int:
        self.ensure_bootstrap()
        self._run_menu(
            lambda: self._screen_title("main", self.i18n.tr("main_menu")),
            lambda: [
                MenuAction("setup", self._menu_label("setup", self.i18n.tr("section_setup")), lambda: self._menu_setup(current_script), pause_after=False),
                MenuAction("secrets", self._menu_label("users", self.i18n.tr("section_secrets")), self._menu_secrets, pause_after=False),
                MenuAction("service", self._menu_label("service", self.i18n.tr("section_service")), self._menu_service, pause_after=False),
                MenuAction("monitor", self._menu_label("monitor", self.i18n.tr("section_monitoring")), self._menu_monitoring, pause_after=False),
                MenuAction("maintenance", self._menu_label("maint", self.i18n.tr("section_maintenance")), self._menu_maintenance, pause_after=False),
                MenuAction("language", self._menu_label("lang", self.i18n.tr("menu_change_language")), self._menu_language, pause_after=False),
                MenuAction("danger", self._menu_label("danger", self.i18n.tr("section_danger")), self._menu_danger, pause_after=False),
            ],
            panel_builder=self._main_menu_panel,
            cancel_label=lambda: self.i18n.tr("exit"),
        )
        return 0

    def _menu_setup(self, current_script: Path) -> None:
        self._run_menu(
            lambda: self._screen_title("setup", self.i18n.tr("section_setup")),
            lambda: [
                MenuAction("install", self._menu_label("setup", self.i18n.tr("setup_install")), lambda: self._action_install(current_script)),
                MenuAction("update", self._menu_label("rotate", self.i18n.tr("setup_update")), lambda: self._action_update(current_script)),
                MenuAction("weak", self._menu_label("maint", self.i18n.tr("setup_weak")), self._action_apply_weak),
                MenuAction("refresh", self._menu_label("status", self.i18n.tr("setup_refresh")), self._action_refresh_proxy),
            ],
            panel_builder=self._setup_panel,
        )

    def _choose_record_id(self) -> int:
        records = self.inventory.list_records()
        if not records:
            raise AppError(key="no_records")
        items = []
        for record in records:
            state = self._state_label(record.enabled)
            note = record.note or "-"
            desc = self.i18n.tr(
                "record_summary",
                state=state,
                user=record.user,
                secret=record.masked_secret(),
                created_at=record.created_at,
                note=note,
            )
            items.append((str(record.id), desc))
        choice = self.console.menu(
            self._screen_title("secret", self.i18n.tr("select_secret")),
            items,
            prompt=self.i18n.tr("choose"),
            ok_label=self.i18n.tr("select"),
            cancel_label=self.i18n.tr("back"),
        )
        if choice is None:
            raise CancelledError(key="cancelled")
        return int(choice)

    def _choose_user(self) -> str:
        users = self.inventory.list_users()
        if not users:
            raise AppError(key="no_users")
        items = []
        for user in users:
            card = self.inventory.get_user_card(user)
            items.append((user, self.i18n.tr("user_summary", enabled=card["enabled"], total=card["total"])))
        choice = self.console.menu(
            self._screen_title("user", self.i18n.tr("select_user")),
            items,
            prompt=self.i18n.tr("choose"),
            ok_label=self.i18n.tr("select"),
            cancel_label=self.i18n.tr("back"),
        )
        if choice is None:
            raise CancelledError(key="cancelled")
        return choice

    def _prompt_fake_tls_domain(self, default: str = "", *, prompt_key: str = "fake_tls_domain") -> str:
        tls_domain = self.console.ask(
            self.i18n.tr(prompt_key),
            default,
            ok_label=self.i18n.tr("save_action"),
            cancel_label=self.i18n.tr("back"),
        )
        if tls_domain is None:
            raise CancelledError(key="cancelled")
        return tls_domain

    def _action_install(self, current_script: Path) -> None:
        source_mode = self._choose_source_mode(for_update=False)
        if source_mode is None:
            raise CancelledError(key="cancelled")
        self.configure(tls_domain=self._prompt_fake_tls_domain(self.settings.tls_domain, prompt_key="setup_fake_tls_prompt"))
        script = self.perform_install(current_script, source_mode=source_mode)
        self.console.ok(self.i18n.tr("setup_installed_script", path=script))

    def _action_update(self, current_script: Path) -> None:
        source_mode = self._choose_source_mode(for_update=True)
        if source_mode is None:
            raise CancelledError(key="cancelled")
        self.update_mtproxy(current_script, source_mode=source_mode)
        self.console.ok(self.i18n.tr("setup_updated"))

    def _action_apply_weak(self) -> None:
        settings = self.system.apply_safe_optimizations(self.settings)
        self.console.ok(self.i18n.tr("setup_weak_applied", workers=settings.workers))

    def _action_refresh_proxy(self) -> None:
        changed = self.system.refresh_proxy_config()
        self.console.ok(self.i18n.tr("setup_proxy_config_updated" if changed else "setup_proxy_config_unchanged"))

    def _action_add_secret(self) -> None:
        user = self.console.ask(
            self.i18n.tr("user_label"),
            ok_label=self.i18n.tr("save_action"),
            cancel_label=self.i18n.tr("back"),
        )
        if user is None:
            raise CancelledError(key="cancelled")
        note = self.console.ask(
            self.i18n.tr("optional_note"),
            ok_label=self.i18n.tr("save_action"),
            cancel_label=self.i18n.tr("back"),
        )
        if note is None:
            raise CancelledError(key="cancelled")
        record = self.inventory.add(user=user, note=note)
        self.reconcile_runtime()
        self.console.ok(self.i18n.tr("added_secret_id", record_id=record.id))

    def _action_enable_one(self) -> None:
        self.inventory.update_enabled(self._choose_record_id(), True)
        self.reconcile_runtime()
        self.console.ok(self.i18n.tr("secret_enabled"))

    def _action_disable_one(self) -> None:
        self.inventory.update_enabled(self._choose_record_id(), False)
        self.reconcile_runtime()
        self.console.ok(self.i18n.tr("secret_disabled"))

    def _action_enable_user(self) -> None:
        changed = self.inventory.set_user_enabled(self._choose_user(), True)
        self.reconcile_runtime()
        self.console.ok(self.i18n.tr("enabled_count", count=changed))

    def _action_disable_user(self) -> None:
        changed = self.inventory.set_user_enabled(self._choose_user(), False)
        self.reconcile_runtime()
        self.console.ok(self.i18n.tr("disabled_count", count=changed))

    def _action_rotate_one(self) -> None:
        record = self.inventory.rotate_one(self._choose_record_id())
        self.reconcile_runtime()
        self.console.ok(self.i18n.tr("rotated_secret_id", record_id=record.id))

    def _action_rotate_user(self) -> None:
        changed = self.inventory.rotate_user(self._choose_user(), only_enabled=True)
        self.reconcile_runtime()
        self.console.ok(self.i18n.tr("rotated_count", count=changed))

    def _action_rotate_all(self) -> None:
        changed = self.inventory.rotate_all_enabled()
        self.reconcile_runtime()
        self.console.ok(self.i18n.tr("rotated_count", count=changed))

    def _action_delete_one(self) -> None:
        record_id = self._choose_record_id()
        if self.console.confirm(
            self.i18n.tr("delete_secret_confirm", record_id=record_id),
            default=False,
            yes_label=self.i18n.tr("delete_action"),
            no_label=self.i18n.tr("back"),
        ):
            self.inventory.delete_one(record_id)
            self.reconcile_runtime()
            self.console.ok(self.i18n.tr("secret_deleted"))

    def _action_delete_user(self) -> None:
        user = self._choose_user()
        if self.console.confirm(
            self.i18n.tr("delete_user_confirm", user=user),
            default=False,
            yes_label=self.i18n.tr("delete_action"),
            no_label=self.i18n.tr("back"),
        ):
            removed = self.inventory.delete_user(user)
            self.reconcile_runtime()
            self.console.ok(self.i18n.tr("deleted_count", count=removed))

    def _action_export_all(self) -> None:
        path = self.exporter.export_to_file(
            self.settings,
            self.inventory.list_records(),
            variant=self._choose_key_variant(),
        )
        self.console.ok(self.i18n.tr("exported_to", path=path))

    def _action_export_user(self) -> None:
        path = self.exporter.export_to_file(
            self.settings,
            self.inventory.list_records(),
            user=self._choose_user(),
            variant=self._choose_key_variant(),
        )
        self.console.ok(self.i18n.tr("exported_to", path=path))

    def _action_start_service(self) -> None:
        self.system.start_service()
        self.console.ok(self.i18n.tr("service_started"))

    def _action_stop_service(self) -> None:
        self.system.stop_service()
        self.console.ok(self.i18n.tr("service_stopped"))

    def _action_restart_service(self) -> None:
        self.system.restart_service()
        self.console.ok(self.i18n.tr("service_restarted"))

    def _action_show_service_status(self) -> None:
        if not self.system.is_service_installed():
            self.console.warn(self.i18n.tr("service_not_installed"))
            return
        self.console.text(
            self._screen_title("status", self.i18n.tr("service_status_title")),
            self._report_text(self._status_report_lines(), self.system.show_service_status()),
            ok_label=self.i18n.tr("close_action"),
        )

    def _action_show_service_logs(self) -> None:
        if not self.system.is_service_installed():
            self.console.warn(self.i18n.tr("service_not_installed"))
            return
        self.console.text(
            self._screen_title("logs", self.i18n.tr("service_logs_title")),
            self._report_text(self._status_report_lines(), self.system.show_logs()),
            ok_label=self.i18n.tr("close_action"),
        )

    def _action_edit_config(self) -> None:
        settings = self.settings
        mt_port = self.console.ask_int(
            self.i18n.tr("client_port"),
            settings.mt_port,
            ok_label=self.i18n.tr("save_action"),
            cancel_label=self.i18n.tr("back"),
        )
        if mt_port is None:
            raise CancelledError(key="cancelled")
        stats_port = self.console.ask_int(
            self.i18n.tr("stats_port"),
            settings.stats_port,
            ok_label=self.i18n.tr("save_action"),
            cancel_label=self.i18n.tr("back"),
        )
        if stats_port is None:
            raise CancelledError(key="cancelled")
        workers = self.console.ask_int(
            self.i18n.tr("worker_count"),
            settings.workers,
            ok_label=self.i18n.tr("save_action"),
            cancel_label=self.i18n.tr("back"),
        )
        if workers is None:
            raise CancelledError(key="cancelled")
        tls_domain = self._prompt_fake_tls_domain(settings.tls_domain)
        ad_tag = self.console.ask(
            self.i18n.tr("ad_tag_prompt"),
            settings.ad_tag,
            ok_label=self.i18n.tr("save_action"),
            cancel_label=self.i18n.tr("back"),
        )
        if ad_tag is None:
            raise CancelledError(key="cancelled")
        self.configure(
            mt_port=mt_port,
            stats_port=stats_port,
            workers=workers,
            tls_domain=tls_domain,
            ad_tag=ad_tag,
        )
        self.console.ok(self.i18n.tr("runtime_config_updated"))

    def _action_cleanup(self) -> None:
        self.system.cleanup()
        self.console.ok(self.i18n.tr("cleanup_finished"))

    def _action_rewrite_units(self) -> None:
        script_path = self.system.ensure_self_installed(Path(__file__).resolve())
        self.system.write_service_units(script_path)
        self.console.ok(self.i18n.tr("units_rewritten"))

    def _action_factory_reset(self) -> str | None:
        if self.console.confirm(
            self.i18n.tr("factory_reset_confirm"),
            default=False,
            yes_label=self.i18n.tr("reset_action"),
            no_label=self.i18n.tr("back"),
        ):
            self.system.factory_reset(delete_source=True, delete_swap=False)
            self.console.ok(self.i18n.tr("factory_reset_complete"))
            return "close"
        return None

    def _menu_secret_access(self) -> None:
        self._run_menu(
            lambda: self._screen_title("ok", self.i18n.tr("section_secret_access")),
            lambda: [
                MenuAction("enable-one", self._menu_label("ok", self.i18n.tr("enable_one_secret")), self._action_enable_one),
                MenuAction("disable-one", self._menu_label("warn", self.i18n.tr("disable_one_secret")), self._action_disable_one),
                MenuAction("enable-user", self._menu_label("ok", self.i18n.tr("enable_user_secrets")), self._action_enable_user),
                MenuAction("disable-user", self._menu_label("warn", self.i18n.tr("disable_user_secrets")), self._action_disable_user),
            ],
            panel_builder=self._secrets_panel,
        )

    def _menu_secret_rotate(self) -> None:
        self._run_menu(
            lambda: self._screen_title("rotate", self.i18n.tr("section_secret_rotate")),
            lambda: [
                MenuAction("rotate-one", self._menu_label("rotate", self.i18n.tr("rotate_one_secret")), self._action_rotate_one),
                MenuAction("rotate-user", self._menu_label("rotate", self.i18n.tr("rotate_user_secrets")), self._action_rotate_user),
                MenuAction("rotate-all", self._menu_label("rotate", self.i18n.tr("rotate_all_secrets")), self._action_rotate_all),
            ],
            panel_builder=self._secrets_panel,
        )

    def _menu_secret_delete(self) -> None:
        self._run_menu(
            lambda: self._screen_title("delete", self.i18n.tr("section_secret_delete")),
            lambda: [
                MenuAction("delete-one", self._menu_label("delete", self.i18n.tr("delete_one_secret")), self._action_delete_one),
                MenuAction("delete-user", self._menu_label("delete", self.i18n.tr("delete_user_secrets")), self._action_delete_user),
            ],
            panel_builder=self._secrets_panel,
        )

    def _menu_secret_view(self) -> None:
        self._run_menu(
            lambda: self._screen_title("link", self.i18n.tr("section_secret_view")),
            lambda: [
                MenuAction("keys-all", self._menu_label("link", self.i18n.tr("show_keys_panel")), self._show_keys_panel),
                MenuAction("keys-user", self._menu_label("link", self.i18n.tr("show_user_keys_panel")), lambda: self._show_keys_panel(self._choose_user())),
                MenuAction("export-all", self._menu_label("export", self.i18n.tr("export_all_links")), self._action_export_all),
                MenuAction("export-user", self._menu_label("export", self.i18n.tr("export_user_links")), self._action_export_user),
            ],
            panel_builder=self._secrets_panel,
        )

    def _menu_secret_browse(self) -> None:
        self._run_menu(
            lambda: self._screen_title("users", self.i18n.tr("section_secret_browse")),
            lambda: [
                MenuAction("inventory", self._menu_label("status", self.i18n.tr("show_inventory")), self.show_inventory),
                MenuAction("card", self._menu_label("info", self.i18n.tr("user_card")), lambda: self.show_user_card(self._choose_user())),
            ],
            panel_builder=self._secrets_panel,
        )

    def _menu_secrets(self) -> None:
        self._run_menu(
            lambda: self._screen_title("users", self.i18n.tr("section_secrets")),
            lambda: [
                MenuAction("add", self._menu_label("users", self.i18n.tr("add_secret")), self._action_add_secret),
                MenuAction("access", self._menu_label("ok", self.i18n.tr("section_secret_access")), self._menu_secret_access, pause_after=False),
                MenuAction("rotate", self._menu_label("rotate", self.i18n.tr("section_secret_rotate")), self._menu_secret_rotate, pause_after=False),
                MenuAction("delete", self._menu_label("delete", self.i18n.tr("section_secret_delete")), self._menu_secret_delete, pause_after=False),
                MenuAction("view", self._menu_label("link", self.i18n.tr("section_secret_view")), self._menu_secret_view, pause_after=False),
                MenuAction("browse", self._menu_label("info", self.i18n.tr("section_secret_browse")), self._menu_secret_browse, pause_after=False),
            ],
            panel_builder=self._secrets_panel,
        )

    def _menu_service(self) -> None:
        self._run_menu(
            lambda: self._screen_title("service", self.i18n.tr("section_service")),
            lambda: [
                MenuAction("start", self._menu_label("service", self.i18n.tr("service_start")), self._action_start_service),
                MenuAction("stop", self._menu_label("warn", self.i18n.tr("service_stop")), self._action_stop_service),
                MenuAction("restart", self._menu_label("rotate", self.i18n.tr("service_restart")), self._action_restart_service),
                MenuAction("status", self._menu_label("status", self.i18n.tr("service_status")), self._action_show_service_status),
                MenuAction("logs", self._menu_label("logs", self.i18n.tr("service_logs")), self._action_show_service_logs),
            ],
            panel_builder=self._service_panel,
        )

    def _menu_monitoring(self) -> None:
        self._run_menu(
            lambda: self._screen_title("monitor", self.i18n.tr("section_monitoring")),
            lambda: [
                MenuAction("status", self._menu_label("status", self.i18n.tr("monitor_show_status")), self._action_show_service_status),
                MenuAction("health", self._menu_label("info", self.i18n.tr("monitor_health")), self.show_health),
                MenuAction("inventory", self._menu_label("users", self.i18n.tr("monitor_inventory")), self.show_inventory),
            ],
            panel_builder=self._monitor_panel,
        )

    def _menu_maintenance(self) -> None:
        self._run_menu(
            lambda: self._screen_title("maint", self.i18n.tr("section_maintenance")),
            lambda: [
                MenuAction("config", self._menu_label("maint", self.i18n.tr("maintenance_config")), self._action_edit_config),
                MenuAction("cleanup", self._menu_label("delete", self.i18n.tr("maintenance_cleanup")), self._action_cleanup),
                MenuAction("rewrite", self._menu_label("rotate", self.i18n.tr("maintenance_rewrite")), self._action_rewrite_units),
            ],
            panel_builder=self._maintenance_panel,
        )

    def _menu_language(self) -> None:
        current = self.settings.ui_lang
        choice = self.console.menu(
            self._screen_title("lang", self.i18n.tr("choose_interface_language")),
            [("ru", self.i18n.tr("language_ru")), ("en", self.i18n.tr("language_en"))],
            prompt=self.i18n.tr("choose"),
            ok_label=self.i18n.tr("select"),
            cancel_label=self.i18n.tr("back"),
        )
        if choice is None:
            return
        if choice == current:
            return
        self.configure(ui_lang=choice)
        self.console.ok(self.i18n.tr("language_changed"))
        self.console.pause()

    def _menu_danger(self) -> None:
        self._run_menu(
            lambda: self._screen_title("danger", self.i18n.tr("section_danger")),
            lambda: [MenuAction("reset", self._menu_label("danger", self.i18n.tr("factory_reset_action")), self._action_factory_reset)],
            panel_builder=self._service_panel,
        )


def generate_secret32() -> str:
    return secrets.token_hex(16)


def run_proxy(paths: Paths) -> int:
    storage = Storage(paths)
    settings = storage.load_settings()
    if not paths.binary_file.exists():
        raise AppError(key="binary_not_found", path=paths.binary_file)
    if not paths.proxy_secret_file.exists():
        raise AppError(key="missing_proxy_secret_file", path=paths.proxy_secret_file)
    if not paths.proxy_config_file.exists():
        raise AppError(key="missing_proxy_config_file", path=paths.proxy_config_file)
    if not paths.secrets_file.exists() or paths.secrets_file.stat().st_size == 0:
        raise AppError(key="secrets_file_empty", path=paths.secrets_file)
    args = [
        str(paths.binary_file),
        "-u",
        "nobody",
        "-p",
        str(settings.stats_port),
        "-H",
        str(settings.mt_port),
    ]
    for raw_line in paths.secrets_file.read_text(encoding="utf-8").splitlines():
        secret = raw_line.strip()
        if secret:
            args.extend(["-S", secret])
    args.extend(["--aes-pwd", str(paths.proxy_secret_file), str(paths.proxy_config_file)])
    if settings.workers > 0 and not settings.tls_domain:
        args.extend(["-M", str(settings.workers)])
    if settings.tls_domain:
        args.extend(["--domain", settings.tls_domain])
    if settings.ad_tag:
        args.extend(["-P", settings.ad_tag])
    os.execv(args[0], args)
    return 0


def ensure_terminal_ui_ready() -> None:
    if not sys.stdin.isatty() or not sys.stdout.isatty() or os.environ.get("TERM", "") in {"", "dumb"}:
        raise AppError(key="interactive_terminal_required")
    if shutil.which("dialog") or shutil.which("whiptail"):
        return
    if os.geteuid() != 0:
        raise AppError(key="need_root_install_dialog")
    env = os.environ.copy()
    env["DEBIAN_FRONTEND"] = "noninteractive"
    subprocess.run(["apt-get", "update"], check=True, env=env)
    subprocess.run(["apt-get", "install", "-y", "dialog", "whiptail"], check=True, env=env)


def run_internal(command: str, paths: Paths) -> int:
    if command == "__run_proxy":
        return run_proxy(paths)
    shell = Shell()
    storage = Storage(paths)
    storage.ensure_dirs()
    system = SystemService(paths, shell, storage)
    if command == "__refresh_proxy_config":
        system.refresh_proxy_config()
        return 0
    if command == "__run_cleanup":
        system.cleanup()
        return 0
    raise AppError(key="unsupported_internal_command", command=command)


def show_startup_error(message: str, i18n: I18N) -> None:
    if shutil.which("dialog") and sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM", "") not in {"", "dumb"}:
        subprocess.run(["dialog", "--stdout", "--colors", "--mouse", "--title", f"{i18n.tr('error')} {APP_NAME}", "--msgbox", message, "18", "94"], check=False)
    elif shutil.which("whiptail") and sys.stdin.isatty() and sys.stdout.isatty() and os.environ.get("TERM", "") not in {"", "dumb"}:
        subprocess.run(["whiptail", "--title", f"{i18n.tr('error')} {APP_NAME}", "--msgbox", message, "18", "94"], check=False)
    else:
        print(f"{i18n.tr('error')}: {message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    paths = Paths()
    if argv and argv[0].startswith("__"):
        return run_internal(argv[0], paths)

    ensure_terminal_ui_ready()
    with FileLock(paths.lock_file):
        app = App(paths)
        app.system.require_root()
        app.system.detect_platform()
        app.ensure_bootstrap()
        return app.interactive_menu(Path(__file__).resolve())


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(130)
    except AppError as exc:
        paths = Paths()
        lang = config_ui_lang(paths)
        i18n = I18N(lambda: lang)
        show_startup_error(resolve_app_error(exc, i18n), i18n)
        raise SystemExit(1)
