# Updating Kodi add-ons without losing your tweaks

Updating an add-on or skin **replaces its files**, so any edit made inside it is gone afterwards. This is the routine that makes that harmless. It works for any box; the commands assume the repo is installed at `/storage/kodi-config` (see the top-level README).

## What survives an update, and what doesn't
| Survives (lives in your user data) | Gone after an update of that add-on |
|---|---|
| Keymaps (`userdata/keymaps/`), Kodi settings, profiles, library databases | Edits inside the skin (`addons/skin.arctic.fuse.3/…`) |
| Skin settings and Skin Variables menu/widget definitions (`addon_data/…`) | Edits inside other add-ons (`addons/plugin.video.…/…`) |
| Add-on logins and settings (`addon_data/<id>/`) | |

Everything in the right-hand column is what `reapply.sh` puts back.

## One-time setup
1. **Updates notify only.** Settings → System → Add-ons → Updates → *Notify, but don't install updates*. (Check *Updates* in the Add-ons menu now and then.)
2. Install this repo on the box and run `sh /storage/kodi-config/reapply.sh status` once. Everything should say `applied`; that is your baseline.

## Each time you update
1. **Pause or stop playback.** An update can reload parts of Kodi, so do it while nothing is playing.
2. **Back up.** Copy `/storage/.kodi/userdata` and the add-ons you are about to update (for example `tar czf /storage/backup-$(date +%Y%m%d).tgz -C /storage/.kodi userdata addons/<id>`).
3. **Update one add-on at a time** (Add-ons → *Available updates*), most important last. Never update the skin together with other things.
4. Run `sh /storage/kodi-config/reapply.sh status`.
   * `pending`: the update removed an edit. Go to step 5.
   * `BROKEN`: the add-on changed the spot the patch attaches to. **Nothing was forced.** Adjust that patch (see the README of the folder) or leave that add-on's tweak out until you have.
   * `MANUAL`: a tweak that cannot be re-created automatically; the output says how to redo it.
5. `sh /storage/kodi-config/reapply.sh apply`. It backs up each changed file first.
6. Follow the "NEXT" lines it prints: for the skin, rebuild the Skin Variables templates if told to and reload the skin; for add-ons, restart Kodi. **Only when nothing is playing.**
7. Look at the screens the patches touch (Home, a library, the play bar) and the Kodi log for errors before going on to the next add-on.

## Roll back
* A single file: copy it back from the `backup-…-pre-apply-<date>` folder the tool printed.
* A whole add-on: with Kodi stopped, put back the add-on folder from the backup you made in step 2 (`tar xzf` it over `/storage/.kodi`). Don't count on Kodi keeping the old version for you.
* Settings: unpack your `userdata` backup over `/storage/.kodi/userdata` with Kodi stopped.

## Hints
* **Skin updates are the risky ones.** A skin update can move or rewrite the lines the skin patches attach to, and it also changes many files. Try a skin update on a *copy* of the skin folder first: `python3 arctic-fuse-3/af3_patch.py status --skin /path/to/copy`.
* Keep a note of the version each patch was tested on (the folder READMEs do). A patch that still says `applied` after an update means the add-on author left that file alone.
* A patch that is no longer needed (the author fixed it) can simply be deleted from the list.
