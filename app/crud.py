from datetime import datetime

from sqlalchemy import or_
from sqlalchemy.orm import Session, joinedload

from app.models import Language, Snippet, Tag


def get_all_languages(session: Session) -> list[Language]:
    return session.query(Language).order_by(Language.name).all()


def get_or_create_language(session: Session, name: str) -> Language:
    name = name.strip()
    lang = session.query(Language).filter(Language.name == name).first()
    if not lang:
        lang = Language(name=name)
        session.add(lang)
        session.flush()
    return lang


def get_all_tags(session: Session) -> list[Tag]:
    return session.query(Tag).order_by(Tag.name).all()


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
    q = session.query(Snippet).options(
        joinedload(Snippet.language),
        joinedload(Snippet.tags),
    )
    if pinned_only:
        q = q.filter(Snippet.is_pinned.is_(True))
    if language_id is not None:
        q = q.filter(Snippet.language_id == language_id)
    if tag_ids:
        if tag_mode == "and":
            for tid in tag_ids:
                q = q.filter(Snippet.tags.any(Tag.id == tid))
        else:
            q = q.filter(Snippet.tags.any(Tag.id.in_(tag_ids)))
    if search:
        like = f"%{search}%"
        q = q.filter(
            or_(
                Snippet.title.ilike(like),
                Snippet.description.ilike(like),
                Snippet.code.ilike(like),
                Snippet.tags.any(Tag.name.ilike(like)),
            )
        )
    order = _SORT_COLUMNS.get(sort_by, Snippet.updated_at.desc())
    return q.order_by(Snippet.is_pinned.desc(), order).all()


def get_snippet(session: Session, snippet_id: int) -> Snippet | None:
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
    snippet = Snippet(
        title=title, code=code, language_id=language_id, description=description
    )
    session.add(snippet)
    session.flush()
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
    snippet.updated_at = datetime.now()
    _sync_tags(session, snippet, tags or [])
    session.commit()
    session.refresh(snippet)
    return snippet


def toggle_pin(session: Session, snippet_id: int) -> Snippet | None:
    snippet = session.query(Snippet).filter(Snippet.id == snippet_id).first()
    if not snippet:
        return None
    snippet.is_pinned = not snippet.is_pinned
    session.commit()
    session.refresh(snippet)
    return snippet


def duplicate_snippet(session: Session, snippet_id: int) -> Snippet | None:
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
    )
    session.add(copy)
    session.flush()
    _sync_tags(session, copy, [t.name for t in original.tags])
    session.commit()
    session.refresh(copy)
    return copy


def delete_snippet(session: Session, snippet_id: int) -> None:
    snippet = session.query(Snippet).filter(Snippet.id == snippet_id).first()
    if snippet:
        session.delete(snippet)
        session.flush()
        _cleanup_unused_tags(session)
        session.commit()


def _sync_tags(session: Session, snippet: Snippet, tag_names: list[str]) -> None:
    snippet.tags.clear()
    session.flush()
    for raw in tag_names:
        name = raw.strip()
        if not name:
            continue
        tag = session.query(Tag).filter(Tag.name == name).first()
        if not tag:
            tag = Tag(name=name)
            session.add(tag)
            session.flush()
        snippet.tags.append(tag)
    _cleanup_unused_tags(session)


def _cleanup_unused_tags(session: Session) -> None:
    from app.models import SnippetTag
    used_ids = {row.tag_id for row in session.query(SnippetTag.tag_id).all()}
    session.query(Tag).filter(Tag.id.notin_(used_ids)).delete(synchronize_session="fetch")
