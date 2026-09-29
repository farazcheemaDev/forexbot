# Azure portal > VM > Run command >
# RunShellScript
# UPDATE THE COMBINATION BOOK, 2026-09-29
# 1. held MN coins are priced, not dropped
# 2. the fair H1 line in --status
# 3. rebuild_equity.py knows all 7 books
# Restarts combo-paper ONLY. blend-paper
# is not touched: blend_paper.py did not
# change, and the check below proves it.
# The pull overwrites TRACKED files only;
# book state and trade logs are untouched
# and combo_state.json is copied first.
# Lines under 44 chars, no backslashes:
# Run command wraps near 50 and a wrapped
# tail RUNS as a command.
cd /opt/forexbot
set -e
export SYSTEMD_PAGER=cat
P=./.venv/bin/python
N=combo-paper
U1=https://github.com/farazcheemaDev
U2=/forexbot.git
T=$(date -u +%Y%m%d-%H%M%S)
OWNER=$(stat -c %U blend_paper.py)
echo ==1-BACKUP==
cp logs/combo_state.json logs/cs.$T
echo ==2-PULL==
git remote set-url origin $U1$U2
git fetch -q origin
git reset -q --hard origin/main
git log -1 --oneline
echo ==3-VERIFY-BLOB-IDS==
G=git
B=$($G hash-object blend_paper.py)
B=$(echo $B|head -c 16)
test $B = 46ba2f55f75ab3d2
C=$($G hash-object combo_paper.py)
C=$(echo $C|head -c 16)
test $C = ff46504686eac69d
M=$($G hash-object mn_paper.py)
M=$(echo $M|head -c 16)
test $M = 43c6781cee554e73
R=$($G hash-object rebuild_equity.py)
R=$(echo $R|head -c 16)
test $R = 679d86c6b751e66e
echo BLOBS_OK-blend_paper-unchanged
chown -R $OWNER:$OWNER /opt/forexbot
echo ==4-TESTS-stop-here-if-any-fail==
for X in mn_held rebuild_equity combo_paper
do
F=tests/test_$X.py
K=ok
sudo -u $OWNER $P $F >/tmp/t 2>&1||K=FAIL
tail -2 /tmp/t
test $K = ok
done
echo ==5-RESTART-COMBO-ONLY==
systemctl restart $N
sleep 150
systemctl is-active $N
journalctl -u $N -n 60 >/tmp/c||true
grep -e rror -e raceback /tmp/c|head -5
echo errors-above-if-any
echo ==6-THE-BOOK==
sudo -u $OWNER $P combo_paper.py --status
echo ==7-CORRECTED-EQUITY==
sudo -u $OWNER $P rebuild_equity.py
