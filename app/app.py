import os
from flask import Flask, jsonify, render_template_string, request


class PrefixMiddleware:
    """Lets the app live under a path like /pr-42 behind the load balancer."""

    def __init__(self, wsgi_app, prefix=""):
        self.wsgi_app = wsgi_app
        self.prefix = prefix.rstrip("/")

    def __call__(self, environ, start_response):
        if not self.prefix:
            return self.wsgi_app(environ, start_response)
        path = environ.get("PATH_INFO", "")
        if path == self.prefix or path.startswith(self.prefix + "/"):
            environ["SCRIPT_NAME"] = self.prefix
            environ["PATH_INFO"] = path[len(self.prefix):] or "/"
            return self.wsgi_app(environ, start_response)
        start_response("404 Not Found", [("Content-Type", "text/plain")])
        return [b"Not Found"]


PAGE = """
<!doctype html>
<title>CO2 Estimator Preview</title>
<h1>CO2 Estimator (preview)</h1>
<p>Prefix: <code>{{ prefix or "none" }}</code> | Commit: <code>{{ sha }}</code></p>
<p>Try: <a href="{{ url_for('co2', km=100, l_per_100km=7) }}">100 km at 7 L/100km</a></p>
<p>Health check: <a href="{{ url_for('health') }}">/health</a></p>
"""


def create_app(prefix=None):
    app = Flask(__name__)
    if prefix is None:
        prefix = os.environ.get("APP_PREFIX", "")
    app.wsgi_app = PrefixMiddleware(app.wsgi_app, prefix)

    @app.get("/")
    def index():
        return render_template_string(
            PAGE, prefix=prefix, sha=os.environ.get("GIT_SHA", "local")
        )

    @app.get("/health")
    def health():
        return jsonify(status="ok")

    @app.get("/api/co2")
    def co2():
        try:
            km = float(request.args.get("km", 0))
            rate = float(request.args.get("l_per_100km", 0))
        except ValueError:
            return jsonify(error="km and l_per_100km must be numbers"), 400
        if km < 0 or rate < 0:
            return jsonify(error="values must not be negative"), 400
        litres = km * rate / 100
        kg = litres * 2.31  # rough petrol factor, demo only
        return jsonify(km=km, litres=round(litres, 2), co2_kg=round(kg, 2))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
