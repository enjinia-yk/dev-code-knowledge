# スニペット・言語・タグの CRUD 操作（Create / Read / Update / Delete）

from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models import Language, Snippet, Tag


def get_all_languages(session: Session) -> list[Language]:
    """全言語を名前順で取得する"""
    return session.query(Language).order_by(Language.name).all()


def get_language_snippet_counts(session: Session) -> dict[int, int]:
    """言語IDごとのスニペット数を返す（削除ボタンの表示判定に使用）"""
    from sqlalchemy import func
    rows = (
        session.query(Language.id, func.count(Snippet.id))
        .outerjoin(Snippet, Snippet.language_id == Language.id)
        .group_by(Language.id)
        .all()
    )
    return {lang_id: count for lang_id, count in rows}


def delete_language(session: Session, language_id: int) -> bool:
    """スニペットに使われていない言語を削除する。使われている場合は False を返す"""
    count = session.query(Snippet).filter(Snippet.language_id == language_id).count()
    if count > 0:
        return False
    lang = session.query(Language).filter(Language.id == language_id).first()
    if not lang:
        return False
    session.delete(lang)
    session.commit()
    return True


def get_or_create_language(session: Session, name: str) -> Language:
    """言語名で検索し、存在しなければ新規作成して返す"""
    name = name.strip()
    lang = session.query(Language).filter(Language.name == name).first()
    if not lang:
        lang = Language(name=name)
        session.add(lang)
        session.flush()  # ID を確定させる
    return lang


def get_all_tags(session: Session) -> list[Tag]:
    """全タグを名前順で取得する"""
    return session.query(Tag).order_by(Tag.name).all()


# ソート条件の定義（キー → SQLAlchemy の ORDER BY 句）
_SORT_COLUMNS = {
    "updated_desc": Snippet.updated_at.desc(),
    "updated_asc":  Snippet.updated_at.asc(),
    "created_desc": Snippet.created_at.desc(),
    "created_asc":  Snippet.created_at.asc(),
    "title_asc":    Snippet.title.asc(),
    "title_desc":   Snippet.title.desc(),
}


def get_snippets(
    session: Session,
    search: str = "",
    language_id: int | None = None,
    tag_ids: list[int] | None = None,
    tag_mode: str = "or",
    sort_by: str = "updated_desc",
    pinned_only: bool = False,
) -> list[Snippet]:
    """条件に合うスニペット一覧を取得する。
    ピン留めスニペットは常に先頭にまとめて表示する。"""

    # 言語・タグを1回のクエリで取得する（N+1問題を防ぐ）
    q = session.query(Snippet).options(
        joinedload(Snippet.language),
        joinedload(Snippet.tags),
    )

    # ピン留めのみ表示フィルター
    if pinned_only:
        q = q.filter(Snippet.is_pinned.is_(True))

    # 言語フィルター
    if language_id is not None:
        q = q.filter(Snippet.language_id == language_id)

    # タグフィルター（AND: 全タグを持つ / OR: いずれかのタグを持つ）
    if tag_ids:
        if tag_mode == "and":
            # 各タグ条件を連鎖させることで AND 絞り込みを実現する
            for tid in tag_ids:
                q = q.filter(Snippet.tags.any(Tag.id == tid))
        else:
            q = q.filter(Snippet.tags.any(Tag.id.in_(tag_ids)))

    # キーワード検索（スペース区切りで複数ワードの AND 検索）
    # 各ワードがタイトル・説明・コード・タグ名・言語名のいずれかに部分一致すればヒット
    if search:
        for word in search.split():
            like = f"%{word}%"
            q = q.filter(
                or_(
                    Snippet.title.ilike(like),
                    Snippet.description.ilike(like),
                    Snippet.code.ilike(like),
                    Snippet.tags.any(Tag.name.ilike(like)),
                    Snippet.language.has(Language.name.ilike(like)),
                )
            )

    # ピン留めを先頭に固定し、その中で選択されたソート順を適用する
    order = _SORT_COLUMNS.get(sort_by, Snippet.updated_at.desc())
    return q.order_by(Snippet.is_pinned.desc(), order).all()


