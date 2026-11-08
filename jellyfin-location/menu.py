"""Kodi side-panel tile: choose where Jellyfin/Seerr point (auto / home / away).

Run from Kodi: RunScript(/storage/kodi-config/jellyfin-location/menu.py)
Saves the choice (survives restarts) and, when that means a switch, restarts
Kodi so jf_location.py can rewrite the settings while Kodi is stopped.
"""
import os, subprocess, sys
import xbmc, xbmcgui

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import jf_location as jf

LABELS = {"auto": "Auto", "home": "Home", "away": "Away"}
TILE_LABEL = "Jellyfin: %s"

def set_tile_label(mode, now):
    # Find the tile that runs this script and update its label.
    for i in ("01", "02", "03", "04"):
        if "jellyfin-location/menu.py" in xbmc.getInfoLabel("Skin.String(OptionsTiles.%s.Onclick)" % i):
            label = TILE_LABEL % LABELS[mode]
            if mode == "auto" and now in ("home", "away"):
                label += " (%s)" % now
            xbmc.executebuiltin("Skin.SetString(OptionsTiles.%s.Label,%s)" % (i, label))

def main():
    conf = jf.load_conf()
    mode, now = jf.read_mode(), jf.current(conf)
    detected = jf.detect(conf) or now
    options = [
        ("auto", "Automatic - now: %s (home on the home network, otherwise internet)" % detected),
        ("home", "Always home (local server)"),
        ("away", "Always away (internet URLs)"),
    ]
    pick = xbmcgui.Dialog().select("Jellyfin server  [in use: %s]" % now,
                                   [o[1] for o in options],
                                   preselect=[o[0] for o in options].index(mode))
    if pick < 0:
        return
    new_mode = options[pick][0]
    jf.write_mode(new_mode)
    target = detected if new_mode == "auto" else new_mode
    set_tile_label(new_mode, target)
    if target == now:
        xbmcgui.Dialog().notification("Jellyfin", "%s - already %s" % (LABELS[new_mode], now),
                                      xbmcgui.NOTIFICATION_INFO, 3000)
        return
    msg = "Switch Jellyfin to %s?[CR]Kodi restarts (about 15 seconds)." % target
    if xbmc.Player().isPlaying():
        msg += "[CR][B]Playback will stop.[/B]"
    if xbmcgui.Dialog().yesno("Jellyfin", msg, nolabel="Later", yeslabel="Restart now"):
        # systemd runs the restart; ExecStartPre (jf_location.py auto) switches.
        subprocess.Popen(["systemctl", "restart", "--no-block", "kodi"])
    else:
        xbmcgui.Dialog().notification("Jellyfin", "Switches at the next start", xbmcgui.NOTIFICATION_INFO, 3000)

main()
