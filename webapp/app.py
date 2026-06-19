"""Local Flask web UI for FortiObfuscator.

Binds to 127.0.0.1 only. Uploads are processed entirely in memory — nothing is
written to disk server-side and no external requests are made.

Run:
    python -m webapp.app
then open http://127.0.0.1:5000
"""

from __future__ import annotations

import io
import json
import os
import sys
import zipfile

from flask import Flask, render_template, request, send_file

# Allow `python webapp/app.py` as well as `python -m webapp.app`.
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from fortiobfuscator.engine import (  # noqa: E402
    ALL_CATEGORY_KEYS,
    ALL_TYPE_KEYS,
    Options,
    obfuscate,
)
from fortiobfuscator.rules import CATEGORIES, TYPE_TOGGLES  # noqa: E402

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 64 * 1024 * 1024  # 64 MB cap


@app.get("/")
def index():
    return render_template(
        "index.html",
        type_toggles=TYPE_TOGGLES,
        categories=CATEGORIES,
    )


@app.post("/obfuscate")
def do_obfuscate():
    upload = request.files.get("config")
    if not upload or not upload.filename:
        return ("No file uploaded.", 400)

    raw = upload.read()
    text = raw.decode("utf-8", errors="replace")

    types = {k for k in ALL_TYPE_KEYS if request.form.get(f"type_{k}")}
    cats = {k for k in ALL_CATEGORY_KEYS if request.form.get(f"cat_{k}")}
    emit_mapping = bool(request.form.get("emit_mapping"))

    options = Options(types=types, categories=cats, emit_mapping=emit_mapping)
    result = obfuscate(text, options)

    base = os.path.splitext(os.path.basename(upload.filename))[0] or "config"
    scrubbed_name = f"{base}_obfuscated.conf"
    scrubbed_bytes = result.text.encode("utf-8")

    if emit_mapping and result.mapping is not None:
        # Bundle scrubbed config + mapping + summary into a zip download.
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
            zf.writestr(scrubbed_name, scrubbed_bytes)
            zf.writestr(
                f"{base}_mapping.json",
                json.dumps(result.mapping, indent=2, sort_keys=True),
            )
            zf.writestr(
                f"{base}_summary.json",
                json.dumps(result.report.as_dict(), indent=2),
            )
        buf.seek(0)
        return send_file(
            buf,
            mimetype="application/zip",
            as_attachment=True,
            download_name=f"{base}_obfuscated.zip",
        )

    return send_file(
        io.BytesIO(scrubbed_bytes),
        mimetype="text/plain",
        as_attachment=True,
        download_name=scrubbed_name,
    )


def main() -> None:
    # 127.0.0.1 only — never exposed beyond this machine.
    app.run(host="127.0.0.1", port=5000, debug=False)


if __name__ == "__main__":
    main()
