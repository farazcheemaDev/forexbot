# READ-ONLY. Answers: what is on the VM.
# Runs nothing, writes nothing, no restart.
# Lines under 44 chars: Run command wraps
# near 50 and a wrapped tail RUNS.
set -e
cd /opt/forexbot
export SYSTEMD_PAGER=cat
echo ==COMMIT-ON-THE-VM==
git log -1 --oneline
echo ==COMMITS-BEHIND-ORIGIN==
git fetch -q origin || true
git rev-list --count HEAD..origin/main
echo ==SERVICES==
for S in blend-paper combo-paper wick-paper
do
printf "%s " $S
systemctl is-active $S || true
done
echo ==BOOK-FILE-HASHES-first16==
sha256sum blend_paper.py | cut -c1-16
sha256sum combo_paper.py | cut -c1-16
sha256sum wick_paper.py | cut -c1-16
echo ==UNCOMMITTED-ON-THE-BOX==
git status --porcelain | head -20
echo ==DONE==
