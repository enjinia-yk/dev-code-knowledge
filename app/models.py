from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Language(Base):
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)

    snippets = relationship("Snippet", back_populates="language")


class Snippet(Base):
    __tablename__ = "snippets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)
    description = Column(Text)
    code = Column(Text, nullable=False)
    language_id = Column(Integer, ForeignKey("languages.id"))
    is_pinned = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.now)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)

    language = relationship("Language", back_populates="snippets")
    tags = relationship("Tag", secondary="snippet_tags", back_populates="snippets")


class Tag(Base):
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)

    snippets = relationship("Snippet", secondary="snippet_tags", back_populates="tags")


class SnippetTag(Base):
    __tablename__ = "snippet_tags"

    snippet_id = Column(
        Integer, ForeignKey("snippets.id", ondelete="CASCADE"), primary_key=True
    )
    tag_id = Column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
