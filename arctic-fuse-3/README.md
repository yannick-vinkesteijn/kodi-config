# Arctic Fuse 3 tweaks

Small, reversible tweaks for the **Arctic Fuse 3** Kodi skin, packaged as one patch tool that survives skin updates. I use them on a Ugoos AM9 Pro running CoreELEC 22 (see [`../devices/ugoos-am9-pro`](../devices/ugoos-am9-pro/README.md)).

Nothing here is specific to that box: it works on any Kodi install that uses Arctic Fuse 3 and has `python3`. It was tested on **Arctic Fuse 3.4.0** only. This is a hobby project, not affiliated with Arctic Fuse 3, Kodi or CoreELEC, and it contains **no skin files**, only my own additions.

## What it changes

| Patch id | What you get |
|---|---|
| `sort-buttons` | A visible **sort** button and **ascending/descending arrow** above the poster wall of Movies / TV shows (no more digging through the menu). |
| `wall-sort-up` | Pressing **Up** on the top row of the wall focuses the sort button. |
| `wall-horizontal` | The poster wall **scrolls sideways** (rows of posters) instead of down. |
| `wall-resume`, `row-resume`, `combined-resume`, `combined-wall-resume` | A **short press on a movie or episode resumes** where you left off (no "Resume from… / Play from beginning" prompt). **Long press** still opens Kodi's menu, where "Play from beginning" / "Reset resume position" live. Covers the poster wall, rows, and the seasons/episodes combined views. |
| `home-row-resume` | Same for the home rows *Continue Watching*, *In-Progress* and *New Movies* (needs a skin rebuild, see below). |
| `osd-timer`, `osd-timer2` | Fixes the **play bar staying on screen** after you open the subtitle / audio / video settings from it (the skin cancelled the auto-close timer and never restarted it). |
| `osd-timer3-*` (one per pop-up) | The same fix for the pop-ups of the play bar itself (playlist, cast, info, audio / subtitle / video streams): the auto-close timer restarts when they close, so the bar no longer stays on screen after you back out of them. |
| `profile-button` | The **weather slot of the side panel** shows the active Kodi **profile** (picture + name); clicking it opens *Switch user*. Handy with more than one profile. |

`../keymaps/remote-tweaks.xml` makes **Up/Down during playback show the play bar** instead of skipping, for both the box's own remote (keyboard keys) and a TV remote over HDMI-CEC (`<remote>` buttons). Back = stop is a personal preference, delete it if you don't want it.

### Known limits
* Resume only applies to items Kodi knows as a movie or an episode. Clicking a *TV show* tile (not an episode) still uses Kodi's default select action.
* The plain list view and a few other layouts are not patched.
* Kodi's own prompt ("Resume from…") can still appear anywhere the skin does not start playback itself (for example search results or the info page).
* Tested on one box. Different Arctic Fuse versions may move the lines the patches attach to; the tool tells you when that happens (see `BROKEN` below).

## Install

Copy `af3_patch.py` and the `snippets/` folder to the device, for example:

```sh
mkdir -p /storage/af3-patches/patcher
scp -r arctic-fuse-3/af3_patch.py arctic-fuse-3/snippets root@<device>:/storage/af3-patches/patcher/
```

Copy `../keymaps/remote-tweaks.xml` to `/storage/.kodi/userdata/keymaps/` on the device and restart Kodi.

## Use

```sh
python3 /storage/af3-patches/patcher/af3_patch.py status     # read-only: applied / pending / BROKEN per patch
python3 /storage/af3-patches/patcher/af3_patch.py apply      # apply pending patches
python3 /storage/af3-patches/patcher/af3_patch.py list
python3 /storage/af3-patches/patcher/af3_patch.py apply --only osd-timer   # just one
```

* The default skin path is `/storage/.kodi/addons/skin.arctic.fuse.3`. Use `--skin PATH` for another location (also handy to try it on a copy first).
* `apply` backs up every file it changes to `/storage/backup-af3-pre-apply-<date>/`, checks the result is valid XML, and rolls a file back if anything fails.
* It **never reloads or restarts anything**. It prints what to do next:
  * `kodi-send --action="RunScript(script.skinvariables,action=buildtemplate,force)"` and wait ~3 minutes (only for `home-row-resume`), then
  * `kodi-send --action="ReloadSkin()"` — **only while nothing is playing** (on my box a skin reload during playback hung it).
* Patches are idempotent: running `apply` twice does nothing the second time.

### After a skin update
(Short version: `sh ../reapply.sh status` / `apply`; the full routine with backups and rollback is in [`../UPDATING.md`](../UPDATING.md).)

Updating Arctic Fuse 3 **replaces the skin files and removes every edit** (that is how I lost mine once). Set *Settings → System → Add-ons → Updates* to *Notify only* so it can't happen unannounced, then after you update by hand:

1. `status` shows what is pending or `BROKEN`.
2. `apply`, then rebuild / reload as printed.
3. A `BROKEN` patch means the line it anchors to moved. Open `af3_patch.py`, find the patch by id and adjust its anchor; the other patches are unaffected.

## How it works
Each patch in `af3_patch.py` is: a file in the skin, an anchor (a unique line or regex), what to insert/replace, and a marker comment that tells the tool it is already applied. That is more robust than copying whole files over the skin, because only the lines we own change. I verified that, starting from the untouched 3.4.0 files, the tool reproduces my working setup byte for byte.

## Safety
These edit files inside your Kodi add-on folder. Look at `af3_patch.py` before running it, keep the backups it makes, and try `--skin` on a copy first if you want to see the result. Use at your own risk.

## License
MIT, see `LICENSE`.
