#!/usr/bin/env python3
"""Small edits to third-party Kodi add-ons (Retrospect, Jellyfin, KodiSeerr), kept as ONE definition.

Usage (on the box, python3 exists on CoreELEC):
    python3 addon_patch.py status            # read-only: applied / pending / BROKEN / MANUAL per patch
    python3 addon_patch.py apply             # apply every pending patch (makes a backup first)
    python3 addon_patch.py apply --only ID   # just one patch
    python3 addon_patch.py list
    --root PATH   add-ons folder (default /storage/.kodi/addons)

It never restarts anything. A patch is "applied" when its marker text is present in the file; a patch whose
anchor cannot be found (the add-on changed that spot) is reported as BROKEN and is NOT applied. A MANUAL patch
cannot be re-created automatically (no original text to anchor on): the tool only tells you whether it is still
present. After `apply`, restart Kodi (not while something is playing) so the Python files are reloaded.
"""
import argparse, os, shutil, sys, time, warnings

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_ROOT = "/storage/.kodi/addons"


def snippet(name):
    with open(os.path.join(HERE, "snippets", name), encoding="utf-8") as f:
        return f.read()


# ---------------------------------------------------------------- patch primitives
def _lines(new_text):
    """The lines of new_text exactly as written (one trailing newline ends the last line; more = blank lines)."""
    return (new_text[:-1] if new_text.endswith("\n") else new_text).split("\n")


def insert_after_line(anchor, new_text):
    """Insert new_text after the single line that contains `anchor`."""
    def fn(text):
        lines = text.split("\n")
        hits = [i for i, l in enumerate(lines) if anchor in l]
        if len(hits) != 1:
            raise LookupError("anchor found %d times: %r" % (len(hits), anchor))
        i = hits[0]
        return "\n".join(lines[:i + 1] + _lines(new_text) + lines[i + 1:])
    return fn


def insert_before_line(anchor, new_text):
    """Insert new_text (ends with a newline) before the single line that contains `anchor`."""
    def fn(text):
        lines = text.split("\n")
        hits = [i for i, l in enumerate(lines) if anchor in l]
        if len(hits) != 1:
            raise LookupError("anchor found %d times: %r" % (len(hits), anchor))
        i = hits[0]
        return "\n".join(lines[:i] + _lines(new_text) + lines[i:])
    return fn


def replace_n(old, new, count):
    """Replace `old` with `new`; it must occur exactly `count` times."""
    def fn(text):
        if text.count(old) != count:
            raise LookupError("text found %d times (expected %d): %r" % (text.count(old), count, old))
        return text.replace(old, new)
    return fn


# ---------------------------------------------------------------- the patch list
NOS = "plugin.video.retrospect/channels/channel.nos/nos2010/chn_nos2010.py"
DESC_OLD = '            item.description = image_data.get("description")'
DESC_NEW = ('            item.description = ", ".join(g["name"] for g in (result_set.get("genres") or []) '
            'if isinstance(g, dict) and g.get("name"))  # AM9 tweak 2026-10-27: genre names instead of NPO image labels')

