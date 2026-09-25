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
echo ==BOOK-BLOB-IDS==
# NOT sha256sum of the file: this repo
# stores wick_paper.py with LF and the
# other two with CRLF, so a Windows disk
# hash never matches a Linux checkout.
# A blob id is the same on every OS.
git rev-parse --short HEAD:blend_paper.py
git rev-parse --short HEAD:combo_paper.py
git rev-parse --short HEAD:wick_paper.py
echo ==FILES-MATCH-THEIR-COMMIT==
git diff --stat HEAD -- blend_paper.py
git diff --stat HEAD -- combo_paper.py
git diff --stat HEAD -- wick_paper.py
echo nothing-above-means-they-match
echo ==UNCOMMITTED-ON-THE-BOX==
git status --porcelain | head -20
echo ==DONE==
