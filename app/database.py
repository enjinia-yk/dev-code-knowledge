from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)

DATABASE_URL = f"sqlite:///{DATA_DIR}/snippets.db"
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    pass


def get_session():
    return SessionLocal()


def init_db() -> None:
    from app import models  # noqa: F401

    Base.metadata.create_all(bind=engine)
    _migrate()
    _seed_initial_data()


def _migrate() -> None:
    with engine.connect() as conn:
        try:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE snippets ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            conn.commit()
        except Exception:
            pass


def _seed_initial_data() -> None:
    from app.models import Language, Snippet, Tag

    session = SessionLocal()
    try:
        if session.query(Language).count() > 0:
            return

        lang_names = ["SQL", "C#", "VBA", "Python", "JavaScript", "PowerShell", "その他"]
        lang_map: dict[str, Language] = {}
        for name in lang_names:
            lang = Language(name=name)
            session.add(lang)
            lang_map[name] = lang
        session.flush()

        samples = [
            {
                "title": "顧客一覧取得",
                "description": "有効な顧客を名前順で取得する基本クエリ",
                "language": "SQL",
                "tags": ["業務系", "顧客管理"],
                "code": (
                    "SELECT\n"
                    "    customer_id,\n"
                    "    customer_name,\n"
                    "    email,\n"
                    "    created_at\n"
                    "FROM\n"
                    "    customers\n"
                    "WHERE\n"
                    "    is_active = 1\n"
                    "ORDER BY\n"
                    "    customer_name;"
                ),
            },
            {
                "title": "月次売上集計",
                "description": "過去6か月の月別売上件数・金額を集計する",
                "language": "SQL",
                "tags": ["業務系", "月次", "集計"],
                "code": (
                    "SELECT\n"
                    "    FORMAT(order_date, 'yyyy-MM') AS year_month,\n"
                    "    COUNT(*)                      AS order_count,\n"
                    "    SUM(amount)                   AS total_amount\n"
                    "FROM\n"
                    "    orders\n"
                    "WHERE\n"
                    "    order_date >= DATEADD(MONTH, -6, GETDATE())\n"
                    "GROUP BY\n"
                    "    FORMAT(order_date, 'yyyy-MM')\n"
                    "ORDER BY\n"
                    "    year_month;"
                ),
            },
            {
                "title": "DataGridView 全行ループ",
                "description": "DataGridView の全行をループして値を取得する",
                "language": "C#",
                "tags": ["業務系", "WinForms"],
                "code": (
                    "foreach (DataGridViewRow row in dataGridView1.Rows)\n"
                    "{\n"
                    "    if (row.IsNewRow) continue;\n"
                    "\n"
                    "    string value = row.Cells[\"ColumnName\"].Value?.ToString() ?? string.Empty;\n"
                    "    Console.WriteLine(value);\n"
                    "}"
                ),
            },
        ]

        tag_cache: dict[str, Tag] = {}
        for s in samples:
            snippet = Snippet(
                title=s["title"],
                description=s["description"],
                code=s["code"],
                language=lang_map[s["language"]],
            )
            session.add(snippet)
            session.flush()
            for tag_name in s["tags"]:
                if tag_name not in tag_cache:
                    tag = Tag(name=tag_name)
                    session.add(tag)
                    session.flush()
                    tag_cache[tag_name] = tag
                snippet.tags.append(tag_cache[tag_name])

        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
