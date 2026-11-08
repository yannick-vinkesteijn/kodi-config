#!/usr/bin/env python3
"""Download movies/episodes from your Jellyfin server to a USB stick or SD card
on the Kodi box, for watching offline (holiday, no internet).

Uses the login of the Jellyfin for Kodi add-on (no extra password) and the
server address it has now (works with ../jellyfin-location too).

    jf_download.py search <text>                 find movies / series
    jf_download.py get <text|id> [options]       download (original file + external subtitles)
        --season N         series: only this season
        --episodes A-B     series: only these episode numbers (with --season)
        --dest DIR         default: the only mounted disk under /var/media
        --dry-run          show what would be downloaded and the total size
        --bg               run in the background (log: /storage/logs/jf-download.log)
    jf_download.py list [--dest DIR]             what's on the disk + free space

Layout on the disk:  Movies/<Name> (<Year>)/<file>
                     Series/<Name>/Season NN/<file>
Partial downloads resume; complete files are skipped.
"""
import json, os, re, subprocess, sys, time, urllib.parse, urllib.request

DATA = os.environ.get("JF_DATA", "/storage/.kodi/userdata/addon_data/plugin.video.jellyfin/data.json")
LOG = "/storage/logs/jf-download.log"
CLIENT = 'MediaBrowser Client="jf-download", Device="Kodi box", DeviceId="jf-download", Version="1.0"'

# --- server --------------------------------------------------------------
def server():
    s = json.load(open(DATA))["Servers"][0]
    return s["address"].rstrip("/"), s["AccessToken"], s["UserId"]

def request(path, params=None, headers=None, method="GET"):
    base, token, _ = server()
    url = base + path + ("?" + urllib.parse.urlencode(params) if params else "")
    h = {"Authorization": CLIENT + ', Token="%s"' % token}
    h.update(headers or {})
    return urllib.request.urlopen(urllib.request.Request(url, headers=h, method=method), timeout=30)

def api(path, **params):
    with request(path, params) as r:
        return json.load(r)

def find(text, types="Movie,Series"):
    _, _, uid = server()
    if re.fullmatch(r"[0-9a-f]{32}", text):
        return [api("/Users/%s/Items/%s" % (uid, text))]
    return api("/Users/%s/Items" % uid, searchTerm=text, IncludeItemTypes=types, Recursive="true",
               Fields="ProductionYear,MediaSources,ChildCount", Limit=20).get("Items", [])

# --- helpers -------------------------------------------------------------
def human(n):
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return "%.1f %s" % (n, unit) if unit != "B" else "%d B" % n
        n /= 1024.0

def safe(name):
    return re.sub(r'[\\/:*?"<>|]', "_", name).strip(" .") or "untitled"

def default_dest():
    mounts = [l.split()[1] for l in open("/proc/mounts") if l.split()[1].startswith("/var/media/")]
    if len(mounts) != 1:
        sys.exit("jf-download: %d disks under /var/media (%s); pass --dest" % (len(mounts), ", ".join(mounts) or "none"))
    return mounts[0]

def free_bytes(path):
    st = os.statvfs(path)
    return st.f_bavail * st.f_frsize

# --- what to download ----------------------------------------------------
def plan(item, season=None, episodes=None):
    """List of (item, relative folder) for a movie or (part of) a series."""
    _, _, uid = server()
    if item["Type"] == "Movie":
        year = " (%s)" % item["ProductionYear"] if item.get("ProductionYear") else ""
        return [(item, os.path.join("Movies", safe(item["Name"] + year)))]
    if item["Type"] == "Series":
        params = dict(UserId=uid, Fields="MediaSources,Path")
        if season is not None:
            params["season"] = season
        eps = api("/Shows/%s/Episodes" % item["Id"], **params).get("Items", [])
        if episodes:
            a, b = episodes
            eps = [e for e in eps if a <= (e.get("IndexNumber") or 0) <= b]
        return [(e, os.path.join("Series", safe(item["Name"]), "Season %02d" % (e.get("ParentIndexNumber") or 0)))
                for e in eps if e.get("LocationType") != "Virtual"]
    sys.exit("jf-download: %s is a %s, not a movie or series" % (item["Name"], item["Type"]))

def details(item):
    """Full item with MediaSources (search results can be thin)."""
    if item.get("MediaSources"):
        return item
    _, _, uid = server()
    return api("/Users/%s/Items/%s" % (uid, item["Id"]))

def files_for(item, folder):
    """[(url_path, relative target, size)] for the video and its external subtitles."""
    item = details(item)
    src = item["MediaSources"][0]
    video = os.path.basename(src.get("Path") or "") or safe(item["Name"]) + "." + (src.get("Container") or "mkv")
    out = [("/Items/%s/Download" % item["Id"], os.path.join(folder, safe(video)), src.get("Size") or 0)]
    stem = os.path.splitext(safe(video))[0]
    for s in src.get("MediaStreams", []):
        if s.get("Type") == "Subtitle" and s.get("IsExternal"):
            codec = {"subrip": "srt"}.get((s.get("Codec") or "srt").lower(), (s.get("Codec") or "srt").lower())
            tag = "".join("." + t for t in (s.get("Language"), "forced" if s.get("IsForced") else None) if t)
            out.append(("/Videos/%s/%s/Subtitles/%d/0/Stream.%s" % (item["Id"], src["Id"], s["Index"], codec),
                        os.path.join(folder, "%s%s.%d.%s" % (stem, tag, s["Index"], codec)), 0))
    return out

