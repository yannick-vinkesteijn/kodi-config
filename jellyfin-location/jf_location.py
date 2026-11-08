#!/usr/bin/env python3
"""Point Kodi's Jellyfin (and Seerr) add-ons at the LAN or the public URL.

Kodi stores the Jellyfin server URL in the add-on settings *and* in every
library path and artwork URL, so changing the add-on setting alone leaves
posters and playback pointing at the old address. This rewrites all of them.

    jf_location.py status          read-only: where things point now
    jf_location.py auto            home if the LAN server answers with the
                                   right server id, otherwise away
    jf_location.py home|away       force one
    jf_location.py --dry-run ...   show what would change
    The side panel tile (menu.py) can pin auto to home or away; that choice
    is kept in /storage/.config/jellyfin-location.mode.

Kodi must NOT be running for auto/home/away (it keeps settings in memory and
writes them back on exit). Meant to run as ExecStartPre of kodi.service; to
switch by hand: `systemctl restart kodi`.

Settings: /storage/.config/jellyfin-location.conf (KEY=value lines):
    HOME_JELLYFIN=http://<lan ip>:8096
    AWAY_JELLYFIN=https://jellyfin.example.org
    SERVER_ID=<Id from <url>/System/Info/Public>
    HOME_SEERR=http://<lan ip>:5055        (optional)
    AWAY_SEERR=https://seerr.example.org   (optional)
"""
import glob, json, os, re, shutil, sqlite3, sys, time, urllib.request

CONF = os.environ.get("JF_LOCATION_CONF", "/storage/.config/jellyfin-location.conf")
# auto | home | away, set from the Kodi side panel (menu.py); survives restarts
MODE_FILE = os.environ.get("JF_LOCATION_MODE", "/storage/.config/jellyfin-location.mode")
USERDATA = os.environ.get("KODI_USERDATA", "/storage/.kodi/userdata")
BACKUPS = os.environ.get("JF_LOCATION_BACKUPS", "/storage/backup-jellyfin-location")
KEEP_BACKUPS = 3

def log(msg):
    print("jf-location: " + msg, flush=True)

def load_conf():
    conf = {}
    with open(CONF) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                conf[k.strip()] = v.strip().strip('"').rstrip("/")
    for k in ("HOME_JELLYFIN", "AWAY_JELLYFIN", "SERVER_ID"):
        if not conf.get(k):
            sys.exit("jf-location: %s missing in %s" % (k, CONF))
    return conf

# --- where the URLs live -------------------------------------------------
def text_files():
    a = os.path.join(USERDATA, "addon_data")
    return [os.path.join(a, "plugin.video.jellyfin", "settings.xml"),
            os.path.join(a, "plugin.video.jellyfin", "data.json"),
            os.path.join(a, "plugin.video.kodiseerr", "settings.xml")]

DB_COLUMNS = [("MyVideos*.db", "path", "strPath"),
              ("MyVideos*.db", "art", "url"),
              ("Textures*.db", "texture", "url")]

def newest(pattern):
    files = glob.glob(os.path.join(USERDATA, "Database", pattern))
    files = [f for f in files if re.search(r"\d+\.db$", f)]
    return max(files, key=lambda f: int(re.search(r"(\d+)\.db$", f).group(1))) if files else None

def pairs(conf, target):
    """(old, new) prefixes to replace for this target."""
    other = "away" if target == "home" else "home"
    out = [(conf[other.upper() + "_JELLYFIN"], conf[target.upper() + "_JELLYFIN"])]
    if conf.get("HOME_SEERR") and conf.get("AWAY_SEERR"):
        out.append((conf[other.upper() + "_SEERR"], conf[target.upper() + "_SEERR"]))
    return out

# --- detection -----------------------------------------------------------
def lan_server_ok(conf, wait):
    """True if the LAN URL answers with our server id within `wait` s."""
    deadline = time.time() + wait
    while True:
        try:
            with urllib.request.urlopen(conf["HOME_JELLYFIN"] + "/System/Info/Public", timeout=2) as r:
                return json.load(r).get("Id") == conf["SERVER_ID"]
        except Exception:
            if time.time() >= deadline:
                return False
            time.sleep(1)

def own_networks():
    """IPv4 networks of this box's interfaces (lo excluded), via `ip`."""
    import ipaddress, subprocess
    try:
        out = subprocess.run(["ip", "-4", "-o", "addr", "show"], capture_output=True, text=True).stdout
    except OSError:
        return None
    nets = []
    for m in re.finditer(r"^\d+:\s+(\S+)\s+inet\s+(\S+)", out, re.M):
        if m.group(1) != "lo":
            nets.append(ipaddress.ip_interface(m.group(2)).network)
    return nets

def detect(conf):
    """'home', 'away' or None (no network). Fast: only probes the server when
    the box is in the same subnet as the home server."""
    import ipaddress, urllib.parse
    host = urllib.parse.urlparse(conf["HOME_JELLYFIN"]).hostname
    try:
        home_ip = ipaddress.ip_address(host)
    except ValueError:
        home_ip = None                      # a hostname: just probe it
    deadline = time.time() + 20             # wait for Wi-Fi to get an address
    while True:
        nets = own_networks()
        if nets is None or home_ip is None:
            return "home" if lan_server_ok(conf, 8) else "away"
        if nets:
            break
        if time.time() >= deadline:
            return None
        time.sleep(1)
    if not any(home_ip in n for n in nets):
        return "away"                       # other network: no need to ask
    return "home" if lan_server_ok(conf, 3) else "away"

