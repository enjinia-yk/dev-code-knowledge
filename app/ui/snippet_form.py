# スニペット登録・編集フォームのダイアログ

import json
import uuid

from nicegui import ui

from app.crud import create_snippet, get_all_languages, get_all_tags, get_or_create_language, get_snippet, update_snippet
from app.database import get_session

# Quasar（NiceGUI の UI フレームワーク）がダイアログの幅を制限するため、
# CSS で上書きして全画面表示に対応する
_FORM_CSS = """
.snippet-form-dialog .q-dialog__inner {
    width: 100vw !important;
    max-width: 100vw !important;
    height: 100vh !important;
    max-height: 100vh !important;
    padding: 0 !important;
}
.snippet-form-dialog .q-dialog__inner > div {
    width: 100% !important;
    height: 100% !important;
}
"""


def show_form(
    snippet_id: int | None = None,
    on_save=None,
) -> None:
    """スニペット登録・編集ダイアログを表示する。
    snippet_id が None の場合は新規登録、指定された場合は編集モードになる。
    保存完了後は on_save(saved_id) が呼ばれる。"""

    # フォームを開く前に DB から言語・タグ・対象スニペットを取得する
    session = get_session()
    try:
        languages = get_all_languages(session)
        all_tags = get_all_tags(session)
        sn = get_snippet(session, snippet_id) if snippet_id else None
    finally:
        session.close()

    # 選択肢の準備
    lang_options  = [lang.name for lang in languages]
    default_lang  = languages[0].name if languages else None
    tag_options   = [t.name for t in all_tags]

    # 初期値の設定（編集時は既存データ、新規時は空）
    init_title    = sn.title if sn else ""
    init_desc     = (sn.description or "") if sn else ""
    init_code     = sn.code if sn else ""
    init_lang     = (sn.language.name if sn.language else default_lang) if sn else default_lang
    init_tag_list = [t.name for t in sn.tags] if sn else []

    is_edit = snippet_id is not None  # 編集モードかどうかのフラグ

    ui.add_css(_FORM_CSS)

    # maximized で全画面ダイアログを表示する
    # ui.card() を使わず素の div にすることで Quasar の幅制限を回避する
    with ui.dialog().props("maximized").classes("snippet-form-dialog") as dialog:
        with ui.element("div").style(
            "display: flex; flex-direction: column; "
            "width: 100vw; height: 100vh; background: white; overflow: hidden;"
        ):

            # ── ヘッダー（タイトル + 閉じるボタン）────────────────────
            with ui.element("div").style(
                "display: flex; align-items: center; padding: 12px 24px; "
                "border-bottom: 1px solid #e0e0e0; flex-shrink: 0;"
            ):
                ui.label("スニペット編集" if is_edit else "スニペット登録").classes(
                    "font-bold text-lg flex-1"
                )
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")

            # ── 本体（左カラム：メタ情報 / 右カラム：コード入力）────────
            with ui.element("div").style(
                "display: flex; flex: 1; min-height: 0; overflow: hidden;"
            ):
                # 左カラム：タイトル・説明・言語・タグを入力する（固定幅）
                with ui.element("div").style(
                    "width: 360px; flex-shrink: 0; display: flex; "
                    "flex-direction: column; gap: 16px; padding: 24px; "
                    "border-right: 1px solid #e0e0e0; overflow-y: auto;"
                ):
                    ui.label("タイトル *").classes("text-sm font-semibold text-gray-600 -mb-2")
                    title_input = (
                        ui.input(value=init_title, placeholder="例: 顧客一覧取得")
                        .style("width: 100%")
                        .props("outlined dense")
                    )

                    ui.label("説明（任意）").classes("text-sm font-semibold text-gray-600 -mb-2")
                    desc_input = (
                        ui.input(value=init_desc, placeholder="例: 有効な顧客を名前順で取得")
                        .style("width: 100%")
                        .props("outlined dense")
                    )

                    ui.label("言語 *").classes("text-sm font-semibold text-gray-600 -mb-2")
                    # use-input で入力補完、add-unique で新規言語のインライン追加を可能にする
                    lang_select = (
                        ui.select(
                            options=lang_options,
                            value=init_lang,
                            new_value_mode="add-unique",
                        )
                        .style("width: 100%")
                        .props("outlined dense use-input hide-dropdown-icon")
                    )

                    ui.label("タグ").classes("text-sm font-semibold text-gray-600 -mb-2")
                    # use-chips で選択済みタグをバッジ表示、複数選択・新規追加に対応する
                    tags_select = (
                        ui.select(
                            options=tag_options,
                            value=init_tag_list,
                            multiple=True,
                            new_value_mode="add-unique",
                        )
                        .style("width: 100%")
                        .props("outlined dense use-chips use-input hide-dropdown-icon")
                    )
                    ui.label("既存タグを選択、または入力して新規作成できます").classes(
                        "text-xs text-gray-400 -mt-3"
                    )

                # 右カラム：コード入力エリア（残り全幅・全高を占有する）
                with ui.element("div").style(
                    "display: flex; flex-direction: column; flex: 1; "
                    "min-width: 0; padding: 24px; gap: 8px; overflow: hidden;"
                ):
                    ui.label("コード *").style(
                        "font-size: 0.875rem; font-weight: 600; "
                        "color: #4b5563; flex-shrink: 0;"
                    )

                    # NiceGUI の ui.textarea はコード入力に不向きなため、
                    # 生の textarea 要素を使い JavaScript で初期値を注入する
                    ta_id = f"code-ta-{uuid.uuid4().hex}"  # 複数ダイアログが同時に存在しても衝突しない ID
                    ui.element("textarea").props(f'id="{ta_id}"').style(
                        "flex: 1; "
                        "width: 100%; "
                        "min-height: 0; "
                        "padding: 12px; "
                        "font-family: Consolas, Monaco, monospace; "
                        "font-size: 0.875rem; "
                        "line-height: 1.6; "
                        "border: 1px solid #9e9e9e; "
                        "border-radius: 4px; "
                        "box-sizing: border-box; "
                        "overflow: auto; "
                        "white-space: pre; "
                        "resize: none; "
                        "outline: none; "
                        "background: #fafafa;"
                    )

                    # DOM が描画された後に初期値を注入する（描画前に実行すると要素が存在しない）
                    ui.timer(0.1, lambda: ui.run_javascript(
                        f'const el = document.getElementById("{ta_id}");'
                        f'if (el) el.value = {json.dumps(init_code)};'
                    ), once=True)

            # ── フッター（キャンセル / 保存ボタン）──────────────────────
            with ui.element("div").style(
                "display: flex; justify-content: flex-end; gap: 8px; "
                "padding: 12px 24px; border-top: 1px solid #e0e0e0; flex-shrink: 0;"
            ):
                ui.button("キャンセル", on_click=dialog.close).props("flat no-caps")

                async def save() -> None:
                    """入力内容を検証して DB に保存する"""
                    title = title_input.value.strip()
                    # textarea の値は Vue の管理外のため JavaScript 経由で取得する
                    code = await ui.run_javascript(
                        f'return document.getElementById("{ta_id}").value;'
                    )
                    code = (code or "").strip()
                    lang_name = (lang_select.value or "").strip()

                    # 必須項目のバリデーション
                    if not title:
                        ui.notify("タイトルを入力してください", type="warning")
                        return
                    if not code:
                        ui.notify("コードを入力してください", type="warning")
                        return
                    if not lang_name:
                        ui.notify("言語を選択してください", type="warning")
                        return

                    # タグは空文字を除外してリスト化する
                    tags = [t.strip() for t in (tags_select.value or []) if t.strip()]

                    db = get_session()
                    try:
                        # 言語名から ID を取得する（存在しなければ新規作成）
                        lang = get_or_create_language(db, lang_name)
                        if is_edit:
                            update_snippet(
                                db, snippet_id, title, code, lang.id,
                                desc_input.value, tags,
                            )
                            saved_id = snippet_id
                        else:
                            new_sn = create_snippet(
                                db, title, code, lang.id, desc_input.value, tags
                            )
                            saved_id = new_sn.id
                    finally:
                        db.close()

                    dialog.close()
                    ui.notify("保存しました", type="positive", position="top-right")
                    # 保存後にリストを再描画して選択状態を更新するためコールバックを呼ぶ
                    if on_save:
                        on_save(saved_id)

                ui.button("保存", on_click=save).props("color=primary unelevated no-caps")

    dialog.open()
