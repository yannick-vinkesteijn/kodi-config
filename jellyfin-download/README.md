# Jellyfin downloads for offline viewing

The Jellyfin for Kodi add-on can't download; only the Jellyfin web and phone apps can.
`jf_download.py` does it on the Kodi box itself: it fetches the **original file** (no
transcoding) plus external subtitles to a USB stick or SD card, so you can watch
without internet (holiday, train). Play them in Kodi via *Videos → Files → <disk>*.

It uses the login the Jellyfin add-on already has (`plugin.video.jellyfin/data.json`),
so there's no extra password, and the server address the add-on uses now (works together
with [`../jellyfin-location`](../jellyfin-location/README.md)). Your Jellyfin user needs
the *Allow media downloading* permission (on by default for admins).

## Use (on the box, over SSH)
```sh
P="python3 /storage/kodi-config/jellyfin-download/jf_download.py"
$P search midsommar                       # id, type, name, year, size
$P get midsommar --dry-run                # what would be downloaded, total size, free space
$P get midsommar --bg                     # download in the background
tail -f /storage/logs/jf-download.log     # progress
$P get "<series id>" --season 2 --episodes 1-4 --bg
$P list                                   # what's on the disk + free space
```
* With several matches it lists them; use the id.
* Layout: `Movies/<Name> (<Year>)/<file>` and `Series/<Name>/Season NN/<file>`.
* Complete files are skipped; an interrupted file resumes where it stopped (`.part`).
  The final size is checked against the server.
* It refuses to start when the disk lacks space. `--dest DIR` if more than one disk is
  mounted under `/var/media`.
* Use the disk as **exFAT** so a Mac/PC can read it too (files > 4 GB are fine).
  On CoreELEC: `parted -s /dev/mmcblk1 mklabel msdos mkpart primary ntfs 1MiB 100%`
  then `mkfs.exfat -L <label> /dev/mmcblk1p1`. **Check the device first** (`cat
  /sys/block/mmcblk1/device/type` = `SD`); the eMMC with CoreELEC is usually `mmcblk0`.

Speed at home over Ethernet: about 30 MB/s (a 2-hour 1080p film in under a minute,
a 4K remux in a few minutes). Watched status of downloaded files stays in Kodi; it
doesn't sync back to Jellyfin.