# --- status --------------------------------------------------------------
def count(conf):
    """{'home': n, 'away': n} occurrences of each Jellyfin base."""
    res = {"home": 0, "away": 0}
    for f in text_files():
        if os.path.exists(f):
            s = open(f, encoding="utf-8").read()
            for side in res:
                res[side] += s.count(conf[side.upper() + "_JELLYFIN"])
    for pattern, table, col in DB_COLUMNS:
        db = newest(pattern)
        if not db:
            continue
        c = sqlite3.connect("file:%s?mode=ro" % db, uri=True)
        for side in res:
            res[side] += c.execute('select count(*) from "%s" where "%s" like ?' % (table, col),
                                   (conf[side.upper() + "_JELLYFIN"] + "%",)).fetchone()[0]
        c.close()
    return res

def read_mode():
    try:
        m = open(MODE_FILE).read().strip()
    except OSError:
        return "auto"
    return m if m in ("auto", "home", "away") else "auto"

def write_mode(mode):
    tmp = MODE_FILE + ".tmp"
    with open(tmp, "w") as f:
        f.write(mode + "\n")
    os.replace(tmp, MODE_FILE)

def current(conf):
    c = count(conf)
    return "home" if c["home"] and not c["away"] else "away" if c["away"] and not c["home"] else "mixed"

def kodi_running():
    for p in glob.glob("/proc/[0-9]*/comm"):
        try:
            if open(p).read().strip() == "kodi.bin":
                return True
        except OSError:
            pass
    return False

# --- switch --------------------------------------------------------------
def backup(stamp):
    dest = os.path.join(BACKUPS, stamp)
    os.makedirs(dest, exist_ok=True)
    for f in text_files():
        if os.path.exists(f):
            shutil.copy2(f, os.path.join(dest, os.path.basename(os.path.dirname(f)) + "__" + os.path.basename(f)))
    for pattern in sorted({p for p, _, _ in DB_COLUMNS}):
        db = newest(pattern)
        if db:
            src = sqlite3.connect(db)
            dst = sqlite3.connect(os.path.join(dest, os.path.basename(db)))
            src.backup(dst)
            dst.close(); src.close()
    old = sorted(glob.glob(os.path.join(BACKUPS, "*")))
    for d in old[:-KEEP_BACKUPS]:
        shutil.rmtree(d, ignore_errors=True)
    return dest

def switch(conf, target, dry):
    """Databases first (each in one transaction), then the small text files,
    so a failure never leaves the add-on settings ahead of the library."""
    reps = pairs(conf, target)
    old, new = reps[0]
    changed = 0
    by_db = {}
    for pattern, table, col in DB_COLUMNS:
        db = newest(pattern)
        if db:
            by_db.setdefault(db, []).append((table, col))
    for db, cols in by_db.items():
        c = sqlite3.connect(db)
        try:
            with c:
                for table, col in cols:
                    where = '"%s" like ?' % col
                    n = c.execute('select count(*) from "%s" where %s' % (table, where), (old + "%",)).fetchone()[0]
                    if not n:
                        continue
                    changed += 1
                    log("%s %d rows in %s %s.%s" % ("would update" if dry else "update", n, os.path.basename(db), table, col))
                    if not dry:
                        # Replace only the prefix. "or ignore": if the new value
                        # already exists (unique index), keep the old row.
                        c.execute('update or ignore "%s" set "%s" = ? || substr("%s", ?) where %s'
                                  % (table, col, col, where), (new, len(old) + 1, old + "%"))
        finally:
            c.close()
    for f in text_files():
        if not os.path.exists(f):
            continue
        s = open(f, encoding="utf-8").read()
        n = s
        for o, nw in reps:
            n = n.replace(o, nw)
        if n != s:
            changed += 1
            log("%s %s" % ("would update" if dry else "update", f))
            if not dry:
                tmp = f + ".jf-tmp"
                with open(tmp, "w", encoding="utf-8") as out:
                    out.write(n)
                shutil.copymode(f, tmp)
                os.replace(tmp, f)
    return changed

def main(argv):
    dry = "--dry-run" in argv
    args = [a for a in argv if a != "--dry-run"]
    mode = args[0] if args else "status"
    if mode not in ("status", "auto", "home", "away"):
        sys.exit(__doc__)
    conf = load_conf()

    if mode == "status":
        c = count(conf)
        log("now: %s (%d home refs, %d away refs); mode: %s; detected: %s"
            % (current(conf), c["home"], c["away"], read_mode(), detect(conf)))
        return

    if mode == "auto" and read_mode() != "auto":
        mode = read_mode()
        log("mode fixed to %s (side panel), not detecting" % mode)
    if mode == "auto":
        t0 = time.time()
        target = detect(conf)
        if target is None:
            log("no network after 20 s, leaving settings as they are")
            return
        log("detected: %s (%.1f s)" % (target, time.time() - t0))
    else:
        target = mode

    if not dry and kodi_running():
        sys.exit("jf-location: Kodi is running; stop it first (systemctl stop kodi) or restart it")

    reps = pairs(conf, target)
    c = count(conf)
    other = "away" if target == "home" else "home"
    if not c[other]:
        log("already %s, nothing to do" % target)
        return
    if not dry:
        log("backup in " + backup(time.strftime("%Y%m%d-%H%M%S")))
    n = switch(conf, target, dry)
    log("%s %s (%d places)" % ("would switch to" if dry else "switched to", target, n))

if __name__ == "__main__":
    main(sys.argv[1:])
