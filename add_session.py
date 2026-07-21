"""practice-feed — add a practice session to the feed.

Run it, pick your recording, pick a cover picture, confirm the metadata.
The script then:

1. builds an MP3 with the picture embedded as cover art -> audio/
   (needs ffmpeg; without it, your audio file is copied unchanged)
2. copies the picture -> pictures/
3. adds the session to sessions.json (the feed reads this)
4. if this folder is a pushable git repo: commit + push = live

Requires Python 3.10+ with tkinter (included in the standard installer).
ffmpeg is optional but recommended: install it from ffmpeg.org and put it
on your PATH, or `pip install imageio-ffmpeg`.

No personal data leaves your machine except what you commit yourself.
"""

import json
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from tkinter import Tk, filedialog, messagebox, simpledialog

SITE_DIR = Path(__file__).parent
SESSIONS_JSON = SITE_DIR / "sessions.json"

AUDIO_TYPES = [("Audio files", "*.mp3 *.wav *.m4a *.aac *.flac *.ogg *.wma"), ("All files", "*.*")]
IMAGE_TYPES = [("Image files", "*.jpg *.jpeg *.png *.bmp *.webp *.svg"), ("All files", "*.*")]


def find_ffmpeg() -> str | None:
    try:
        from imageio_ffmpeg import get_ffmpeg_exe  # optional pip package
        return get_ffmpeg_exe()
    except ImportError:
        return shutil.which("ffmpeg")


def slugify(name: str) -> str:
    slug = re.sub(r"[^\w\-]+", "-", name, flags=re.UNICODE).strip("-").lower()
    return slug or "session"


def unique_id(slug: str, sessions: list[dict]) -> str:
    taken = {s["id"] for s in sessions}
    if slug not in taken:
        return slug
    n = 2
    while f"{slug}-{n}" in taken:
        n += 1
    return f"{slug}-{n}"


def parse_artist_song(stem: str) -> tuple[str, str]:
    """'Some Artist - Some Song [12]' -> ('Some Artist', 'Some Song').

    A trailing [NN] number is stripped. If there is no ' - ' separator,
    everything is treated as the song name.
    """
    name = re.sub(r"\s*\[\d+\]\s*$", "", stem).strip()
    if " - " in name:
        artist, song = name.split(" - ", 1)
        return artist.strip(), song.strip()
    return "", name


def audio_duration_seconds(ffmpeg: str, path: Path) -> float | None:
    result = subprocess.run([ffmpeg, "-i", str(path)], capture_output=True, text=True)
    match = re.search(r"Duration: (\d+):(\d+):(\d+\.?\d*)", result.stderr)
    if not match:
        return None
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def build_mp3_with_cover(ffmpeg: str, audio: Path, image: Path, output: Path,
                         artist: str = "", title: str = "", album: str = "") -> None:
    """Convert any audio to MP3 with the picture embedded as ID3 cover art."""
    audio_codec = ["-c:a", "copy"] if audio.suffix.lower() == ".mp3" else ["-c:a", "libmp3lame", "-b:a", "192k"]
    tags = []
    if artist:
        tags += ["-metadata", f"artist={artist}"]
    if title:
        tags += ["-metadata", f"title={title}"]
    if album:
        tags += ["-metadata", f"album={album}"]
    cover = [] if image.suffix.lower() == ".svg" else [
        "-i", str(image), "-map", "0:a", "-map", "1:v",
        "-c:v", "mjpeg", "-vf", "scale='min(1000,iw)':-2",
        "-metadata:s:v", "title=Album cover",
        "-metadata:s:v", "comment=Cover (front)",
    ]
    output.parent.mkdir(parents=True, exist_ok=True)
    cmd = [ffmpeg, "-y", "-i", str(audio), *cover, *audio_codec, *tags, "-id3v2_version", "3", str(output)]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(result.stderr[-2000:])


def load_sessions() -> list[dict]:
    if SESSIONS_JSON.exists():
        return json.loads(SESSIONS_JSON.read_text(encoding="utf-8"))
    return []


