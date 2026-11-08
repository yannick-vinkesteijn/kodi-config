#!/usr/bin/env bash
# Pull a backup of a CoreELEC/LibreELEC box's /storage config to a server.
# Runs on the server (not on the box). The box only lets the backup key run
# one tar command (forced command in the box's /storage/.ssh/authorized_keys),
# so a stolen key can read the config but not change anything on the box.
#
# Usage:
#   kodi-box-backup.sh                 scheduled run: makes a weekly backup,
#                                      skipped if one newer than 6 days exists
#                                      or if the box is off; keeps KEEP_WEEKLY
#   kodi-box-backup.sh before <topic>  before a large change; kept until the
#                                      matching "after" succeeds
#   kodi-box-backup.sh after <topic>   once the change works: replaces this
#                                      week's weekly, then deletes the
#                                      before-<topic> backup
#
# Settings: ~/.config/kodi-box-backup.conf (shell syntax) or environment:
#   BOX=<box ip or hostname>           required
#   DEST=<backup folder>               required (make it mode 700: secrets inside)
#   KEY=~/.ssh/id_kodi_backup          SSH key allowed only the forced tar
#   KEEP_WEEKLY=4
set -euo pipefail

CONF=${KODI_BACKUP_CONF:-$HOME/.config/kodi-box-backup.conf}
# shellcheck source=/dev/null
[[ -r $CONF ]] && . "$CONF"
: "${BOX:?set BOX in $CONF}"
: "${DEST:?set DEST in $CONF}"
KEY=${KEY:-$HOME/.ssh/id_kodi_backup}
KEEP_WEEKLY=${KEEP_WEEKLY:-4}
mkdir -p "$DEST"

part=""                                   # global, so the EXIT trap can see it
trap '[[ -n $part ]] && rm -f "$part"' EXIT

log() { echo "$(date -Is) $*"; }
usage() { echo "usage: $0 [before|after <topic>]" >&2; exit 2; }

box_online() {
  # Port 22 open? (The forced command ignores whatever we ask it to run,
  # so a plain "ssh true" would start a full tar.)
  timeout 5 bash -c "</dev/tcp/$BOX/22" 2>/dev/null
}

# make_backup <name>: pull, verify and store $DEST/<name>.tar.gz
make_backup() {
  local name=$1 entries
  part=$DEST/.$name.tar.gz.part

  # The forced command on the box sends the tar; we only compress here.
  ssh -T -i "$KEY" -o BatchMode=yes -o ConnectTimeout=10 root@"$BOX" | gzip -6 > "$part"

  gzip -t "$part"
  entries=$(tar tzf "$part" | wc -l)
  if (( entries < 1000 )); then
    log "$name: only $entries entries, not kept" >&2
    exit 1
  fi
  # grep without -q: an early exit would SIGPIPE tar and fail the pipeline
  tar tzf "$part" | grep '^\.kodi/userdata/guisettings\.xml$' > /dev/null \
    || { log "$name: guisettings.xml missing, not kept" >&2; exit 1; }

  mv "$part" "$DEST/$name.tar.gz"
  part=""
  log "$name.tar.gz: $entries entries, $(du -h "$DEST/$name.tar.gz" | cut -f1)"
}

this_week() {
  find "$DEST" -maxdepth 1 -name 'storage-weekly-*.tar.gz' -mtime -6
}

rotate_weekly() {
  ls -1t "$DEST"/storage-weekly-*.tar.gz | tail -n +$((KEEP_WEEKLY + 1)) | xargs -r rm -f
}

stamp=$(date +%Y%m%d-%H%M)
mode=${1:-}
topic=${2:-}

case $mode in
  "")
    [[ -z $(this_week) ]] || exit 0
    # Box off (normal when it powers off instead of sleeping): try next run.
    box_online || { log "box $BOX offline, weekly backup postponed"; exit 0; }
    make_backup "storage-weekly-$stamp"
    rotate_weekly
    ;;
  before|after)
    [[ $topic =~ ^[A-Za-z0-9._-]+$ ]] || usage
    box_online || { log "box $BOX not reachable" >&2; exit 1; }
    if [[ $mode == before ]]; then
      make_backup "storage-$stamp-before-$topic"
    else
      replaced=$(this_week)
      make_backup "storage-weekly-$stamp"
      # Only reached when the new weekly is verified (set -e).
      for f in $replaced "$DEST"/storage-*-before-"$topic".tar.gz; do
        [[ -e $f ]] || continue
        rm -f "$f"
        log "removed $(basename "$f")"
      done
      rotate_weekly
    fi
    ;;
  *) usage ;;
esac
