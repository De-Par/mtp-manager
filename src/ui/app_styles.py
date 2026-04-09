"""Centralized application CSS for the main Textual app."""

from __future__ import annotations

from ui.theme import (
    ACCENT_LIGHT_BG,
    ACCENT_MID_BG,
    BUTTON_DANGER_BORDER,
    BUTTON_DANGER_HOVER_BG,
    BUTTON_DANGER_HOVER_BORDER,
    BUTTON_DANGER_TEXT,
    BUTTON_DEFAULT_HOVER_BG,
    BUTTON_FLAT_BORDER,
    BUTTON_FLAT_TEXT,
    BUTTON_FOCUS_BORDER,
    BUTTON_HEIGHT,
    BUTTON_SUCCESS_HOVER_BG,
    BUTTON_WARNING_BG,
    BUTTON_WARNING_BORDER,
    BUTTON_WARNING_FOCUS_BORDER,
    BUTTON_WARNING_FOCUS_TEXT,
    BUTTON_WARNING_HOVER_BG,
    BUTTON_WARNING_HOVER_BORDER,
    BUTTON_WARNING_TEXT,
    CONTENT_LIGHT_BG,
    CONTENT_SUBTLE_TEXT,
    FOCUS_INK,
    LIST_ROW_EVEN_BG,
    LIST_ROW_ODD_BG,
    SCROLLBAR_SIZE,
    SECTION_HOVER_BG,
    SLATE_BG,
    SLATE_FG,
    SPLIT_HANDLE_COLOR,
    SPLIT_HANDLE_FOCUS_BG,
    SPLIT_HANDLE_FOCUS_COLOR,
    SPLIT_HANDLE_HOVER_BG,
    SPLIT_HANDLE_HOVER_COLOR,
    THEME_CSS_TOKENS,
    TOAST_ERROR_BORDER,
    TOAST_INFO_BORDER,
    TOAST_WARNING_BORDER,
    TOPBAR_CLOSE_WIDTH,
    TOPBAR_HEIGHT,
    UI_BORDER_ACTIVE,
)

CSS_REPLACEMENTS = {
    "{TOPBAR_HEIGHT}": str(TOPBAR_HEIGHT),
    "{TOPBAR_CLOSE_WIDTH}": str(TOPBAR_CLOSE_WIDTH),
    "{SPLIT_HANDLE_COLOR}": str(SPLIT_HANDLE_COLOR),
    "{SPLIT_HANDLE_HOVER_COLOR}": str(SPLIT_HANDLE_HOVER_COLOR),
    "{SPLIT_HANDLE_HOVER_BG}": str(SPLIT_HANDLE_HOVER_BG),
    "{SPLIT_HANDLE_FOCUS_COLOR}": str(SPLIT_HANDLE_FOCUS_COLOR),
    "{SPLIT_HANDLE_FOCUS_BG}": str(SPLIT_HANDLE_FOCUS_BG),
    "{SCROLLBAR_SIZE}": str(SCROLLBAR_SIZE),
    "{CONTENT_SUBTLE_TEXT}": str(CONTENT_SUBTLE_TEXT),
    "{ACCENT_LIGHT_BG}": str(ACCENT_LIGHT_BG),
    "{ACCENT_MID_BG}": str(ACCENT_MID_BG),
    "{LIST_ROW_ODD_BG}": str(LIST_ROW_ODD_BG),
    "{LIST_ROW_EVEN_BG}": str(LIST_ROW_EVEN_BG),
    "{CONTENT_LIGHT_BG}": str(CONTENT_LIGHT_BG),
    "{SECTION_HOVER_BG}": str(SECTION_HOVER_BG),
    "{SLATE_BG}": str(SLATE_BG),
    "{SLATE_FG}": str(SLATE_FG),
    "{TOAST_INFO_BORDER}": str(TOAST_INFO_BORDER),
    "{TOAST_WARNING_BORDER}": str(TOAST_WARNING_BORDER),
    "{TOAST_ERROR_BORDER}": str(TOAST_ERROR_BORDER),
    "{BUTTON_HEIGHT}": str(BUTTON_HEIGHT),
    "{BUTTON_DEFAULT_HOVER_BG}": str(BUTTON_DEFAULT_HOVER_BG),
    "{BUTTON_FOCUS_BORDER}": str(BUTTON_FOCUS_BORDER),
    "{BUTTON_SUCCESS_HOVER_BG}": str(BUTTON_SUCCESS_HOVER_BG),
    "{BUTTON_DANGER_TEXT}": str(BUTTON_DANGER_TEXT),
    "{BUTTON_DANGER_BORDER}": str(BUTTON_DANGER_BORDER),
    "{BUTTON_DANGER_HOVER_BG}": str(BUTTON_DANGER_HOVER_BG),
    "{BUTTON_DANGER_HOVER_BORDER}": str(BUTTON_DANGER_HOVER_BORDER),
    "{BUTTON_WARNING_BG}": str(BUTTON_WARNING_BG),
    "{BUTTON_WARNING_TEXT}": str(BUTTON_WARNING_TEXT),
    "{BUTTON_WARNING_BORDER}": str(BUTTON_WARNING_BORDER),
    "{BUTTON_WARNING_HOVER_BG}": str(BUTTON_WARNING_HOVER_BG),
    "{BUTTON_WARNING_HOVER_BORDER}": str(BUTTON_WARNING_HOVER_BORDER),
    "{BUTTON_WARNING_FOCUS_TEXT}": str(BUTTON_WARNING_FOCUS_TEXT),
    "{BUTTON_WARNING_FOCUS_BORDER}": str(BUTTON_WARNING_FOCUS_BORDER),
    "{BUTTON_FLAT_TEXT}": str(BUTTON_FLAT_TEXT),
    "{BUTTON_FLAT_BORDER}": str(BUTTON_FLAT_BORDER),
    "{FOCUS_INK}": str(FOCUS_INK),
    "{UI_BORDER_ACTIVE}": str(UI_BORDER_ACTIVE),
}