def save_sessions(sessions: list[dict]) -> None:
    SESSIONS_JSON.write_text(json.dumps(sessions, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def git_publish(title: str) -> str:
    """Commit and push the site if it lives in a git repo with a remote."""
    def git(*args: str) -> subprocess.CompletedProcess:
        return subprocess.run(["git", "-C", str(SITE_DIR), *args], capture_output=True, text=True)

    if git("rev-parse", "--is-inside-work-tree").returncode != 0:
        return "This folder is not a git repo — feed updated locally only."
    if not git("remote").stdout.strip():
        return "No git remote configured — feed updated locally only."

    git("add", "-A")
    commit = git("commit", "-m", f"practice.feed: {title}")
    if commit.returncode != 0:
        return "Nothing new to commit — feed updated locally only."
    # comments may have been committed remotely via the GitHub API, so integrate them first
    pull = git("pull", "--rebase")
    if pull.returncode != 0:
        git("rebase", "--abort")
        return f"Commit ok, but syncing with the remote failed:\n{pull.stderr.strip()[-500:]}"
    push = git("push")
    if push.returncode != 0:
        return f"Commit ok, but push failed:\n{push.stderr.strip()[-500:]}"
    return "Pushed — the session is live!"


def main() -> int:
    root = Tk()
    root.withdraw()
    root.attributes("-topmost", True)

    audio = filedialog.askopenfilename(parent=root, title="Select the audio (your session)", filetypes=AUDIO_TYPES)
    if not audio:
        print("Cancelled - no audio selected.")
        return 1
    audio = Path(audio)

    image = filedialog.askopenfilename(parent=root, title="Select the cover picture", filetypes=IMAGE_TYPES)
    if not image:
        print("Cancelled - no picture selected.")
        return 1
    image = Path(image)

    # metadata, pre-filled from the file name — Enter to accept, or correct it
    artist_guess, song_guess = parse_artist_song(audio.stem)
    artist = simpledialog.askstring("practice.feed", "Artist (incl. features):", initialvalue=artist_guess, parent=root)
    artist = artist_guess if artist is None else artist.strip()
    song = simpledialog.askstring("practice.feed", "Song:", initialvalue=song_guess, parent=root)
    song = song_guess if song is None else song.strip()
    session_input = simpledialog.askstring("practice.feed", "Session no:", initialvalue="", parent=root)
    session_number = int(session_input) if session_input and session_input.strip().isdigit() else None

    sessions = load_sessions()
    session_id = unique_id(slugify(audio.stem), sessions)
    picture = SITE_DIR / "pictures" / f"{session_id}{image.suffix.lower()}"

    ffmpeg = find_ffmpeg()
    if ffmpeg:
        out_audio = SITE_DIR / "audio" / f"{session_id}.mp3"
        print("Building MP3 with cover art...")
        try:
            build_mp3_with_cover(
                ffmpeg, audio, image, out_audio, artist=artist, title=song,
                album=f"Session {session_number}" if session_number is not None else "",
            )
        except RuntimeError as err:
            print("ffmpeg failed:\n", err)
            messagebox.showerror("practice.feed", f"MP3 creation failed:\n{err}", parent=root)
            return 1
        duration = audio_duration_seconds(ffmpeg, out_audio)
    else:
        out_audio = SITE_DIR / "audio" / f"{session_id}{audio.suffix.lower()}"
        out_audio.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(audio, out_audio)
        duration = None
        print("ffmpeg not found — audio copied unchanged (no cover art, no duration).")

    picture.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(image, picture)

    sessions.insert(0, {
        "id": session_id,
        "title": audio.stem,
        "artist": artist,
        "song": song or audio.stem,
        "session": session_number,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "audio": f"audio/{out_audio.name}",
        "picture": f"pictures/{picture.name}",
        "duration": round(duration, 1) if duration else None,
        "size": out_audio.stat().st_size + picture.stat().st_size,
    })
    save_sessions(sessions)
    print(f"Feed updated: {len(sessions)} sessions.")

    status = git_publish(audio.stem)
    print(status)
    messagebox.showinfo("practice.feed", f"Session added to the feed!\n\n{status}", parent=root)
    return 0


if __name__ == "__main__":
    sys.exit(main())
