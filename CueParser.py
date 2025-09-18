import re
import vlc

class CueParser:
    def __init__(self, cue_path):
        self.cue_path = cue_path
        self.tracks = []
        self._parse()

    def _parse(self):
        current_file = None
        with open(self.cue_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line.upper().startswith("FILE"):
                    # Example: FILE "album.flac" WAVE
                    parts = line.split('"')
                    if len(parts) > 1:
                        current_file = parts[1]
                elif line.upper().startswith("TRACK"):
                    track_num = int(line.split()[1])
                    self.tracks.append({
                        "number": track_num,
                        "file": current_file,
                        "title": None,
                        "index": 0
                    })
                elif line.upper().startswith("TITLE") and self.tracks:
                    parts = line.split('"')
                    if len(parts) > 1:
                        self.tracks[-1]["title"] = parts[1]
                elif line.upper().startswith("INDEX 01") and self.tracks:
                    # INDEX 01 mm:ss:ff (75 frames/sec)
                    timecode = line.split()[2]
                    mm, ss, ff = map(int, timecode.split(':'))
                    ms = (mm * 60 + ss) * 1000 + ff * (1000 // 75)
                    self.tracks[-1]["index"] = ms

    def get_tracks(self):
        """Return list of parsed tracks"""
        return self.tracks

    def play_track(self, track_num, vlc_instance):
        """Play a given track number using VLC instance"""
        track = next((t for t in self.tracks if t["number"] == track_num), None)
        if not track:
            raise ValueError(f"Track {track_num} not found in cue file")

        player = vlc_instance.media_player_new()
        media = vlc_instance.media_new(track["file"])
        player.set_media(media)
        player.play()
        # wait briefly so VLC starts playback before seeking
        import time
        time.sleep(0.2)
        player.set_time(track["index"])
        return player

if __name__ == "__main__":
    cue = CueParser("album.cue")
    for t in cue.get_tracks():
        print(f"Track {t['number']}: {t['title']} ({t['index']} ms) -> {t['file']}")

    # Play track 2
    instance = vlc.Instance()
    player = cue.play_track(2, instance)
