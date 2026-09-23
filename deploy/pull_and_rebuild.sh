# Azure portal > VM > Run command >
# RunShellScript
# ONE PASTE, three jobs: pull the latest
# code, restart the books, then rebuild the
# corrected equity curve from the trade log.
# The rebuild is read-only. The pull only
# overwrites TRACKED files, so the book
# state files (gitignored) and their trades
# CSVs (never committed) are untouched.
# State is tarred up first regardless.
# If the self-check reports MISMATCH, read
# the timestamp it prints. If that is when
# the entry-sized fix landed, it is
# expected. Any other moment is a real
# failure.
cd /opt/forexbot
set -e
export SYSTEMD_PAGER=cat
P=./.venv/bin/python
S=logs
B=blend-paper
U1=https://github.com/farazcheemaDev
U2=/forexbot.git
T=bak-$(date -u +%Y%m%d-%H%M%S)
OWNER=$(stat -c %U blend_paper.py)
echo ==1-BACKUP==
tar czf $S/books.$T.tgz $S/blend_state*.json
ls -la $S/books.$T.tgz
echo ==2-PULL==
git remote set-url origin $U1$U2
git fetch origin
git reset --hard origin/main
git log --oneline -1
echo ==3-VERIFY==
H1=f37a6926e812c685
H2=7693d7ed6bf316d0
H3=01f9b5a67b2cd610
H4=7b3960fd72c494d9
H=$H1$H2$H3$H4
G=$(sha256sum blend_paper.py|head -c 64)
test $G = $H
echo HASH_OK
chown -R $OWNER:$OWNER /opt/forexbot
sudo -u $OWNER $P -m py_compile blend_paper.py
echo SYNTAX_OK
echo ==4-RESTART==
systemctl restart $B
sleep 120
systemctl is-active $B
journalctl -u $B -n 60 >/tmp/j||true
grep -e rror -e raceback /tmp/j||echo clean
echo ==5-REBUILD-THE-CURVE==
R=rebuild_equity.py
sudo -u $OWNER $P $R --show-ambiguity
echo ==6-FIVE-BOOKS==
A=blend_paper.py
sudo -u $OWNER $P $A --status>/tmp/s
grep -e equity -e BOOK /tmp/s|head -20
