# メイン画面のレイアウト定義
# 左ペイン（フィルター）・中央ペイン（スニペット一覧）・右ペイン（コード詳細）の
# 3ペイン構成を構築する

import json
from dataclasses import dataclass, field

from nicegui import ui

# NiceGUI の ui.code() が生成するコードブロックのスクロール制御 CSS
# 長いコードが右ペインからはみ出さないようにコードブロック内でスクロールさせる
_DETAIL_CSS = """
/* 右ペイン内のコードブロック：コード内容が長ければ横スクロール */
.code-detail-pane pre {
    overflow-x: auto !important;
    white-space: pre !important;
    margin: 0;
}
.code-detail-pane .nicegui-code {
    overflow-x: auto !important;
    width: 100% !important;
}
"""

from app.crud import (
    delete_snippet,
    duplicate_snippet,
    get_all_languages,
    get_all_tags,
    get_snippet,
    get_snippets,
    toggle_pin,
)
from app.database import get_session

# 言語名から highlight.js の言語識別子へのマッピング
# ui.code() のシンタックスハイライトに使用する
_HIGHLIGHT_MAP: dict[str, str] = {
    "SQL": "sql",
    "C#": "csharp",
    "VBA": "vbscript",
    "Python": "python",
    "JavaScript": "javascript",
    "PowerShell": "powershell",
    "その他": "plaintext",
}

# ソートドロップダウンの選択肢（表示名）
_SORT_OPTIONS: dict[str, str] = {
    "updated_desc": "更新日時（新しい順）",
    "updated_asc":  "更新日時（古い順）",
    "created_desc": "作成日時（新しい順）",
    "created_asc":  "作成日時（古い順）",
    "title_asc":    "タイトル（昇順）",
    "title_desc":   "タイトル（降順）",
}


@dataclass
class _State:
    """画面全体のフィルター・選択状態を保持するクラス。
    ページ単位でインスタンスを生成し、各コールバックが共有して読み書きする。"""
    search: str = ""                              # 検索キーワード
    language_id: int | None = None               # 選択中の言語 ID（None=すべて）
    tag_ids: list[int] = field(default_factory=list)  # 選択中のタグ ID リスト
    tag_mode: str = "or"                         # タグ絞り込み条件（"or" or "and"）
    sort_by: str = "updated_desc"                # ソートキー
    pinned_only: bool = False                    # ピン留めのみ表示フラグ
    selected_id: int | None = None              # 右ペインに表示中のスニペット ID
    lang_collapsed: bool = False                 # 言語セクションの折りたたみ状態
    tag_collapsed: bool = False                  # タグセクションの折りたたみ状態


def _filter_item(label: str, active: bool, on_click) -> None:
    """左ペイン用のフィルターボタンを描画する。選択中は青くハイライトする。"""
    cls = "w-full justify-start text-sm"
    color = "primary" if active else "grey-8"
    ui.button(label, on_click=on_click).classes(cls).props(
        f"flat no-caps color={color}"
    )


