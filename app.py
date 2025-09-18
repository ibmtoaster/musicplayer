import os, time
import vlc
from flask import Flask, request, jsonify, render_template, redirect, url_for
from urllib.parse import unquote
from CueParser import CueParser   # your parser

app = Flask(__name__)

MUSIC_ROOT = "/home/pi/Music"
vlc_instance = vlc.Instance()
player = vlc_instance.media_player_new()

current_dir = MUSIC_ROOT
current_cue = None
cue_parser = None
current_song = None
current_track = None

def is_audio_file(filename):
    extensions = [".mp3", ".flac", ".wav", ".aac", ".ogg", ".m4a"]
    return any(filename.lower().endswith(ext) for ext in extensions)

@app.route("/")
def root():
    return browse("")   # call browse with empty path directly

@app.route("/browse/", defaults={"path": ""})
@app.route("/browse/<path:path>")
def browse(path):
    abs_dir = os.path.join(MUSIC_ROOT, path)

    if not os.path.isdir(abs_dir):
        return f"Not a directory: {abs_dir}", 404

    entries = []
    for entry in os.scandir(abs_dir):
        entries.append({
            "name": entry.name,
            "is_dir": entry.is_dir(),
            "url": url_for("browse", path=os.path.join(path, entry.name)) if entry.is_dir() else None
        })

    breadcrumbs = _make_breadcrumb(path)
    return render_template("index.html",
                           entries=entries,
                           breadcrumbs=breadcrumbs,
                           current=abs_dir,
                           path=path)


def _make_breadcrumb(path: str):
    crumbs = [{
        "name": os.path.basename(MUSIC_ROOT) or "Music",
        "url": url_for("root")   # root crumb always goes to `/`
    }]

    if path:
        parts = path.strip("/").split("/")
        for i in range(len(parts)):
            crumb_path = "/".join(parts[:i+1])
            crumbs.append({
                "name": parts[i],
                "url": url_for("browse", path=crumb_path)
            })
    return crumbs

from urllib.parse import unquote
import time

# ensure these globals exist near the top of app.py:
# cue_parser = None
# current_cue = None
# current_song = None
# current_track = None
# player = vlc_instance.media_player_new()
# MUSIC_ROOT = "/home/pi/Music"

@app.route("/play", methods=["POST"])
def play():
    data = request.get_json()
    rel_path = data.get("file")

    if not rel_path:
        return jsonify({"error": "No file provided"}), 400

    abs_file = os.path.join(MUSIC_ROOT, rel_path)

    if not os.path.exists(abs_file):
        return jsonify({"error": f"File not found: {rel_path}"}), 404

    # Stop current playback first
    if player.is_playing():
        player.stop()

    # Handle .cue files
    if abs_file.lower().endswith(".cue"):
        from CueParser import CueParser
        cue = CueParser(abs_file)
        tracks = cue.get_tracks()
        if tracks:
            # Just load the first track for now
            media = vlc.Media(tracks[0]['file'])
            player.set_media(media)
        else:
            return jsonify({"error": "No tracks in cue"}), 400
    else:
        media = vlc.Media(abs_file)
        player.set_media(media)

    player.play()

    return jsonify({
        "status": "playing",
        "song": os.path.basename(abs_file),
        "path": rel_path
    })



@app.route("/pause", methods=["POST"])
def pause():
    player.pause()
    return jsonify({"status": "paused"})

@app.route("/stop", methods=["POST"])
def stop():
    player.stop()
    return jsonify({"status": "stopped"})

@app.route("/seek", methods=["POST"])
def seek():
    data = request.get_json()
    pos = float(data.get("position", 0))
    length = player.get_length()
    if length > 0:
        player.set_time(int(length * pos))
    return jsonify({"status": "seeked"})

@app.route("/status")
def status():
    global player, current_song, current_track, cue_parser, current_cue

    state = player.get_state()
    is_playing = player.is_playing()
    length = player.get_length() // 1000    # seconds
    pos = player.get_time() // 1000         # seconds
    paused = (state == vlc.State.Paused)

    song_name = current_song
    track_num = current_track

    # If we are inside a CUE track, override length/pos
    if cue_parser and current_cue and current_track:
        tracks = cue_parser.get_tracks()
        track = next((t for t in tracks if int(t["number"]) == int(current_track)), None)
        if track:
            start = int(track.get("index", 0)) // 1000   # ms -> sec
            end = int(track.get("end", length * 1000)) // 1000
            pos = max(0, pos - start)
            length = max(0, end - start)

    return jsonify({
        "state": str(state),
        "is_playing": is_playing,
        "paused": paused,
        "length": length,
        "pos": pos,
        "song": song_name,
        "track": track_num,
    })

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)