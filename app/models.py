# データベースのテーブル定義（SQLAlchemy ORM モデル）
# 各クラスが1つのテーブルに対応する

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship

from app.database import Base


class Language(Base):
    """プログラミング言語マスタ（languages テーブル）"""
    __tablename__ = "languages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)  # 言語名（重複不可）

    # この言語に紐づくスニペット一覧
    snippets = relationship("Snippet", back_populates="language")


class Snippet(Base):
    """コードスニペット本体（snippets テーブル）"""
    __tablename__ = "snippets"

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(String, nullable=False)       # タイトル（必須）
    description = Column(Text)                   # 説明（任意）
    code = Column(Text, nullable=False)          # コード本文（必須）
    language_id = Column(Integer, ForeignKey("languages.id"))  # 言語への外部キー
    is_pinned = Column(Boolean, nullable=False, default=False)  # ピン留め状態
    created_at = Column(DateTime, default=datetime.now)                        # 作成日時
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now) # 更新日時（変更時に自動更新）

    # 関連テーブルへのリレーション
    language = relationship("Language", back_populates="snippets")
    tags = relationship("Tag", secondary="snippet_tags", back_populates="snippets")


class Tag(Base):
    """タグマスタ（tags テーブル）"""
    __tablename__ = "tags"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, unique=True, nullable=False)  # タグ名（重複不可）

    # このタグが付いているスニペット一覧
    snippets = relationship("Snippet", secondary="snippet_tags", back_populates="tags")


class SnippetTag(Base):
    """スニペットとタグの中間テーブル（多対多の紐付け）"""
    __tablename__ = "snippet_tags"

    # スニペット削除時に関連レコードも自動削除（CASCADE）
    snippet_id = Column(
        Integer, ForeignKey("snippets.id", ondelete="CASCADE"), primary_key=True
    )
    # タグ削除時に関連レコードも自動削除（CASCADE）
    tag_id = Column(
        Integer, ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True
    )
