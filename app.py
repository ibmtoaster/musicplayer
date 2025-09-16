import os
import vlc
import sys
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
    # Decode any %xx escapes from the URL
    safe_path = unquote(path)
    
    """Browse directory and list audio files + subfolders."""
    abs_path = os.path.join(MUSIC_DIR, safe_path)
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
def play_post():
    global player, current_media
    data = request.get_json()
    if not data or "filename" not in data:
        return ("Missing filename", 400)

    filepath = os.path.join(MUSIC_DIR, data["filename"])
    
    # Debug logging (always on)
    print(
        f"[DEBUG] filepath={filepath}",
        file=sys.stderr,
        flush=True
    )
    
    if os.path.isfile(filepath):
        media = instance.media_new(filepath)
        player.set_media(media)
        player.play()
        current_media = os.path.basename(filepath)
        #return ("", 204)
        return jsonify(success=True)

    return ("File not found", 404)

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
    global player
    data = request.get_json()

    if not data or "position" not in data:
        print("DEBUG /seek: No position provided", file=sys.stderr, flush=True)
        return jsonify(success=False, error="No position provided"), 400

    new_pos = float(data["position"])  # fraction between 0.0 and 1.0
    print(f"DEBUG /seek: ${new_pos}", file=sys.stderr, flush=True)
    if player is not None:
        player.set_position(new_pos)
        return jsonify(success=True)

    return jsonify(success=False, error="No active player")


@app.route("/status")
def status():
    global player, current_media
    state = player.get_state()
    length = player.get_length() // 1000 if current_media else 0
    time_pos = player.get_time() // 1000 if current_media else 0

    # Debug logging (always on)
    print(
        f"[DEBUG] state={state}, length={length}, time_pos={time_pos}, current_media={current_media}"
        f"is_playing={player.is_playing()}, paused={paused}",
        file=sys.stderr,
        flush=True
    )

    if current_media:
        # Case 1: VLC says playback ended
        if state == vlc.State.Ended:
            return jsonify({
                "file": os.path.basename(current_media),
                "playing": False,
                "paused": False,
                "ended": True,
                "length": 0,
                "position": 0,
                "song": current_media
            })

        # Case 2: VLC explicitly stopped
        if state == vlc.State.Stopped:
            return jsonify({
                "file": os.path.basename(current_media),
                "playing": False,
                "paused": False,
                "ended": False,
                "length": length,
                "position": 0
            })

        # Case 3: Normal playback or paused
        return jsonify({
            "file": os.path.basename(current_media),
            "playing": state == vlc.State.Playing,
            "paused": state == vlc.State.Paused,
            "ended": False,
            "length": length,
            "position": time_pos,
            "song": current_media
        })

    # Case 4: No media loaded
    return jsonify({"playing": False, "paused": False, "ended": False})

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
