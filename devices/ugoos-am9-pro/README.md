# Ugoos AM9 Pro (CoreELEC 22, eMMC)

Where these configs were developed and tested.

* **Hardware:** Ugoos AM9 Pro.
* **OS:** CoreELEC 22.0-Piers_rc1 installed to eMMC. See [dangerouslaser/ugoos-am9-pro-coreelec-emmc](https://github.com/dangerouslaser/ugoos-am9-pro-coreelec-emmc) for the install scripts.
* **Skin:** Arctic Fuse 3.4.0.
* **Tested with:** the box's IR remote and a TV remote over HDMI-CEC.

## Notes that apply to this box
* `python3` and `kodi-send` exist on CoreELEC, so [`../../arctic-fuse-3/af3_patch.py`](../../arctic-fuse-3/af3_patch.py) runs directly on the device (`scp` it to `/storage`).
* On CoreELEC 22 rc1, `cmp` and `diff` are not installed (BusyBox); use `md5sum` to compare files.
* A skin reload while a video is playing hung the box once; the patch tool therefore never reloads by itself.
* Turn Kodi's add-on updates to *Notify only* (Settings → System → Add-ons → Updates). An unattended Arctic Fuse update removes all skin edits.
* **Sleep (suspend) and an HDMI switch:** behind a 3-input HDMI switch the box suspended fine (the TV going off made Kodi request it), but twice it never woke again (blue LED, no network, only unplugging helped). The logs stopped right after the sleep script unloaded the Wi-Fi/USB drivers. With **Wi-Fi switched off** the next sleep/wake cycle resumed (kernel wake reason `0x2`, which I read as the IR remote). One cycle isn't proof, and I haven't isolated Wi-Fi as the cause; if you see a hang on resume, try with Wi-Fi off. A real power-off (`ShutDown()`) and starting it with the remote worked every time. The TV did not seem to wake the box through such a switch (my guess: its CEC wake doesn't pass), so rely on the remote.
* **Keep a persistent system log while debugging sleep/wake:** CoreELEC keeps the journal in RAM, so a hang loses it. A small systemd service that appends `journalctl -b -f` to a file under `/storage/logs` keeps it.
* Re-applying all patches after an update: see [`../../UPDATING.md`](../../UPDATING.md) and `reapply.sh` at the repo root.
