#!/usr/bin/env python3
"""Customisations for the Arctic Fuse 3 Kodi skin (tested on 3.4.0), kept as ONE definition.

Usage (on the box, python3 exists on CoreELEC):
    python3 af3_patch.py status            # read-only: which patches are applied / pending / broken
    python3 af3_patch.py apply             # apply every enabled patch that is pending (makes a backup first)
    python3 af3_patch.py apply --only ID   # just one patch
    python3 af3_patch.py list              # show all patches
    --skin PATH   use another skin folder (default /storage/.kodi/addons/skin.arctic.fuse.3)

It never reloads the skin or restarts anything. After `apply` it prints what to do:
  * `rebuild`  -> kodi-send --action="RunScript(script.skinvariables,action=buildtemplate,force)", wait ~3 min
  * `reload`   -> kodi-send --action="ReloadSkin()"  (only with NO video playing)

A patch is "applied" when its marker text is present in the file. A patch whose anchor can't be
found (skin changed that spot) is reported as BROKEN and is NOT applied; nothing else is touched.
"""
import argparse, os, re, shutil, sys, time
import xml.dom.minidom

HERE = os.path.dirname(os.path.abspath(__file__))
DEFAULT_SKIN = "/storage/.kodi/addons/skin.arctic.fuse.3"


def snippet(name):
    with open(os.path.join(HERE, "snippets", name)) as f:
        return f.read()


# ---------------------------------------------------------------- patch primitives
def insert_after_line(anchor, new_text):
    """Insert new_text (ends with newline) after the single line that contains `anchor`."""
    def fn(text):
        lines = text.split("\n")
        hits = [i for i, l in enumerate(lines) if anchor in l]
        if len(hits) != 1:
            raise LookupError("anchor found %d times: %r" % (len(hits), anchor))
        i = hits[0]
        return "\n".join(lines[:i + 1] + new_text.rstrip("\n").split("\n") + lines[i + 1:])
    return fn


def replace_once(old, new):
    def fn(text):
        if text.count(old) != 1:
            raise LookupError("text found %d times: %r" % (text.count(old), old))
        return text.replace(old, new)
    return fn


def regex_once(pattern, repl, flags=0):
    rx = re.compile(pattern, flags)
    def fn(text):
        out, n = rx.subn(repl, text)
        if n != 1:
            raise LookupError("regex matched %d times: %s" % (n, pattern))
        return out
    return fn


def osd_timer(text):
    """VideoOSD.xml: audio/subtitle/video-settings buttons must not cancel the auto-close timer."""
    marker = '<!-- AM9PRO-OSDTIMER: no CancelAlarm so the settings dialog can resume the auto-close timer -->'
    for bid in ("6006", "6007", "6008"):
        head = '<control type="button" id="%s">' % bid
        m = re.search(re.escape(head) + r".*?</control>", text, re.S)
        if not m:
            raise LookupError("button %s not found" % bid)
        blk = m.group(0)
        new = re.sub(r"[ \t]*<onclick>CancelAlarm\(osd_timeout,true\)</onclick>\n", "", blk, count=1)
        if new == blk:
            raise LookupError("button %s has no CancelAlarm onclick" % bid)
        new = new.replace(head, head + marker, 1)
        text = text.replace(blk, new)
    return text


def osd_timer3(num):
    """Custom_11xx OSD pop-ups (playlist, cast, info, audio/subtitle/video streams): restart the auto-close timer when they close."""
    block = ("    <!-- AM9PRO-OSDTIMER3 (2026-10-27): restart the OSD auto-close timer when this pop-up closes -->\n"
             '    <include content="Action_OSD_SuspendAutoClose">\n'
             '        <param name="window">%d</param>\n'
             "    </include>\n" % num)
    return insert_after_line("<defaultcontrol", block)


def profile_button(text):
    """Includes_ButtonMenu.xml: the Weather slot of the side panel shows the Kodi profile (picture + name); click = Switch user."""
    old_head = '''    <include name="ButtonMenu_Weather">
        <include content="ButtonMenu_Special_Button">
            <param name="id">$PARAM[id]</param>
            <param name="toplabel">$INFO[Weather.Temperature]</param>
            <param name="sublabel">$INFO[Weather.Conditions]</param>
            <param name="icon">$INFO[Weather.FanartCode,resource://resource.images.weathericons.white/,.png]</param>'''
    new_head = '''    <!-- AM9PRO-USERBUTTON (2026-10-27): the Weather slot shows the active Kodi profile (image + name); click = Switch user -->
    <variable name="AM9_ProfileIcon">
        <value condition="!String.IsEmpty(System.ProfileThumb)">$INFO[System.ProfileThumb]</value>
        <value>special://skin/extras/icons/address-card.png</value>
    </variable>
    <include name="ButtonMenu_Weather">
        <include content="ButtonMenu_Special_Button">
            <param name="id">$PARAM[id]</param>
            <param name="toplabel">$INFO[System.ProfileName]</param>
            <param name="sublabel">$LOCALIZE[31359]</param>
            <param name="icon">$VAR[AM9_ProfileIcon]</param>'''
    text = replace_once(old_head, new_head)(text)
    return replace_once("                <onclick>ActivateWindow(1161)</onclick>",
                        "                <onclick>ActivateWindow(1195)</onclick>")(text)