# --- download ------------------------------------------------------------
def fetch(url_path, target, size):
    if size and os.path.exists(target) and os.path.getsize(target) == size:
        print("  have  %s" % target, flush=True)
        return
    os.makedirs(os.path.dirname(target), exist_ok=True)
    part = target + ".part"
    have = os.path.getsize(part) if os.path.exists(part) else 0
    headers = {"Range": "bytes=%d-" % have} if have else {}
    with request(url_path, headers=headers) as r:
        if have and r.status != 206:
            have = 0                            # server ignored Range: start over
        total = size or (int(r.headers.get("Content-Length") or 0) + have)
        t0, done = time.time(), have
        last = t0
        with open(part, "ab" if have else "wb") as f:
            while True:
                chunk = r.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)
                done += len(chunk)
                if time.time() - last > 15:
                    rate = (done - have) / max(time.time() - t0, 1)
                    pct = " %3d%%" % (100 * done // total) if total else ""
                    print("  %s%s  %s/s  %s" % (human(done), pct, human(rate), os.path.basename(target)), flush=True)
                    last = time.time()
    if size and os.path.getsize(part) != size:
        raise IOError("size %d != %d for %s (run again to resume)" % (os.path.getsize(part), size, target))
    os.replace(part, target)
    print("  done  %s (%s)" % (target, human(os.path.getsize(target))), flush=True)

def cmd_get(args):
    opts = {"season": None, "episodes": None, "dest": None, "dry": False, "bg": False}
    words = []
    it = iter(args)
    for a in it:
        if a == "--season": opts["season"] = int(next(it))
        elif a == "--episodes":
            a_, _, b_ = next(it).partition("-"); opts["episodes"] = (int(a_), int(b_ or a_))
        elif a == "--dest": opts["dest"] = next(it)
        elif a == "--dry-run": opts["dry"] = True
        elif a == "--bg": opts["bg"] = True
        else: words.append(a)
    if not words:
        sys.exit(__doc__)
    if opts["bg"]:
        os.makedirs(os.path.dirname(LOG), exist_ok=True)
        rest = [a for a in args if a != "--bg"]
        with open(LOG, "a") as log:
            p = subprocess.Popen([sys.executable, os.path.abspath(__file__), "get"] + rest,
                                 stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
        print("jf-download: running in the background (pid %d), log: %s" % (p.pid, LOG))
        return
    hits = find(" ".join(words))
    exact = [h for h in hits if h["Name"].lower() == " ".join(words).lower()]
    hits = exact if len(exact) == 1 else hits
    if len(hits) != 1:
        print("jf-download: %d matches; use the id:" % len(hits))
        show(hits)
        sys.exit(1)
    dest = opts["dest"] or default_dest()
    jobs = []
    for item, folder in plan(hits[0], opts["season"], opts["episodes"]):
        jobs += files_for(item, os.path.join(dest, folder))
    total = sum(s for _, _, s in jobs)
    print("%s %s: %d files, %s; free on %s: %s" % (time.strftime("%H:%M:%S"), hits[0]["Name"], len(jobs),
                                                 human(total), dest, human(free_bytes(dest))), flush=True)
    if opts["dry"]:
        for _, t, s in jobs:
            print("  %-9s %s" % (human(s) if s else "", os.path.relpath(t, dest)))
        return
    need = sum(s for _, t, s in jobs if not (os.path.exists(t) and os.path.getsize(t) == s))
    if need > free_bytes(dest):
        sys.exit("jf-download: needs %s, only %s free" % (human(need), human(free_bytes(dest))))
    for url, target, size in jobs:
        fetch(url, target, size)
    print("%s finished: %s" % (time.strftime("%H:%M:%S"), hits[0]["Name"]), flush=True)

def show(items):
    for h in items:
        src = (h.get("MediaSources") or [{}])[0]
        extra = human(src["Size"]) if src.get("Size") else ("%s episodes" % h["ChildCount"] if h.get("ChildCount") else "")
        print("  %s  %-6s %s%s  %s" % (h["Id"], h["Type"], h["Name"],
                                       " (%s)" % h["ProductionYear"] if h.get("ProductionYear") else "", extra))

def cmd_list(args):
    dest = args[args.index("--dest") + 1] if "--dest" in args else default_dest()
    for top in ("Movies", "Series"):
        base = os.path.join(dest, top)
        if not os.path.isdir(base):
            continue
        print(top + ":")
        for name in sorted(os.listdir(base)):
            size = sum(os.path.getsize(os.path.join(r, f)) for r, _, fs in os.walk(os.path.join(base, name)) for f in fs)
            print("  %-50s %s" % (name, human(size)))
    print("free on %s: %s" % (dest, human(free_bytes(dest))))

def main(argv):
    if not argv or argv[0] not in ("search", "get", "list"):
        sys.exit(__doc__)
    if argv[0] == "search":
        show(find(" ".join(argv[1:])))
    elif argv[0] == "get":
        cmd_get(argv[1:])
    else:
        cmd_list(argv[1:])

if __name__ == "__main__":
    try:
        main(sys.argv[1:])
    except urllib.error.HTTPError as e:
        sys.exit("jf-download: server said %d %s for %s" % (e.code, e.reason, e.url.split("?")[0]))
