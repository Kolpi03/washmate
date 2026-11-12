import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    with app.app_context():
        from manage import init_db
        init_db()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 5000)), debug=False, threaded=True)