OSD_POPUPS = [("1140", "Playlist"), ("1141", "Cast"), ("1145", "InfoPanel"),
              ("1146", "AudioStreams"), ("1147", "SubtitleStreams"), ("1148", "VideoStreams")]


RESUME_ONCLICK = ('<onclick condition="String.IsEqual(ListItem.DBType,movie) | '
                  'String.IsEqual(ListItem.DBType,episode)">PlayMedia($ESCINFO[ListItem.FileNameAndPath],resume)'
                  '</onclick> <!-- AM9PRO-RESUME-ALL -->')

# ---------------------------------------------------------------- the patch list
# id, file (relative to skin), checks (all must be in the file when applied), apply function,
# reload kind, enabled, description
PATCHES = [
    dict(id="sort-buttons", file="1080i/MyVideoNav.xml", checks=["AM9PRO-SORT:"],
         fn=insert_after_line("<include>View_Main</include>", snippet("sort-buttons.xml")),
         after="reload", doc="Sort + order buttons above the poster wall (movies/shows)"),
    dict(id="wall-sort-up", file="1080i/Includes_Views_Wall.xml", checks=["<onup>SetFocus(6101)</onup>"],
         fn=insert_after_line("<onright>611</onright>",
                              "                        <onup>SetFocus(6101)</onup> <!-- AM9PRO-SORT -->\n"),
         after="reload", doc="Up from the top row of the wall focuses the sort button"),
    dict(id="wall-resume", file="1080i/Includes_Views_Wall.xml", checks=["AM9PRO-RESUME-ALL"],
         fn=insert_after_line("<onup>SetFocus(6101)</onup>", "                        " + RESUME_ONCLICK + "\n"),
         after="reload", needs=["wall-sort-up"], doc="Click on a movie/episode in the wall = resume"),
    dict(id="wall-horizontal", file="1080i/Includes_Views_Wall.xml", checks=["AM9PRO-HORIZONTAL"],
         fn=replace_once('<param name="orientation">vertical</param>',
                         '<param name="orientation">horizontal</param> <!-- AM9PRO-HORIZONTAL -->'),
         after="reload", doc="Poster wall scrolls sideways instead of down"),
    dict(id="row-resume", file="1080i/Includes_Views_Row.xml", checks=["AM9PRO-RESUME-ALL"],
         fn=insert_after_line("<pagecontrol>60</pagecontrol>", "                        " + RESUME_ONCLICK + "\n"),
         after="reload", doc="Click on a movie/episode in the rows = resume"),
    dict(id="combined-resume", file="1080i/Includes_Views_Combined.xml", checks=["AM9PRO-RESUME-ALL"],
         fn=regex_once(r"(<onclick condition=\"!Container\(53\$PARAM\[id\]\)\.ListItem\.IsFolder\">"
                       r"PlayMedia\(\$ESCINFO\[Container\(53\$PARAM\[id\]\)\.ListItem\.FileNameAndPath\])\)(</onclick>)",
                       r"\1,resume)\2 <!-- AM9PRO-RESUME-ALL -->"),
         after="reload", doc="Seasons/episodes combined view: click = resume"),
    dict(id="combined-wall-resume", file="1080i/Includes_Views_Combined_Wall.xml", checks=["AM9PRO-RESUME-ALL"],
         fn=regex_once(r"(<onclick condition=\"!Container\(56\$PARAM\[id\]\)\.ListItem\.IsFolder\">"
                       r"PlayMedia\(\$ESCINFO\[Container\(56\$PARAM\[id\]\)\.ListItem\.FileNameAndPath\])\)(</onclick>)",
                       r"\1,resume)\2 <!-- AM9PRO-RESUME-ALL -->"),
         after="reload", doc="Combined wall: click = resume"),
    dict(id="osd-timer", file="1080i/VideoOSD.xml", checks=["AM9PRO-OSDTIMER"], fn=osd_timer,
         after="reload", doc="Settings buttons in the play bar no longer cancel the auto-close timer"),
    dict(id="osd-timer2", file="1080i/Includes_Actions.xml", checks=["AM9PRO-OSDTIMER2"],
         fn=insert_after_line(
             "ClearProperty(osd_timeout_$PARAM[window],home)</onunload>",
             "        <!-- AM9PRO-OSDTIMER2: always restart the auto-close timer when a settings dialog closes over the OSD -->\n"
             "        <onunload condition=\"!String.IsEmpty(Skin.String(OSD_Timeout)) + Window.IsVisible(videoosd) + "
             "!System.HasAlarm(osd_timeout)\">AlarmClock(osd_timeout,RunScript(script.skinvariables,run_executebuiltin="
             "special://skin/shortcuts/builtins/skinvariables-closeosd.json,use_rules=True),"
             "$INFO[Skin.String(OSD_Timeout),00:,],silent)</onunload>\n"),
         after="reload", doc="Restart the play bar auto-close timer whenever a settings dialog closes"),
    dict(id="home-row-resume", file="shortcuts/generator/data/setup/widgets_row.xml",
         checks=["AM9PRO-RESUME", "InProgressMovies.xsp</condition>", "NewMovies.xsp</condition>",
                 "InProgressEpisodes.xsp</condition>"],
         fn=insert_after_line('<rules name="widget_custom_onclick">', snippet("widgets-resume-rules.xml")),
         after="rebuild", doc="Home rows Continue Watching / In-Progress / New Movies: click = resume"),
    dict(id="profile-button", file="1080i/Includes_ButtonMenu.xml", checks=["AM9PRO-USERBUTTON", "ActivateWindow(1195)"],
         fn=profile_button, after="reload",
         doc="Side panel: the weather slot shows the Kodi profile (picture + name); click = Switch user"),
]
# one patch per Custom_11xx pop-up (generated)
PATCHES += [
    dict(id="osd-timer3-%s" % n, file="1080i/Custom_%s_OSD_%s.xml" % (n, name), checks=["AM9PRO-OSDTIMER3"],
         fn=osd_timer3(int(n)), after="reload",
         doc="Pop-up %s over the play bar (%s): restart the auto-close timer when it closes" % (n, name))
    for n, name in OSD_POPUPS
]


