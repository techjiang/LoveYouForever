"""生产环境入口：gunicorn -w 4 -b 0.0.0.0:8000 wsgi:app"""
import os

from app import create_app

app = create_app(os.environ.get("LYF_ENV", "production"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
