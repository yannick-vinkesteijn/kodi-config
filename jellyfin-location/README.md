# Jellyfin home / away switch

Use the LAN address of your Jellyfin (and Seerr) server at home and the public URL
(reverse proxy, Pangolin, Cloudflare tunnel, ...) when the box is somewhere else,
**automatically at every Kodi start**.

Why a script: the Jellyfin add-on writes the server URL into the add-on settings *and*
into every library path and artwork URL in Kodi's database (tens of thousands of rows).
Changing only the add-on's server setting leaves posters and playback on the old
address. This rewrites all of them, including the thumbnail cache, so cached posters
stay cached.

## How it decides (Auto)
Before Kodi starts:
1. Wait until the box has an IP address (max 20 s; if none, change nothing).
2. Box **not** in the home server's subnet (almost every other network) → away, instantly.
3. Box in the same subnet → ask `HOME_JELLYFIN/System/Info/Public`: answers with **your**
   server id → home (milliseconds), otherwise → away (≤5 s). So a holiday network that
   happens to use the same IP range doesn't fool it.

## Manual switch from the side panel (Arctic Fuse 3)
`menu.py` offers *Automatic / Always home / Always away*. The choice is saved in
`/storage/.config/jellyfin-location.mode` (kept across restarts); if it means a switch,
it asks and restarts Kodi. Turn one of the four side-panel tiles into it, no skin edit
needed (tile 04 here; `kodi-send` is on CoreELEC):
```sh
kodi-send --action="Skin.SetString(OptionsTiles.04.Include,Custom)"
kodi-send --action="Skin.SetString(OptionsTiles.04.Label,Jellyfin: Auto)"
kodi-send --action="Skin.SetString(OptionsTiles.04.Icon,special://skin/extras/icons/globe.png)"
kodi-send --action="Skin.SetString(OptionsTiles.04.Onclick,RunScript(/storage/kodi-config/jellyfin-location/menu.py))"
```
Undo: `Skin.SetString(OptionsTiles.04.Include,SystemInfo)` (or what it was). Other skins:
any button or favourite with that `RunScript(...)` works.

| What changes | Where |
|---|---|
| Jellyfin server | `addon_data/plugin.video.jellyfin/settings.xml`, `data.json` |
| Seerr URL (optional) | `addon_data/plugin.video.kodiseerr/settings.xml` |
| Library paths, artwork | `Database/MyVideos*.db` (`path.strPath`, `art.url`) |
| Thumbnail cache index | `Database/Textures*.db` (`texture.url`) |

Only the start of each value (the base URL) is replaced, so home → away → home gives
byte-identical databases (tested on a 24,000-item library).

## Install (CoreELEC / LibreELEC)
```sh
# repo already at /storage/kodi-config (see the top-level README)
cp /storage/kodi-config/jellyfin-location/jellyfin-location.conf.example /storage/.config/jellyfin-location.conf
vi /storage/.config/jellyfin-location.conf
python3 /storage/kodi-config/jellyfin-location/jf_location.py status
python3 /storage/kodi-config/jellyfin-location/jf_location.py --dry-run auto

mkdir -p /storage/.config/system.d/kodi.service.d
cp /storage/kodi-config/jellyfin-location/kodi-jellyfin-location.conf \
   /storage/.config/system.d/kodi.service.d/jellyfin-location.conf
systemctl daemon-reload
```

## Use
* Nothing: it runs before every Kodi start (so every boot). Or use the side-panel tile.
* Switch by hand (e.g. the box stayed on while you moved it): `systemctl restart kodi`,
  or `systemctl stop kodi; python3 .../jf_location.py away; systemctl start kodi`.
* `jf_location.py status` shows where things point now. `--dry-run` shows what would change.
* The log of each start: `journalctl -u kodi | grep jf-location`.

Each real switch first backs up the changed files and databases to
`/storage/backup-jellyfin-location/<time>/` (last 3 kept).

## Away from home
* The public URL must reach Jellyfin **without a login page in front** (Kodi can't
  click through an SSO screen). Check: `curl https://<public url>/System/Info/Public`.
* Bandwidth = your home upload speed. Lower the add-on's max bitrate or let Jellyfin
  transcode for 4K files.
* Items added to the library while away get the public URL; the next start at home
  switches them back.

## Uninstall
`rm /storage/.config/jellyfin-location.mode;` `rm /storage/.config/system.d/kodi.service.d/jellyfin-location.conf; systemctl daemon-reload`,
then `systemctl stop kodi; python3 .../jf_location.py home; systemctl start kodi` if you were away.
