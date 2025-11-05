from flask import Flask


def create_app() -> Flask:
    app = Flask(__name__)
    app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB upload limit
    app.secret_key = "docx-split-secret"

    from .routes import bp as main_bp  # type: ignore

    app.register_blueprint(main_bp)
    return app
