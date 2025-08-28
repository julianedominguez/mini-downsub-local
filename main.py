import re
from flask import Flask, request, jsonify, render_template, make_response
from flask_cors import CORS
from youtube_transcript_api import YouTubeTranscriptApi, TranscriptsDisabled, NoTranscriptFound, VideoUnavailable

app = Flask(__name__)
CORS(app)

ID_RE = re.compile(r"[A-Za-z0-9_-]{11}")

# Soporta enlaces tipo watch?v=, youtu.be/, shorts/
PATTERNS = [
    r"v=([A-Za-z0-9_-]{11})",
    r"youtu\.be/([A-Za-z0-9_-]{11})",
    r"shorts/([A-Za-z0-9_-]{11})",
]

def extract_video_id(url_or_id: str):
    if ID_RE.fullmatch(url_or_id):
        return url_or_id
    for p in PATTERNS:
        m = re.search(p, url_or_id)
        if m:
            return m.group(1)
    return None

def get_transcript_text(video_id: str, langs=None):
    langs = langs or ["es", "es-419", "es-ES", "en"]
    data = YouTubeTranscriptApi.get_transcript(video_id, languages=langs)
    segments = [
        {"text": s.get("text", "").replace("\n", " ").strip(),
         "start": s.get("start"),
         "duration": s.get("duration")}
        for s in data if s.get("text", "").strip()
    ]
    plain = " ".join(s["text"] for s in segments)
    return plain, segments

@app.route("/")
def home():
    return render_template("index.html")

@app.route("/api/transcript")
def api_transcript():
    url = request.args.get("url", "").strip()
    langs = request.args.get("langs", "").split(",") if request.args.get("langs") else None
    vid = extract_video_id(url)
    if not vid:
        return jsonify({"ok": False, "error": "Link de YouTube inválido"}), 400
    try:
        text, segments = get_transcript_text(vid, langs)
        return jsonify({"ok": True, "videoId": vid, "text": text, "segments": segments})
    except TranscriptsDisabled:
        return jsonify({"ok": False, "error": "El video no tiene subtítulos habilitados."}), 404
    except NoTranscriptFound:
        return jsonify({"ok": False, "error": "No se encontró ningún subtítulo disponible en los idiomas solicitados."}), 404
    except VideoUnavailable:
        return jsonify({"ok": False, "error": "El video no está disponible (privado/bloqueado)."}), 404
    except Exception as e:
        return jsonify({"ok": False, "error": f"Error inesperado: {type(e).__name__}"}), 500

@app.route("/api/transcript.txt")
def api_transcript_txt():
    url = request.args.get("url", "").strip()
    langs = request.args.get("langs", "").split(",") if request.args.get("langs") else None
    vid = extract_video_id(url)
    if not vid:
        return ("Link inválido", 400, {"Content-Type": "text/plain; charset=utf-8"})
    try:
        text, _ = get_transcript_text(vid, langs)
        resp = make_response(text)
        resp.headers["Content-Type"] = "text/plain; charset=utf-8"
        resp.headers["Content-Disposition"] = f"attachment; filename=transcript_{vid}.txt"
        return resp
    except Exception as e:
        return (f"Error: {type(e).__name__}", 500, {"Content-Type": "text/plain; charset=utf-8"})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080, debug=False)
