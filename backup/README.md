# Box backup (pull to a server)

`kodi-box-backup.sh` runs on a Linux server, not on the box. It pulls `/storage` from a
CoreELEC/LibreELEC box (Kodi settings and library, add-ons including your patched ones,
`.config`, `.ssh`, network settings), stores it as a `.tar.gz` and checks it before keeping it.

The archives contain secrets (Kodi web password, add-on tokens, Wi-Fi password). Keep the
backup folder mode 700 and never publish it. CoreELEC itself (the system on the eMMC) is not
in the backup; reinstall that and then restore.

## Setup
1. On the server: `ssh-keygen -t ed25519 -N '' -f ~/.ssh/id_kodi_backup`
2. On the box, add the public key to `/storage/.ssh/authorized_keys` with a forced command,
   so this key can only read, never run anything else:
   ```
   command="cd /storage && tar cf - --exclude=.kodi/temp .kodi .config .ssh .cache",restrict ssh-ed25519 AAAA... kodi-backup
   ```
3. On the server, `~/.config/kodi-box-backup.conf`:
   ```sh
   BOX=<box ip or hostname>
   DEST=/path/to/backups/kodi-box     # chmod 700
   KEY=$HOME/.ssh/id_kodi_backup
   KEEP_WEEKLY=4
   ```
4. Copy the script to `~/bin/` and add a cron entry. If your box powers off instead of
   sleeping, run it every hour: a run does nothing when this week's backup exists or the
   box is off.
   ```
   15 * * * * $HOME/bin/kodi-box-backup.sh >> $HOME/logs/kodi-box-backup.log 2>&1
   ```

## Use
| Command | What it does |
|---|---|
| `kodi-box-backup.sh` | Weekly backup, skipped if one newer than 6 days exists or the box is off. Keeps `KEEP_WEEKLY`. |
| `kodi-box-backup.sh before <topic>` | Before a big change (CoreELEC update, skin/add-on patches). Kept until `after`. |
| `kodi-box-backup.sh after <topic>` | Once the change works: new weekly replaces this week's, then `before-<topic>` is deleted. If the change failed, don't run it; restore from the `before` file. |

Each backup must pass `gzip -t`, have more than 1000 files and contain `guisettings.xml`, or it is not kept.

## Restore
Box boots but settings or add-ons are broken (from a machine that can reach both):
```sh
ssh <server> cat <DEST>/<archive>.tar.gz \
  | ssh root@<box> 'systemctl stop kodi; cd /storage && tar xzf -'
ssh root@<box> reboot
```
This overwrites files from the backup; files added later stay. If the box doesn't boot,
reinstall CoreELEC (same version if you use kernel modules such as `dovi.ko`), enable SSH,
add your key, then restore as above. That also brings back the backup key.

**Test a restore** once, and after big changes: unpack into a test folder on the box and
compare `md5sum` lists with the live files (BusyBox has no `diff`/`cmp`).
