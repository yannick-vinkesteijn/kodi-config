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