def get_snippet(session: Session, snippet_id: int) -> Snippet | None:
    """ID を指定してスニペット1件を取得する"""
    return (
        session.query(Snippet)
        .options(joinedload(Snippet.language), joinedload(Snippet.tags))
        .filter(Snippet.id == snippet_id)
        .first()
    )


def create_snippet(
    session: Session,
    title: str,
    code: str,
    language_id: int,
    description: str = "",
    tags: list[str] | None = None,
) -> Snippet:
    """新しいスニペットを登録して返す"""
    snippet = Snippet(
        title=title, code=code, language_id=language_id, description=description
    )
    session.add(snippet)
    session.flush()  # ID を確定させてからタグを紐付ける
    _sync_tags(session, snippet, tags or [])
    session.commit()
    session.refresh(snippet)
    return snippet


def update_snippet(
    session: Session,
    snippet_id: int,
    title: str,
    code: str,
    language_id: int,
    description: str = "",
    tags: list[str] | None = None,
) -> Snippet | None:
    """既存スニペットを更新して返す。対象が存在しない場合は None を返す"""
    snippet = (
        session.query(Snippet)
        .options(joinedload(Snippet.tags))
        .filter(Snippet.id == snippet_id)
        .first()
    )
    if not snippet:
        return None
    snippet.title = title
    snippet.code = code
    snippet.language_id = language_id
    snippet.description = description
    # onupdate では手動更新が反映されないケースがあるため明示的に設定する
    snippet.updated_at = datetime.now()
    _sync_tags(session, snippet, tags or [])
    session.commit()
    session.refresh(snippet)
    return snippet


def toggle_pin(session: Session, snippet_id: int) -> Snippet | None:
    """スニペットのピン留め状態を ON/OFF 切り替えて返す"""
    snippet = session.query(Snippet).filter(Snippet.id == snippet_id).first()
    if not snippet:
        return None
    snippet.is_pinned = not snippet.is_pinned
    session.commit()
    session.refresh(snippet)
    return snippet


def duplicate_snippet(session: Session, snippet_id: int) -> Snippet | None:
    """スニペットを複製して新しいスニペットとして返す。
    ピン留め状態は引き継がない。"""
    original = (
        session.query(Snippet)
        .options(joinedload(Snippet.tags))
        .filter(Snippet.id == snippet_id)
        .first()
    )
    if not original:
        return None
    copy = Snippet(
        title=f"{original.title} のコピー",
        code=original.code,
        description=original.description,
        language_id=original.language_id,
        # is_pinned はデフォルト値（False）のまま引き継がない
    )
    session.add(copy)
    session.flush()
    _sync_tags(session, copy, [t.name for t in original.tags])
    session.commit()
    session.refresh(copy)
    return copy


def delete_snippet(session: Session, snippet_id: int) -> None:
    """スニペットを削除し、不要になったタグも合わせて削除する"""
    snippet = session.query(Snippet).filter(Snippet.id == snippet_id).first()
    if snippet:
        session.delete(snippet)
        session.flush()  # 削除を確定してから孤立タグを検出する
        _cleanup_unused_tags(session)
        session.commit()


def _sync_tags(session: Session, snippet: Snippet, tag_names: list[str]) -> None:
    """スニペットに紐づくタグを tag_names の内容に同期する。
    一度全て外してから付け直すことで追加・削除を一括処理する。"""
    snippet.tags.clear()
    session.flush()
    for raw in tag_names:
        name = raw.strip()
        if not name:
            continue
        # 既存タグを再利用し、なければ新規作成する
        tag = session.query(Tag).filter(Tag.name == name).first()
        if not tag:
            tag = Tag(name=name)
            session.add(tag)
            session.flush()
        snippet.tags.append(tag)
    # タグ同期後に使われなくなったタグを削除する
    _cleanup_unused_tags(session)


def _cleanup_unused_tags(session: Session) -> None:
    """どのスニペットにも紐づいていない孤立タグを一括削除する"""
    from app.models import SnippetTag
    # 現在使われているタグ ID のセットを取得する
    used_ids = {row.tag_id for row in session.query(SnippetTag.tag_id).all()}
    # 使われていないタグをまとめて削除する
    session.query(Tag).filter(Tag.id.notin_(used_ids)).delete(synchronize_session="fetch")
