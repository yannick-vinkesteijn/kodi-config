# Add-on patches (Retrospect, Jellyfin, KodiSeerr)

Small edits to three third-party Kodi add-ons, packaged as one tool that **re-applies them after an add-on update**. Same idea as the Arctic Fuse 3 patcher next door: nothing is copied over a whole file, each patch finds its spot in the file as it is now, and the tool tells you when it can't.

Contains **no add-on code** except the few lines each patch adds. Not affiliated with the add-on authors. Tested on one box (CoreELEC 22, Kodi 21) with the add-on versions below.

| Patch id | Add-on (tested version) | What you get |
|---|---|---|
| `retrospect-genres` | Retrospect 5.7.39 (NPO channel) | The line under a programme shows its **genres** instead of an image label like "Bekijk de serie". |
| `retrospect-buildid` | Retrospect 5.7.39 (NPO channel) | NPO pages that were **empty** (saved links go stale each time npo.nl redeploys; the stale site build id gives a 404) load again. The patch swaps in the current build id. |
| `jellyfin-resume` | Jellyfin 2.2.0+py3 | Episodes started by **Up Next** resume from the Jellyfin server position when Kodi itself has no bookmark. |
| `kodiseerr-genre-ids` | KodiSeerr 4.6 | Discover lists show **genre names** (the API only sends TMDB genre ids there). |
| `kodiseerr-info-text` | KodiSeerr 4.6 | **MANUAL.** Info text = description + "Genre: …" only. The original code is not recorded, so the tool can only tell you whether it is still there; the list output says how to redo it. |

## Install
Copy the folder to the device and run with `python3` (CoreELEC has it):

```sh
scp -r addon-patches root@<device>:/storage/kodi-config/addon-patches
```

## Use
```sh
python3 addon_patch.py list
python3 addon_patch.py status               # read-only: applied / pending / BROKEN / MANUAL
python3 addon_patch.py apply                # apply what is pending
python3 addon_patch.py apply --only retrospect-buildid
python3 addon_patch.py status --root /some/copy/of/addons    # try it on a copy first
```
* `apply` backs up every file it changes to `/storage/backup-addon-patches-pre-apply-<date>/`, checks that the result is still valid Python, and leaves a file untouched if anything fails.
* It never restarts anything. After `apply`, restart Kodi (**not while something is playing**) so the add-ons reload their Python files.
* Idempotent: a second `apply` does nothing. A patch counts as applied when its marker comment is in the file.

## When a patch says BROKEN
The add-on changed the spot the patch attaches to (the message shows the line it looked for). The other patches are not affected. Open `addon_patch.py`, find the patch by id, and adjust its anchor, or re-do the edit by hand using the snippet in `snippets/`. If the add-on author fixed the problem themselves, delete the patch.

## How it was tested
For each patch I started from the original file (a backup made before the edit, or the file with the edit cut out), ran `apply`, and compared the result byte for byte with the file that had been running for weeks. All identical, a second `apply` changed nothing, and a renamed anchor was reported as BROKEN and not forced.
