# データベース接続・初期化・マイグレーション処理

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase

# DB ファイルの保存先（プロジェクトルートの data/ フォルダ）
DATA_DIR = Path(__file__).parent.parent / "data"
DATA_DIR.mkdir(exist_ok=True)  # フォルダが存在しない場合は自動作成

DATABASE_URL = f"sqlite:///{DATA_DIR}/snippets.db"

# SQLite はスレッドをまたぐ接続を禁止しているが、NiceGUI の非同期処理で
# 複数スレッドから触るため check_same_thread=False で制限を解除する
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})

# DB セッションのファクトリ（呼び出すたびに新しいセッションを生成する）
SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """全モデルの基底クラス。モデルはこのクラスを継承して定義する"""
    pass


def get_session():
    """新しい DB セッションを返す。使用後は呼び出し元で close() すること"""
    return SessionLocal()


def init_db() -> None:
    """アプリ起動時に呼び出す DB 初期化処理"""
    from app import models  # noqa: F401 — モデルをインポートして Base に登録する

    # 存在しないテーブルを作成する（既存テーブルは変更しない）
    Base.metadata.create_all(bind=engine)
    # 既存 DB へのカラム追加など、後から加えた変更を反映する
    _migrate()
    # 初回起動時のみサンプルデータを投入する
    _seed_initial_data()


def _migrate() -> None:
    """既存 DB に新しいカラムを追加するマイグレーション処理。
    既にカラムが存在する場合は例外を無視してスキップする。"""
    with engine.connect() as conn:
        try:
            conn.execute(
                __import__("sqlalchemy").text(
                    "ALTER TABLE snippets ADD COLUMN is_pinned BOOLEAN NOT NULL DEFAULT 0"
                )
            )
            conn.commit()
        except Exception:
            # カラムが既に存在する場合のエラーは正常なのでスキップ
            pass


def _seed_initial_data() -> None:
    """初回起動時のみサンプルデータ（言語・スニペット・タグ）を投入する"""
    from app.models import Language, Snippet, Tag

    session = SessionLocal()
    try:
        # 言語レコードが1件でもあれば投入済みとみなして終了する
        if session.query(Language).count() > 0:
            return

        # 初期言語マスタを登録し、名前→オブジェクトのマップを作成する
        lang_names = ["SQL", "C#", "VBA", "Python", "JavaScript", "PowerShell", "その他"]
        lang_map: dict[str, Language] = {}
        for name in lang_names:
            lang = Language(name=name)
            session.add(lang)
            lang_map[name] = lang
        session.flush()  # ID を確定させてからスニペット登録に進む

        # サンプルスニペットの定義
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

        # サンプルスニペットとタグを登録する
        # 同じタグ名を重複登録しないようにキャッシュを使う
        tag_cache: dict[str, Tag] = {}
        for s in samples:
            snippet = Snippet(
                title=s["title"],
                description=s["description"],
                code=s["code"],
                language=lang_map[s["language"]],
            )
            session.add(snippet)
            session.flush()  # スニペット ID を確定させてからタグを紐付ける
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
