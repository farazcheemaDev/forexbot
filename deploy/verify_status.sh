#!/usr/bin/env bash
# READ-ONLY re-check of the facts docs/STATUS.md quotes. Run from the repo root on the PC (Git Bash):
#     bash deploy/verify_status.sh
# It SSHes to the VM (alias forexbot-vm, see CLAUDE.md s8) and only reads: systemctl, git, file times, the
# dashboard feed and the books' own --status. It writes nothing on the VM and restarts nothing.
# Afterwards, update the "Verified" line and any figure that moved in docs/STATUS.md.
# (Unlike status_digest.sh this is for ssh, not Azure Run command: no 4KB limit, no line-length rule.)
set -u
cd "$(dirname "$0")/.." || exit 1
KILL_LINE=261.30   # doc 22 s3b: the main account's KILL line at 2026-11-23 00:04 UTC

OUT=$(ssh -o ConnectTimeout=20 -o BatchMode=yes forexbot-vm 'bash -s' <<'REMOTE'
cd /opt/forexbot || exit 1
P=./.venv/bin/python
echo "VM time       $(date -u +%FT%TZ)"
echo "VM HEAD       $(git log -1 --format='%h %cI') | modified tracked files: $(git status --short | grep -vc '^??')"
echo "SERVICES"
for s in blend-paper combo-paper combo-bot-final combo-bot-fresh wick-paper pair-paper status-server \
         forexbot-dash.timer crowd-paper.timer analyst-paper.timer combo-bot-demo; do
  printf "  %-20s %s\n" $s "$(systemctl is-active $s)"
done
chk() { s=$1; shift   # file mtimes lie (a reset --hard rewrites them unchanged), so ask git what HEAD held at the start
  st=$(date -d "$(systemctl show $s -p ActiveEnterTimestamp --value)" +%s 2>/dev/null) || st=0
  at=$(git rev-parse -q --verify "HEAD@{$(date -u -d @$st '+%Y-%m-%d %H:%M:%S +0000')}" 2>/dev/null)
  bad=""; for f in "$@"; do git diff --quiet "$at" HEAD -- $f || bad="$bad $f"; done
  if [ -z "$at" ]; then r="unknown (no reflog entry)"; elif [ -z "$bad" ]; then r="OK: its files are unchanged since it started"
  else r="WARNING: changed since it started (restart pending):$bad"; fi
  printf "  %-16s started %s (HEAD then %s)  %s\n" $s "$(date -u -d @$st +%FT%TZ)" "${at:0:7}" "$r"; }
echo "PROCESS START vs CODE (files the service runs, at its start vs now)"
chk blend-paper blend_paper.py
chk combo-paper combo_paper.py blend_paper.py mn_paper.py
chk combo-bot-final combo_bot.py final_books.py wick_live.py news_books.py blend_paper.py mn_paper.py
chk combo-bot-fresh combo_bot.py final_books.py wick_live.py news_books.py blend_paper.py mn_paper.py
chk wick-paper wick_paper.py
chk pair-paper pair_live.py
echo "LIVE EQUITY (dashboard feed)"
for a in main fresh; do
  read t v < <(tail -n 1 logs/dashboard/eq_${a}_h.csv | tr , ' ')
  echo "  $a  \$$v at $(date -u -d @$t +%FT%TZ)"
done
echo "BOOKS (their own --status)"
echo " final main:";  $P combo_bot.py --mode dry --final --status 2>&1 | grep -E 'PAPER BOOK|account|made by' | cut -c1-150
echo " final fresh:"; $P combo_bot.py --mode dry --final --account fresh --status 2>&1 | grep -E 'PAPER BOOK|account|made by' | cut -c1-150
echo " v2 combo_paper:"; $P combo_paper.py --status 2>&1 | grep -E 'PAPER BOOK|account|made by' | cut -c1-150
echo " pair:"; $P pair_live.py --status 2>&1 | head -n 1 | cut -c1-150
echo " crash bids:"; $P wick_paper.py --status 2>&1 | grep -E 'BITGET   hour' | cut -c1-150
for f in blend_paper.py combo_paper.py wick_paper.py pair_live.py news_books.py news/crowd_paper.py combo_bot.py final_books.py wick_live.py; do
  echo "BLOB $f $(git rev-parse --short HEAD:$f)"
done
REMOTE
) || { echo "ssh to forexbot-vm failed - nothing verified"; exit 1; }

grep -v '^BLOB ' <<<"$OUT"
echo "LIVE EQUITY vs the main account's day-45 line (\$$KILL_LINE, read 2026-11-23 00:04 UTC, not before):"
awk -v l=$KILL_LINE '/^  main /{gsub(/\$/,"",$2); printf "  main is $%.2f -> %+.2f against the line\n", $2, $2-l}' <<<"$OUT"
echo "CODE IDENTITY"
git fetch -q origin 2>/dev/null
echo "  origin/main $(git rev-parse --short origin/main) | local HEAD $(git rev-parse --short HEAD) | local uncommitted tracked files: $(git status --short | grep -vc '^??')"
while read -r _ f b; do
  l=$(git rev-parse --short HEAD:"$f"); [ "$l" = "$b" ] && s="same as local HEAD" || s="DIFFERS from local HEAD ($l)"
  printf "  %-22s VM %s  %s\n" "$f" "$b" "$s"
done < <(grep '^BLOB ' <<<"$OUT")
echo "PC PROCESSES (python)"
powershell.exe -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { \$_.Name -like 'python*' } | ForEach-Object { '  ' + \$_.CommandLine }" 2>/dev/null | tr -d '\r' | cut -c1-150
echo "REAL-MONEY GATES"
grep -n '^ALLOW_REAL' combo_bot.py longtrend_bot.py micro_bot.py