PATCHES = [
    dict(id="retrospect-genres", file=NOS, checks=["AM9 tweak 2026-10-27: genre names instead of NPO image labels"],
         fn=replace_n(DESC_OLD, DESC_NEW, 3), tested="Retrospect 5.7.39",
         doc="NPO: the description under a programme is its genres (Retrospect shows an image label otherwise)"),
    dict(id="retrospect-buildid", file=NOS, checks=["AM9 tweak 2026-10-27: current Next.js build"],
         fn=insert_before_line("    def extract_nextjs_data(self", snippet("retrospect-buildid.py.txt")),
         tested="Retrospect 5.7.39",
         doc="NPO: saved links with an outdated site build id (npo.nl redeploys) no longer give an empty page"),
    dict(id="jellyfin-resume", file="plugin.video.jellyfin/jellyfin_kodi/entrypoint/default.py",
         checks=["AM9PRO 2026-10-17"],
         fn=insert_before_line("            Actions(server, api_client).play(", snippet("jellyfin-resume.py.txt")),
         tested="Jellyfin 2.2.0+py3",
         doc="Episodes started by Up Next resume from the server position when Kodi has no bookmark"),
    dict(id="kodiseerr-genre-ids", file="plugin.video.kodiseerr/media_utils.py", checks=["AM9PRO: discover lists only carry TMDB genre ids"],
         fn=insert_after_line("genres = join_names(item.get('genres', []))", snippet("kodiseerr-genre-ids.py.txt")),
         tested="KodiSeerr 4.6",
         doc="KodiSeerr discover lists show genre names (they only carry TMDB genre ids)"),
    dict(id="kodiseerr-info-text", file="plugin.video.kodiseerr/media_utils.py",
         checks=["AM9PRO: info text = description + genre only"], manual=True, tested="KodiSeerr 4.6",
         doc="MANUAL: the info text is description + 'Genre: ...' only. In media_utils.py, after `type_label = ...`, "
             "replace the block that builds `rich_plot` with: rich_plot = plot or \"\" ; "
             "if genres: rich_plot = (rich_plot + \"\\n\\n\" if rich_plot else \"\") + f\"Genre: {genres}\" "
             "(keep the comment `# AM9PRO: info text = description + genre only`)"),
]


# ---------------------------------------------------------------- engine
def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def state(root, p, sim):
    path = os.path.join(root, p["file"])
    if not os.path.exists(path):
        return "MISSING-FILE"
    text = sim.get(p["file"])
    if text is None:
        text = read(path)
    if all(c in text for c in p["checks"]):
        sim[p["file"]] = text
        return "applied"
    if p.get("manual"):
        sim[p["file"]] = text
        return "MANUAL"
    try:
        sim[p["file"]] = p["fn"](text)
    except LookupError as e:
        sim[p["file"]] = text
        return "BROKEN (%s)" % e
    return "pending"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["status", "apply", "list"])
    ap.add_argument("--root", default=DEFAULT_ROOT)
    ap.add_argument("--only")
    ap.add_argument("--backup-dir")
    a = ap.parse_args()

    if a.mode == "list":
        for p in PATCHES:
            print("%-22s %-20s %s" % (p["id"], p["tested"], p["doc"]))
        return 0

    todo, bad, sim = [], 0, {}
    for p in PATCHES:
        if a.only and p["id"] != a.only:
            continue
        st = state(a.root, p, sim)
        print("  %-22s %-10s %s" % (p["id"], st if len(st) < 12 else st.split()[0], p["doc"] if st != "applied" else ""))
        if st.startswith(("BROKEN", "MISSING", "MANUAL")):
            bad += 1
            if st.startswith("BROKEN"):
                print("      " + st)
        if st == "pending":
            todo.append(p)
    if a.mode == "status":
        print("\n%d pending, %d need attention" % (len(todo), bad))
        return 1 if bad else 0
    if not todo:
        print("\nnothing to apply")
        return 1 if bad else 0

    bdir = a.backup_dir or "/storage/backup-addon-patches-pre-apply-" + time.strftime("%Y%m%d-%H%M%S")
    files = []
    for p in todo:
        if p["file"] not in files:
            files.append(p["file"])
    done = []
    for rel in files:
        path = os.path.join(a.root, rel)
        text = read(path)
        here = []
        try:
            for p in [q for q in todo if q["file"] == rel]:
                text = p["fn"](text)
                here.append(p)
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                compile(text, path, "exec")  # the result must still be valid Python
        except Exception as e:  # noqa
            print("  !! %s: not changed (%s)" % (rel, e))
            bad += 1
            continue
        os.makedirs(os.path.dirname(os.path.join(bdir, rel)), exist_ok=True)
        shutil.copy2(path, os.path.join(bdir, rel))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        done += [p["id"] for p in here]
    print("\napplied: %s" % (", ".join(done) or "none"))
    if done:
        print("backup of the changed files: %s" % bdir)
        print("NEXT (no video playing!): restart Kodi so the add-ons reload their Python files")
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
