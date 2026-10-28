# kodi-config

My Kodi / CoreELEC configuration, tweaks and tools, kept per skin and per device so the same setup can be reused on more than one box.

| Folder | What's in it |
|---|---|
| [`arctic-fuse-3/`](arctic-fuse-3/README.md) | A patch tool for the Arctic Fuse 3 skin: sort buttons, sideways poster wall, resume on short press, play bar fixes. Survives skin updates (re-apply with one command). |
| [`addon-patches/`](addon-patches/README.md) | The same kind of tool for small edits to Retrospect (NPO), Jellyfin and KodiSeerr: re-applied after an add-on update, `BROKEN` instead of forcing when the add-on changed. |
| [`UPDATING.md`](UPDATING.md) | **How to update add-ons without losing tweaks**: what survives, the backup / update / re-apply routine, rollback. `reapply.sh` runs both patch tools. |
| [`keymaps/`](keymaps/remote-tweaks.xml) | Kodi key mappings: Up/Down show the play bar during playback for both an IR remote and a TV remote over HDMI-CEC. |
| [`devices/`](devices/) | Notes per device (hardware, OS version, what was tested where). Currently: [Ugoos AM9 Pro](devices/ugoos-am9-pro/README.md). |

Everything here is plain files you can read before using. No credentials, no personal data. Each folder has its own README with install and rollback steps.

## Install on the device (and re-apply after updates)
```sh
tar --exclude=.git -cf - . | ssh root@<device> 'mkdir -p /storage/kodi-config && cd /storage/kodi-config && tar -xf -'
ssh root@<device> 'sh /storage/kodi-config/reapply.sh status'     # read-only report
ssh root@<device> 'sh /storage/kodi-config/reapply.sh apply'      # apply what is pending (backs up first)
```
Needs only `python3` on the device. `reapply.sh` runs the skin patcher and the add-on patcher and never restarts anything; the routine for a safe update is in [`UPDATING.md`](UPDATING.md).

New box or skin? Add a folder under `devices/` or next to `arctic-fuse-3/` and link it in the table above.

License: MIT, see [`LICENSE`](LICENSE).

## Keeping it clean (for contributors, and for me)
This repo is public, so a pre-commit hook blocks IP addresses, MAC addresses, passwords/tokens, private keys, email addresses, home-directory paths, credentials in URLs and files like `guisettings.xml`. Enable it once after cloning:

```sh
git config core.hooksPath .githooks
.githooks/pre-commit --all     # scan every tracked file
```

Put strings that must never be published (your username, hostnames) in the untracked file `.git/secret-denylist`, one per line. A false positive can be allowed by adding `secret-ok` on that line. Needs only `bash` and `grep`.
