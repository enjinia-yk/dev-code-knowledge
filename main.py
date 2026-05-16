from nicegui import ui

from app.database import init_db


def main() -> None:
    init_db()

    @ui.page("/")
    def index() -> None:
        ui.query("body").style("margin: 0; padding: 0; overflow: hidden; height: 100vh;")
        ui.query(".nicegui-content").style("padding: 0; max-width: 100%; height: 100%; display: flex; flex-direction: column;")
        from app.ui.layout import create_layout

        create_layout()

    ui.run(title="CodeSnippet", port=8080, reload=False, show=True)


if __name__ == "__main__":
    main()
