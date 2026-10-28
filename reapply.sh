#!/bin/sh
# Re-apply my Kodi customisations after an add-on or skin update.
#   sh reapply.sh status     read-only: what is applied / pending / BROKEN / MANUAL
#   sh reapply.sh apply      apply what is pending (backs up every changed file first)
# Runs the Arctic Fuse 3 skin patcher and the add-on patcher; never restarts anything.
set -u
HERE=$(cd "$(dirname "$0")" && pwd)
mode=${1:-status}
case "$mode" in status|apply) ;; *) echo "usage: sh reapply.sh status|apply" >&2; exit 2 ;; esac
rc=0
echo "== Arctic Fuse 3 skin"
python3 "$HERE/arctic-fuse-3/af3_patch.py" "$mode" || rc=1
echo
echo "== Add-ons (Retrospect, Jellyfin, KodiSeerr)"
python3 "$HERE/addon-patches/addon_patch.py" "$mode" || rc=1
echo
if [ "$rc" -ne 0 ]; then
  echo "Some patches need attention (BROKEN / MANUAL / MISSING above). Nothing was forced."
fi
exit $rc