def _css(template: str) -> str:
    for key, value in CSS_REPLACEMENTS.items():
        template = template.replace(key, value)
    return template


APP_CSS = _css(
    THEME_CSS_TOKENS
    + """

Screen {
    background: $app-surface;
    color: $ui-ink;
}

#topbar {
    dock: top;
    height: {TOPBAR_HEIGHT};
    layout: horizontal;
    align: center middle;
    background: $app-header-bg;
    color: $app-header-fg;
    padding: 0 0 0 3;
    text-style: bold;
}

#topbar-title {
    width: 1fr;
    height: 1fr;
    content-align: center middle;
    color: $app-header-fg;
    text-style: bold;
}

#topbar-close {
    dock: right;
    width: {TOPBAR_CLOSE_WIDTH};
    min-width: {TOPBAR_CLOSE_WIDTH};
    height: {TOPBAR_HEIGHT};
    align: center middle;
    background: $app-header-bg;
    color: $app-header-fg;
    border: none;
    padding: 0;
    margin: 0;
    text-style: bold;
}

#topbar-close-glyph {
    width: 1fr;
    height: 1fr;
    content-align: center middle;
    text-align: center;
    color: $app-header-fg;
    background: transparent;
    text-style: bold;
}

#topbar-close:hover {
    background: $app-header-bg-hover;
    color: white;
    border: none;
}

#topbar-close:focus {
    background: $app-header-bg-hover;
    color: white;
    border: none;
}

#root {
    layout: vertical;
    height: 1fr;
    padding: 1;
    background: $app-surface;
}

#workspace-row {
    layout: horizontal;
    height: 1fr;
    align: left top;
}

#root.compact #workspace-row {
    layout: vertical;
    height: auto;
}

#root.sections-icons #sections-list > ListItem {
    padding: 0 1;
}

#sections-panel {
    width: 1fr;
    min-width: 20;
    background: $app-surface;
    height: 1fr;
    margin-bottom: 0;
}

#overview-panel,
#activity-panel,
#explorer-panel,
#content-column,
#actions-panel {
    width: 1fr;
    background: $app-surface;
}

#content-column {
    layout: vertical;
    height: 1fr;
    margin-bottom: 0;
}

#content-column.users-only #explorer-panel {
    height: 1fr;
    margin-bottom: 0;
    padding: 1 1 0 1;
}

#content-column.users-only #overview-panel {
    display: none;
}

#workspace-row > #sections-panel,
#workspace-row > #content-column {
    height: 1fr;
    margin-bottom: 0;
}

#top-split-handle {
    width: 1;
    min-width: 1;
    height: 1fr;
    content-align: center middle;
    color: {SPLIT_HANDLE_COLOR};
    background: transparent;
    text-style: bold;
    margin: 0;
}

#top-split-handle:hover {
    color: {SPLIT_HANDLE_HOVER_COLOR};
    background: {SPLIT_HANDLE_HOVER_BG};
}

#top-split-handle:focus {
    color: {SPLIT_HANDLE_FOCUS_COLOR};
    background: {SPLIT_HANDLE_FOCUS_BG};
}

.panel {
    background: $app-surface;
    border: round $ui-border;
    padding: 1;
    margin-bottom: 1;
    height: auto;
}

#overview-panel {
    margin-bottom: 0;
}

.panel-title {
    width: 1fr;
    content-align: center middle;
    color: $ui-accent-ink;
    text-style: bold;
    margin: 0 0 1 0;
}

.content-scroll {
    height: 1fr;
    background: $app-surface;
}

#overview-scroll.dashboard-card-scroll {
    content-align: center top;
}

.content-text {
    color: $ui-ink;
    padding: 0 0 1 0;
    background: $app-surface;
}

#overview-content.dashboard-card {
    width: 1fr;
    content-align: center top;
    text-align: center;
}

.content-scroll,
ListView,
HorizontalScroll {
    scrollbar-color: $scrollbar-color;
    scrollbar-color-hover: $scrollbar-color-hover;
    scrollbar-color-active: $scrollbar-color-active;
    scrollbar-background: $scrollbar-background;
    scrollbar-background-hover: $scrollbar-background-hover;
    scrollbar-background-active: $scrollbar-background-active;
    scrollbar-size-vertical: {SCROLLBAR_SIZE};
    scrollbar-size-horizontal: {SCROLLBAR_SIZE};
}

.field-label {
    text-style: bold;
    color: {CONTENT_SUBTLE_TEXT};
}

ListView {
    background: transparent;
    color: $ui-ink;
    border: none;
    height: 1fr;
}

ListItem {
    background: white;
    color: $ui-ink;
    padding: 0 1;
    margin-bottom: 1;
}

ListItem.-highlight {
    background: {ACCENT_LIGHT_BG};
    color: $ui-ink;
    text-style: bold;
}

ListView:focus > ListItem.-highlight {
    background: {ACCENT_MID_BG};
    color: white;
}

.list-label {
    width: 1fr;
}

#sections-list {
    width: 1fr;
    height: 1fr;
    padding: 0;
    background: $app-surface;
}

#overview-scroll,
#activity-scroll,
#explorer-lists,
#users-subpanel,
#secrets-subpanel,
#users-list,
#secrets-list {
    background: $app-surface;
}

#sections-list .list-label {
    content-align: center middle;
    text-align: center;
    text-style: bold;
    height: 1;
}

#sections-list .section-item-row {
    width: 1fr;
    height: auto;
    align: center middle;
}

#sections-list .section-item-row.icon-only {
    width: 1fr;
}

#sections-list .section-item-icon {
    width: 3;
    min-width: 3;
    height: auto;
    content-align: center middle;
    text-align: center;
    text-style: bold;
}

#sections-list .section-item-label {
    width: auto;
    height: auto;
    content-align: left middle;
    text-align: left;
    text-style: bold;
}

#sections-list > ListItem {
    width: 1fr;
    background: $app-surface;
    border: round $ui-border;
    color: $ui-ink;
    padding: 0 2;
    margin: 0 1 0 1;
    min-height: 2;
}

#users-list {
    padding: 0 2;
    background: $app-surface;
}

#users-table {
    width: 1fr;
    height: 1fr;
    min-height: 0;
    background: $app-surface;
    color: $ui-ink;
    padding: 0;
    margin: 0;
    scrollbar-color: $scrollbar-color;
    scrollbar-color-hover: $scrollbar-color-hover;
    scrollbar-color-active: $scrollbar-color-active;
    scrollbar-background: $scrollbar-background;
    scrollbar-background-hover: $scrollbar-background-hover;
    scrollbar-background-active: $scrollbar-background-active;
    scrollbar-size-vertical: {SCROLLBAR_SIZE};
    scrollbar-size-horizontal: {SCROLLBAR_SIZE};
}

#users-empty-state {
    width: 1fr;
    height: 1fr;
    padding: 0 4;
    color: {CONTENT_SUBTLE_TEXT};
    content-align: center middle;
    text-align: center;
}

#users-table > .datatable--header {
    background: $app-header-bg;
    color: $app-header-fg;
    text-style: bold;
}

#users-table > .datatable--header-hover {
    background: $app-header-bg-hover;
    color: $app-header-fg;
    text-style: bold;
}

#users-table > .datatable--header-cursor {
    background: $app-header-bg-hover;
    color: $app-header-fg;
    text-style: bold;
}

#users-table > .datatable--cursor {
    background: {ACCENT_LIGHT_BG};
    color: $ui-ink;
    text-style: bold;
}

#users-table.no-selection > .datatable--cursor {
    background: transparent;
    color: $ui-ink;
    text-style: none;
}

#users-table > .datatable--hover {
    background: transparent;
}

#users-table > .datatable--odd-row {
    background: {LIST_ROW_ODD_BG};
}

#users-table > .datatable--even-row {
    background: {LIST_ROW_EVEN_BG};
}

#users-table > .datatable--fixed {
    background: $app-header-bg;
    color: $app-header-fg;
    text-style: bold;
}

#users-table > .datatable--cell {
    color: $ui-ink;
}

#users-list .list-label {
    content-align: left middle;
    text-align: left;
    text-style: none;
}

#users-list > ListItem {
    background: transparent;
    border: none;
    color: $ui-ink;
    padding: 0 1;
    margin-bottom: 0;
    min-height: 1;
}

#users-list > ListItem:hover {
    background: {CONTENT_LIGHT_BG};
    border: none;
    color: $ui-ink;
}

#sections-list > ListItem:hover {
    background: {SECTION_HOVER_BG};
    border: round $ui-border-active;
    color: $ui-ink;
}

#sections-list > ListItem.-highlight {
    background: $app-surface;
    border: round $ui-border;
    color: $ui-ink;
}

#sections-list:focus > ListItem.-highlight {
    background: $app-surface;
    border: round $ui-border;
    color: $ui-ink;
}

#sections-list > ListItem.-highlight:hover,
#sections-list:focus > ListItem.-highlight:hover {
    background: {SECTION_HOVER_BG};
    border: round $ui-border-active;
    color: $ui-ink;
}

#users-list > ListItem.-highlight {
    background: transparent;
    border: none;
    color: $ui-ink;
}

#users-list:focus > ListItem.-highlight {
    background: transparent;
    border: none;
    color: $ui-ink;
}

#users-list > ListItem.-highlight:hover,
#users-list:focus > ListItem.-highlight:hover {
    background: {CONTENT_LIGHT_BG};
    border: none;
    color: $ui-ink;
}

#explorer-lists {
    height: 1fr;
}

#users-subpanel,
#secrets-subpanel {
    width: 1fr;
    height: 1fr;
}

#users-subpanel {
    margin: 0;
    padding: 0;
}

.subpanel-title {
    width: 1fr;
    content-align: center middle;
    color: $ui-accent-ink;
    text-style: bold;
    margin-bottom: 1;
}

#users-title {
    content-align: left middle;
    color: $ui-ink;
    text-style: bold;
    margin: 0 1 1 3;
}

#activity-panel {
    display: none;
}

#actions-panel {
    height: auto;
    min-height: 3;
    background: transparent;
    border: none;
    padding: 1 0;
    margin: 0;
}

#busy-overlay {
    layer: overlay;
    width: 1fr;
    height: 1fr;
    display: none;
    align: center middle;
    background: transparent;
}

#busy-dialog {
    width: 32;
    height: auto;
    background: {SLATE_BG};
    color: {SLATE_FG};
    border: none;
    padding: 1 3;
    offset: 0 -1;
}

#busy-label {
    width: 1fr;
    color: {SLATE_FG};
    text-style: none;
    content-align: center middle;
    margin-bottom: 1;
}

#busy-progress {
    width: 1fr;
    color: {SLATE_FG};
    content-align: center middle;
}

#actions-scroll {
    height: auto;
    margin: 0;
}

#actions-container {
    width: 1fr;
    height: auto;
    align: center middle;
    padding: 0;
}

ToastRack {
    margin-bottom: 1;
}

Toast {
    width: 76;
    max-width: 72%;
    padding: 1 2;
    background: {SLATE_BG};
    color: {SLATE_FG};
}

Toast.-information {
    border-left: outer {TOAST_INFO_BORDER};
}

Toast.-warning {
    border-left: outer {TOAST_WARNING_BORDER};
}

Toast.-error {
    border-left: outer {TOAST_ERROR_BORDER};
}

.action-button {
    width: auto;
    min-width: 11;
    margin-right: 1;
}

Button {
    min-width: 9;
    height: {BUTTON_HEIGHT};
    padding: 0 2;
    content-align: center middle;
    text-style: bold;
}

Button.-style-default {
    background: white;
    color: $ui-ink;
    border: round $ui-border-active;
    text-style: bold;
}

Button.-style-default:hover {
    background: {BUTTON_DEFAULT_HOVER_BG};
}

Button.-style-default:focus {
    background: white;
    color: $ui-ink;
    border: round {BUTTON_FOCUS_BORDER};
}

Button.-style-default:hover:focus {
    background: {BUTTON_DEFAULT_HOVER_BG};
    color: $ui-ink;
    border: round {BUTTON_FOCUS_BORDER};
}

Button.-success {
    background: white;
    color: $ui-ink;
    border: round $ui-border-active;
    text-style: bold;
}

Button.-success:hover {
    background: {BUTTON_SUCCESS_HOVER_BG};
    color: $ui-ink;
    border: round {BUTTON_FOCUS_BORDER};
}

Button.-success:focus {
    background: {BUTTON_DEFAULT_HOVER_BG};
    color: $ui-ink;
    border: round {BUTTON_FOCUS_BORDER};
}

Button.-success:hover:focus {
    background: {BUTTON_SUCCESS_HOVER_BG};
    color: $ui-ink;
    border: round {BUTTON_FOCUS_BORDER};
}

Button.-error {
    background: white;
    color: {BUTTON_DANGER_TEXT};
    border: round {BUTTON_DANGER_BORDER};
    text-style: bold;
}

Button.-error:hover {
    background: {BUTTON_DANGER_HOVER_BG};
    color: {BUTTON_DANGER_TEXT};
    border: round {BUTTON_DANGER_HOVER_BORDER};
}

Button.-error:focus {
    background: {BUTTON_DANGER_HOVER_BG};
    color: {BUTTON_DANGER_TEXT};
    border: round {BUTTON_DANGER_HOVER_BORDER};
}

Button.-error:hover:focus {
    background: {BUTTON_DANGER_HOVER_BG};
    color: {BUTTON_DANGER_TEXT};
    border: round {BUTTON_DANGER_HOVER_BORDER};
}

Button.-warning {
    background: {BUTTON_WARNING_BG};
    color: {BUTTON_WARNING_TEXT};
    border: round {BUTTON_WARNING_BORDER};
    text-style: bold;
}

Button.-warning:hover {
    background: {BUTTON_WARNING_HOVER_BG};
    color: {BUTTON_WARNING_TEXT};
    border: round {BUTTON_WARNING_HOVER_BORDER};
}

Button.-warning:focus {
    background: {BUTTON_WARNING_BORDER};
    color: {BUTTON_WARNING_FOCUS_TEXT};
    border: round {BUTTON_WARNING_FOCUS_BORDER};
}

Button.-warning:hover:focus {
    background: {BUTTON_WARNING_HOVER_BG};
    color: {BUTTON_WARNING_TEXT};
    border: round {BUTTON_WARNING_HOVER_BORDER};
}

Button.-flat {
    background: white;
    color: {BUTTON_FLAT_TEXT};
    border: round {BUTTON_FLAT_BORDER};
    text-style: bold;
}

Button.-flat:hover {
    background: {BUTTON_DEFAULT_HOVER_BG};
}

Button.-flat:focus {
    background: white;
    color: {FOCUS_INK};
    border: round {UI_BORDER_ACTIVE};
}

#explorer-panel {
    display: none;
}
"""
)