# ---------------------------------------------------------------- engine
def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def state(skin, p, sim):
    """Status of one patch. `sim` carries the simulated text per file so that patches which build on
    an earlier pending patch in the same file are judged in order."""
    path = os.path.join(skin, p["file"])
    if not os.path.exists(path):
        return "MISSING-FILE"
    text = sim.get(p["file"])
    if text is None:
        text = read(path)
    if all(c in text for c in p["checks"]):
        sim[p["file"]] = text
        return "applied"
    try:
        sim[p["file"]] = p["fn"](text)
    except LookupError as e:
        sim[p["file"]] = text
        return "BROKEN (%s)" % e
    return "pending"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["status", "apply", "list"])
    ap.add_argument("--skin", default=DEFAULT_SKIN)
    ap.add_argument("--only")
    ap.add_argument("--backup-dir")
    a = ap.parse_args()

    if a.mode == "list":
        for p in PATCHES:
            print("%-22s %-8s %s  [%s]" % (p["id"], "enabled" if p.get("enabled", True) else "DRAFT", p["doc"], p["file"]))
        return 0

    ver = re.search(r'<addon[^>]*\sversion="([^"]+)"', read(os.path.join(a.skin, "addon.xml")))
    print("skin %s  (%s)" % (ver.group(1) if ver else "?", a.skin))
    todo, bad, sim = [], 0, {}
    for p in PATCHES:
        if a.only and p["id"] != a.only:
            continue
        st = state(a.skin, p, sim)
        on = p.get("enabled", True) or a.only == p["id"]
        print("  %-22s %-9s %s" % (p["id"], st if on else "(draft) " + st.split()[0], p["doc"]))
        if st.startswith(("BROKEN", "MISSING")) and on:
            bad += 1
        if st == "pending" and on:
            todo.append(p)
    if a.mode == "status":
        print("\n%d pending, %d broken" % (len(todo), bad))
        return 1 if bad else 0

    if not todo:
        print("\nnothing to apply")
        return 1 if bad else 0
    bdir = a.backup_dir or "/storage/backup-af3-pre-apply-" + time.strftime("%Y%m%d-%H%M%S")
    done, need = [], set()
    # group by file, apply in list order, validate XML, roll back that file on any error
    files = []
    for p in todo:
        if p["file"] not in files:
            files.append(p["file"])
    for rel in files:
        path = os.path.join(a.skin, rel)
        orig = read(path)
        text = orig
        applied_here = []
        try:
            for p in [q for q in todo if q["file"] == rel]:
                text = p["fn"](text)
                applied_here.append(p)
            xml.dom.minidom.parseString(text.encode("utf-8"))
        except Exception as e:  # noqa
            print("  !! %s: not changed (%s)" % (rel, e))
            bad += 1
            continue
        os.makedirs(os.path.dirname(os.path.join(bdir, rel)), exist_ok=True)
        shutil.copy2(path, os.path.join(bdir, rel))
        with open(path, "w", encoding="utf-8") as f:
            f.write(text)
        for p in applied_here:
            done.append(p["id"])
            need.add(p["after"])
    print("\napplied: %s" % (", ".join(done) or "none"))
    if done:
        print("backup of the changed files: %s" % bdir)
    if "rebuild" in need:
        print('NEXT: kodi-send --action="RunScript(script.skinvariables,action=buildtemplate,force)"   (wait ~3 min)')
    if need:
        print('THEN (no video playing!): kodi-send --action="ReloadSkin()"')
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
