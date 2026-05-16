import json
import uuid

from nicegui import ui

from app.crud import create_snippet, get_all_languages, get_all_tags, get_or_create_language, get_snippet, update_snippet
from app.database import get_session

# ダイアログ内コンテナの幅制限を解除するCSS
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
    """スニペット登録・編集ダイアログを表示する"""
    session = get_session()
    try:
        languages = get_all_languages(session)
        all_tags = get_all_tags(session)
        sn = get_snippet(session, snippet_id) if snippet_id else None
    finally:
        session.close()

    lang_options  = [lang.name for lang in languages]
    default_lang  = languages[0].name if languages else None
    tag_options   = [t.name for t in all_tags]

    init_title    = sn.title if sn else ""
    init_desc     = (sn.description or "") if sn else ""
    init_code     = sn.code if sn else ""
    init_lang     = (sn.language.name if sn.language else default_lang) if sn else default_lang
    init_tag_list = [t.name for t in sn.tags] if sn else []

    is_edit = snippet_id is not None

    ui.add_css(_FORM_CSS)

    # ui.card()をやめて素のdivを使う（Quasarの幅制限を回避）
    with ui.dialog().props("maximized").classes("snippet-form-dialog") as dialog:
        with ui.element("div").style(
            "display: flex; flex-direction: column; "
            "width: 100vw; height: 100vh; background: white; overflow: hidden;"
        ):

            # ── ヘッダー ────────────────────────────────────────────
            with ui.element("div").style(
                "display: flex; align-items: center; padding: 12px 24px; "
                "border-bottom: 1px solid #e0e0e0; flex-shrink: 0;"
            ):
                ui.label("スニペット編集" if is_edit else "スニペット登録").classes(
                    "font-bold text-lg flex-1"
                )
                ui.button(icon="close", on_click=dialog.close).props("flat round dense")

            # ── 本体（2カラム） ──────────────────────────────────────
            with ui.element("div").style(
                "display: flex; flex: 1; min-height: 0; overflow: hidden;"
            ):
                # 左カラム：メタ情報（固定幅）
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

                # 右カラム：コード入力（残り全幅・全高）
                with ui.element("div").style(
                    "display: flex; flex-direction: column; flex: 1; "
                    "min-width: 0; padding: 24px; gap: 8px; overflow: hidden;"
                ):
                    ui.label("コード *").style(
                        "font-size: 0.875rem; font-weight: 600; "
                        "color: #4b5563; flex-shrink: 0;"
                    )

                    ta_id = f"code-ta-{uuid.uuid4().hex}"
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

                    ui.timer(0.1, lambda: ui.run_javascript(
                        f'const el = document.getElementById("{ta_id}");'
                        f'if (el) el.value = {json.dumps(init_code)};'
                    ), once=True)

            # ── フッター ─────────────────────────────────────────────
            with ui.element("div").style(
                "display: flex; justify-content: flex-end; gap: 8px; "
                "padding: 12px 24px; border-top: 1px solid #e0e0e0; flex-shrink: 0;"
            ):
                ui.button("キャンセル", on_click=dialog.close).props("flat no-caps")

                async def save() -> None:
                    title   = title_input.value.strip()
                    lang_id = lang_select.value
                    code    = await ui.run_javascript(
                        f'return document.getElementById("{ta_id}").value;'
                    )
                    code = (code or "").strip()

                    lang_name = (lang_select.value or "").strip()

                    if not title:
                        ui.notify("タイトルを入力してください", type="warning")
                        return
                    if not code:
                        ui.notify("コードを入力してください", type="warning")
                        return
                    if not lang_name:
                        ui.notify("言語を選択してください", type="warning")
                        return

                    tags = [t.strip() for t in (tags_select.value or []) if t.strip()]

                    db = get_session()
                    try:
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
                    if on_save:
                        on_save(saved_id)

                ui.button("保存", on_click=save).props("color=primary unelevated no-caps")

    dialog.open()
