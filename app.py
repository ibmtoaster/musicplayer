import os
import vlc
import time
import threading
from flask import Flask, render_template, jsonify, request

MUSIC_DIR = "/home/pi/Music"  # <-- Change to your music folder

app = Flask(__name__)

# VLC player setup
instance = vlc.Instance()
player = instance.media_player_new()

current_media = None
progress_thread = None
running = False
paused = False


def progress_updater():
    global running
    while running:
        time.sleep(1)


@app.route("/")
@app.route("/browse", defaults={"path": ""})
@app.route("/browse/<path:path>")
def browse(path=""):
    """Browse directory and list audio files + subfolders."""
    abs_path = os.path.join(MUSIC_DIR, path)
    abs_path = os.path.abspath(abs_path)

    # prevent escaping root
    if not abs_path.startswith(MUSIC_DIR):
        abs_path = MUSIC_DIR

    items = []
    for f in os.listdir(abs_path):
        full = os.path.join(abs_path, f)
        if os.path.isdir(full):
            items.append({"type": "dir", "name": f})
        elif f.lower().endswith((".mp3", ".wav", ".flac", ".ogg", "m4a")):
            items.append({"type": "file", "name": f})

    rel_path = os.path.relpath(abs_path, MUSIC_DIR)
    if rel_path == ".":
        rel_path = ""

    parent = os.path.dirname(rel_path) if rel_path else None

    return render_template(
        "index.html", files=items, current=rel_path, parent=parent
    )


@app.route("/play", methods=["POST"])
def play():
    global current_media, running, progress_thread, paused

    filename = request.json["filename"]
    rel_dir = request.json.get("directory", "")
    filepath = os.path.join(MUSIC_DIR, rel_dir, filename)

    media = instance.media_new(filepath)
    player.set_media(media)
    player.play()

    current_media = filepath
    paused = False

    if not running:
        running = True
        progress_thread = threading.Thread(target=progress_updater, daemon=True)
        progress_thread.start()

    return jsonify({"status": "playing", "file": filename})


@app.route("/stop", methods=["POST"])
def stop():
    global running, paused
    player.stop()
    running = False
    paused = False
    return jsonify({"status": "stopped"})


@app.route("/pause", methods=["POST"])
def pause():
    global paused
    if player.is_playing():
        player.pause()
        paused = True
        return jsonify({"status": "paused"})
    return jsonify({"status": "not playing"})


@app.route("/resume", methods=["POST"])
def resume():
    global paused
    if paused:
        player.pause()  # toggle back
        paused = False
        return jsonify({"status": "resumed"})
    return jsonify({"status": "not paused"})


@app.route("/seek", methods=["POST"])
def seek():
    pos = request.json.get("position", 0)
    player.set_time(pos * 1000)  # ms
    return jsonify({"status": "seeked", "position": pos})


@app.route("/status")
def status():
    if current_media and (player.is_playing() or paused):
        length = player.get_length() // 1000
        time_pos = player.get_time() // 1000

        if length > 0:
            # Clamp at length if near end
            if time_pos >= length - 1:
                time_pos = length
                # treat as stopped once fully reached
                return jsonify({
                    "file": os.path.basename(current_media),
                    "playing": False,
                    "paused": False,
                    "length": length,
                    "position": length
                })

        return jsonify({
            "file": os.path.basename(current_media),
            "playing": player.is_playing(),
            "paused": paused,
            "length": length,
            "position": time_pos
        })
    return jsonify({"playing": False, "paused": False})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
