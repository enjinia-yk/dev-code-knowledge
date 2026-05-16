# アプリのエントリーポイント
# NiceGUI のサーバーを起動し、ルートページ（/）を定義する

from nicegui import ui

from app.database import init_db


def main() -> None:
    # DB の初期化（テーブル作成・マイグレーション・サンプルデータ投入）
    init_db()

    @ui.page("/")
    def index() -> None:
        # ページ全体のスタイルをリセットし、スクロールバーが画面外に出ないよう制御する
        ui.query("body").style("margin: 0; padding: 0; overflow: hidden; height: 100vh;")
        # NiceGUI が生成するコンテンツラッパーを flex コンテナにして高さを継承させる
        ui.query(".nicegui-content").style("padding: 0; max-width: 100%; height: 100%; display: flex; flex-direction: column;")
        from app.ui.layout import create_layout

        # メインレイアウトを描画する
        create_layout()

    # ポート 8080 でサーバーを起動し、ブラウザを自動で開く
    ui.run(title="CodeSnippet", port=8080, reload=False, show=True)


if __name__ == "__main__":
    main()