def create_layout() -> None:
    """3ペインのメインレイアウトを構築してページに描画する"""
    ui.add_css(_DETAIL_CSS)
    s = _State()  # このページセッション専用の状態オブジェクト

    # ── 更新可能なコンポーネント ─────────────────────────────────────────────
    # @ui.refreshable を付けると、refresh() を呼んだときにその関数だけ再描画される

    @ui.refreshable
    def filter_panel() -> None:
        """左ペインのフィルターパネルを描画する（ピン留め / 言語 / タグ）"""
        session = get_session()
        try:
            languages = get_all_languages(session)
            tags = get_all_tags(session)
        finally:
            session.close()

        # ── ピン留めフィルターボタン ──
        with ui.row().classes("items-center px-2 pt-2 pb-1"):
            ui.button(
                "📌 ピン留めのみ",
                on_click=lambda: _on_pinned_only(),
            ).classes("w-full justify-start text-sm").props(
                f"{'unelevated' if s.pinned_only else 'flat'} no-caps "
                f"color={'primary' if s.pinned_only else 'grey-8'}"
            )

        ui.separator().classes("my-1")

        # ── 言語セクション（ヘッダークリックで折りたたみ）──
        with ui.row().classes("items-center px-3 pt-2 pb-1 cursor-pointer").on(
            "click", lambda: _on_toggle_lang()
        ):
            ui.label("言語").classes(
                "text-xs font-bold text-gray-500 uppercase tracking-wide flex-1"
            )
            # 折りたたみ状態に応じてアイコンを切り替える
            ui.icon(
                "expand_less" if not s.lang_collapsed else "expand_more"
            ).classes("text-gray-400 text-base")

        if not s.lang_collapsed:
            with ui.column().classes("w-full gap-0 px-1"):
                _filter_item("すべて", s.language_id is None, lambda: _on_lang(None))
                for lang in languages:
                    _filter_item(
                        lang.name,
                        s.language_id == lang.id,
                        lambda lid=lang.id: _on_lang(lid),
                    )

        # ── タグセクション（ヘッダークリックで折りたたみ / AND・OR 切替）──
        with ui.row().classes("items-center px-3 pt-4 pb-1 gap-1"):
            with ui.row().classes("items-center flex-1 cursor-pointer gap-1").on(
                "click", lambda: _on_toggle_tag()
            ):
                ui.label("タグ").classes(
                    "text-xs font-bold text-gray-500 uppercase tracking-wide"
                )
                ui.icon(
                    "expand_less" if not s.tag_collapsed else "expand_more"
                ).classes("text-gray-400 text-base")
            if tags and not s.tag_collapsed:
                # AND / OR 切替ボタン
                for mode, label in [("or", "OR"), ("and", "AND")]:
                    active = s.tag_mode == mode
                    ui.button(label, on_click=lambda m=mode: _on_tag_mode(m)).classes(
                        "text-xs"
                    ).props(
                        f"{'unelevated' if active else 'outline'} dense no-caps "
                        f"color={'primary' if active else 'grey-6'} padding='1px 6px'"
                    )
                # タグ選択中のみリセットボタン（×）を表示する
                if s.tag_ids:
                    ui.button(
                        icon="close", on_click=_on_tag_reset
                    ).props("flat dense round color=grey-6 size=xs")

        if not s.tag_collapsed:
            with ui.column().classes("w-full gap-0 px-1"):
                if not tags:
                    ui.label("タグなし").classes("text-xs text-gray-400 px-2 py-1")
                for tag in tags:
                    # 選択中のタグ ID リストに含まれているかでハイライトを判定する
                    _filter_item(
                        f"# {tag.name}",
                        tag.id in s.tag_ids,
                        lambda tid=tag.id: _on_tag(tid),
                    )

    @ui.refreshable
    def snippet_list() -> None:
        """中央ペインのスニペット一覧カードを描画する"""
        session = get_session()
        try:
            snippets = get_snippets(session, s.search, s.language_id, s.tag_ids, s.tag_mode, s.sort_by, s.pinned_only)
        finally:
            session.close()

        if not snippets:
            with ui.column().classes("items-center p-8 gap-2 w-full"):
                ui.icon("search_off").classes("text-5xl text-gray-300")
                ui.label("見つかりません").classes("text-gray-400 text-sm")
            return

        for sn in snippets:
            selected = s.selected_id == sn.id
            # 選択中のカードは左端に青いボーダーを表示する
            border = "border-l-4 border-blue-500 bg-blue-50" if selected else ""
            with ui.card().tight().classes(
                f"w-full cursor-pointer hover:bg-gray-50 transition-colors {border}"
            ).on("click", lambda sid=sn.id: _on_select(sid)):
                with ui.column().classes("p-3 gap-1 w-full"):
                    with ui.row().classes("items-start gap-1 w-full"):
                        ui.label(sn.title).classes("font-semibold text-sm leading-tight flex-1")
                        # ピン留め中のスニペットはピンアイコンを表示する
                        if sn.is_pinned:
                            ui.icon("push_pin").classes("text-blue-500 text-base")
                    with ui.row().classes("gap-1 flex-wrap"):
                        if sn.language:
                            ui.badge(sn.language.name).props("color=blue outline")
                        for tag in sn.tags:
                            ui.badge(f"#{tag.name}").props("color=teal outline")
                    ui.label(sn.updated_at.strftime("%Y-%m-%d")).classes(
                        "text-xs text-gray-400"
                    )

    @ui.refreshable
    def snippet_detail() -> None:
        """右ペインのスニペット詳細（コード表示・操作ボタン）を描画する"""
        if s.selected_id is None:
            # 未選択時はプレースホルダーを表示する
            with ui.column().classes("w-full items-center p-16 gap-3"):
                ui.icon("code").classes("text-8xl text-gray-200")
                ui.label("スニペットを選択してください").classes(
                    "text-gray-400 text-base"
                )
            return

        session = get_session()
        try:
            sn = get_snippet(session, s.selected_id)
        finally:
            session.close()

        if not sn:
            # 他の操作で削除された場合などに表示する
            ui.label("スニペットが削除されました").classes("text-gray-400 p-4")
            return

        # 言語名から highlight.js の識別子を取得する（未登録言語は plaintext で表示）
        lang_name = sn.language.name if sn.language else "その他"
        hl = _HIGHLIGHT_MAP.get(lang_name, "plaintext")

        ui.label(sn.title).classes("text-xl font-bold")
        if sn.description:
            ui.label(sn.description).classes("text-sm text-gray-600")

        with ui.row().classes("gap-1 flex-wrap items-center"):
            if sn.language:
                ui.badge(sn.language.name).props("color=blue outline")
            for tag in sn.tags:
                ui.badge(f"#{tag.name}").props("color=teal outline")
            ui.space()
            ui.label(sn.updated_at.strftime("%Y-%m-%d %H:%M")).classes(
                "text-xs text-gray-400"
            )

        # 操作ボタン群
        with ui.row().classes("gap-0"):
            ui.button("コピー", icon="content_copy", on_click=lambda: _copy(sn.code)).props(
                "flat dense no-caps"
            )
            # ピン留め中かどうかでボタンの表示・色を変える
            ui.button(
                "ピン留め中" if sn.is_pinned else "ピン留め",
                icon="push_pin",
                on_click=lambda: _toggle_pin(sn.id),
            ).props(
                f"{'unelevated' if sn.is_pinned else 'flat'} dense no-caps "
                f"color={'primary' if sn.is_pinned else 'grey-7'}"
            )
            ui.button(
                "複製",
                icon="content_copy",
                on_click=lambda: _duplicate(sn.id),
            ).props("flat dense no-caps color=teal")
            ui.button(
                "編集",
                icon="edit",
                on_click=lambda: _open_form(sn.id),
            ).props("flat dense no-caps color=secondary")
            ui.button(
                "削除",
                icon="delete_outline",
                on_click=lambda: _confirm_delete(sn.id),
            ).props("flat dense no-caps color=negative")

        # シンタックスハイライト付きでコードを表示する
        ui.code(sn.code, language=hl).classes("w-full text-sm")

    # ── コールバック ─────────────────────────────────────────────────────────

    def _on_lang(lid: int | None) -> None:
        """言語フィルターが変更されたときに呼ばれる"""
        s.language_id = lid
        s.selected_id = None  # 絞り込み変更時は選択状態をリセットする
        filter_panel.refresh()
        snippet_list.refresh()
        snippet_detail.refresh()

    def _on_tag(tid: int) -> None:
        """タグボタンがクリックされたときに呼ばれる（選択・解除をトグルする）"""
        if tid in s.tag_ids:
            s.tag_ids.remove(tid)
        else:
            s.tag_ids.append(tid)
        s.selected_id = None
        filter_panel.refresh()
        snippet_list.refresh()
        snippet_detail.refresh()

    def _on_tag_mode(mode: str) -> None:
        """AND / OR 切替ボタンが押されたときに呼ばれる"""
        s.tag_mode = mode
        s.selected_id = None
        filter_panel.refresh()
        snippet_list.refresh()
        snippet_detail.refresh()

    def _on_tag_reset() -> None:
        """タグのリセットボタンが押されたときに選択タグをすべて解除する"""
        s.tag_ids.clear()
        s.selected_id = None
        filter_panel.refresh()
        snippet_list.refresh()
        snippet_detail.refresh()

    def _on_toggle_lang() -> None:
        """言語セクションヘッダーがクリックされたときに折りたたみをトグルする"""
        s.lang_collapsed = not s.lang_collapsed
        filter_panel.refresh()

    def _on_toggle_tag() -> None:
        """タグセクションヘッダーがクリックされたときに折りたたみをトグルする"""
        s.tag_collapsed = not s.tag_collapsed
        filter_panel.refresh()

    def _on_select(sid: int) -> None:
        """スニペットカードがクリックされたときに右ペインに詳細を表示する"""
        s.selected_id = sid
        snippet_list.refresh()
        snippet_detail.refresh()

    def _copy(code: str) -> None:
        """コードをクリップボードにコピーする（JavaScript の Clipboard API を使用）"""
        ui.run_javascript(f"navigator.clipboard.writeText({json.dumps(code)})")
        ui.notify("コピーしました！", type="positive", position="top-right")

    def _toggle_pin(snippet_id: int) -> None:
        """ピン留めボタンが押されたときに ON/OFF を切り替える"""
        db = get_session()
        try:
            toggle_pin(db, snippet_id)
        finally:
            db.close()
        snippet_list.refresh()
        snippet_detail.refresh()

    def _on_pinned_only() -> None:
        """ピン留めフィルターボタンが押されたときに絞り込みをトグルする"""
        s.pinned_only = not s.pinned_only
        s.selected_id = None
        filter_panel.refresh()
        snippet_list.refresh()
        snippet_detail.refresh()

    def _duplicate(snippet_id: int) -> None:
        """複製ボタンが押されたときにスニペットを複製し、複製先を選択状態にする"""
        db = get_session()
        try:
            copy = duplicate_snippet(db, snippet_id)
        finally:
            db.close()
        if copy:
            s.selected_id = copy.id
            filter_panel.refresh()
            snippet_list.refresh()
            snippet_detail.refresh()
            ui.notify("複製しました", type="positive", position="top-right")

    def _open_form(snippet_id: int | None = None) -> None:
        """登録・編集フォームダイアログを開く。保存後に画面を再描画する。"""
        from app.ui.snippet_form import show_form

        def on_saved(saved_id: int) -> None:
            s.selected_id = saved_id
            filter_panel.refresh()
            snippet_list.refresh()
            snippet_detail.refresh()

        show_form(snippet_id, on_save=on_saved)

    def _confirm_delete(snippet_id: int) -> None:
        """削除確認ダイアログを表示し、確定後にスニペットを削除する"""
        with ui.dialog() as dlg, ui.card().classes("p-2 gap-3"):
            ui.label("このスニペットを削除しますか？").classes("font-semibold text-base")
            ui.label("この操作は元に戻せません。").classes("text-sm text-gray-500")
            with ui.row().classes("justify-end gap-2 w-full"):
                ui.button("キャンセル", on_click=dlg.close).props("flat no-caps")

                def do_delete() -> None:
                    db = get_session()
                    try:
                        delete_snippet(db, snippet_id)
                    finally:
                        db.close()
                    s.selected_id = None
                    dlg.close()
                    filter_panel.refresh()
                    snippet_list.refresh()
                    snippet_detail.refresh()
                    ui.notify("削除しました", type="warning", position="top-right")

                ui.button("削除", on_click=do_delete).props("color=negative no-caps")
        dlg.open()

    # ── メインレイアウト ─────────────────────────────────────────────────────

    # 外側コンテナ：画面全体を縦方向に占有する flex コンテナ
    with ui.element("div").style(
        "display: flex; flex-direction: column; height: 100vh; width: 100%;"
    ):
        # 上部バー：検索・新規登録ボタンを配置する
        with ui.element("div").classes(
            "flex shrink-0 items-center px-4 py-2 border-b gap-3 bg-white shadow-sm"
        ):
            ui.icon("snippet_folder").classes("text-blue-600 text-2xl")
            ui.label("CodeSnippet").classes(
                "font-bold text-lg text-blue-700 whitespace-nowrap"
            )
            # 検索バー：入力のたびにリアルタイムでスニペット一覧を更新する
            ui.input(
                placeholder="検索（タイトル・コード・タグ）",
                on_change=lambda e: [
                    setattr(s, "search", e.value),
                    snippet_list.refresh(),
                ],
            ).classes("flex-1").props("outlined dense clearable")
            ui.button(
                "+ 新規登録",
                on_click=lambda: _open_form(),
            ).props("color=primary unelevated no-caps")

        # 3ペイン本体：画面幅が狭い場合は横スクロールで対応する
        with ui.element("div").style(
            "display: flex; flex: 1; min-height: 0; overflow-x: auto; overflow-y: hidden;"
        ):
            # 左ペイン：フィルターパネル（固定幅 190px）
            with ui.element("div").style(
                "flex: none; width: 190px; min-width: 190px; "
                "overflow-y: auto; border-right: 1px solid #e0e0e0; background: #f9fafb;"
            ):
                filter_panel()

            # 中央ペイン：ソート選択 + スニペット一覧（固定幅 300px）
            with ui.element("div").style(
                "flex: none; width: 300px; min-width: 300px; display: flex; "
                "flex-direction: column; border-right: 1px solid #e0e0e0;"
            ):
                # ソート選択ドロップダウン（一覧上部に固定）
                with ui.element("div").style(
                    "flex-shrink: 0; padding: 6px 8px; "
                    "border-bottom: 1px solid #f0f0f0; background: #fafafa;"
                ):
                    ui.select(
                        options=_SORT_OPTIONS,
                        value=s.sort_by,
                        on_change=lambda e: [
                            setattr(s, "sort_by", e.value),
                            snippet_list.refresh(),
                        ],
                    ).style("width: 100%").props("outlined dense options-dense")
                # スニペットカードの一覧（縦スクロール可能）
                with ui.element("div").style("flex: 1; overflow-y: auto;"):
                    with ui.column().classes("p-2 gap-2 w-full"):
                        snippet_list()

            # 右ペイン：コード詳細（残り全幅を占有、縦横スクロール対応）
            with ui.element("div").style(
                "flex: 1; min-width: 380px; overflow-y: auto; overflow-x: auto;"
            ).classes("code-detail-pane"):
                with ui.column().classes("p-4 gap-3 w-full min-w-0"):
                    snippet_detail()
