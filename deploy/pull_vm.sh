# Azure portal > VM > Run command >
# RunShellScript
# DEPLOY BY GIT PULL, now that the repo is
# public. This replaces the base64 paste
# scripts.
# It resets the remote to the clean public
# URL first, in case the old read-only PAT
# is still embedded in it.
# SAFE FOR THE LIVE BOOKS: reset --hard only
# overwrites TRACKED files. The state files
# of the paper books are gitignored and
# their trades CSVs are untracked, so
# neither is touched. The state files are
# tarred up first anyway.
# Short lines and no quotes and no
# backslashes, same rules as the paste
# scripts - a terminal copy still wraps near
# 50 chars.
cd /opt/forexbot
set -e
export SYSTEMD_PAGER=cat
P=./.venv/bin/python
S=logs
B=blend-paper
U1=https://github.com/farazcheemaDev
U2=/forexbot.git
STAMP=$(date -u +%Y%m%d-%H%M%S)
T=bak-$STAMP
OWNER=$(stat -c %U blend_paper.py)
echo ==1-BACKUP==
cp blend_paper.py $S/bp.$T
tar czf $S/books.$T.tgz $S/blend_state*.json
ls -la $S/books.$T.tgz
echo ==2-STATE-BEFORE==
git log --oneline -1
git status --short|head -20
echo ==3-CLEAN-REMOTE==
git remote set-url origin $U1$U2
git remote -v|head -1
echo ==4-FETCH-AND-RESET==
git fetch origin
git reset --hard origin/main
git log --oneline -3
echo ==5-VERIFY==
H1=cc028033ed5a2b4c
H2=bf15e8310f6c9800
H3=40333b0a8fb82116
H4=cb0d90b2e0e548c9
H=$H1$H2$H3$H4
G=$(sha256sum blend_paper.py|head -c 64)
test $G = $H
echo HASH_OK
grep -c rusd blend_paper.py
echo above-must-be-4-entry-sized-fix
grep -c TSTOP_BARS blend_paper.py
echo above-must-be-3-sixth-book
sudo -u $OWNER $P -m py_compile blend_paper.py
echo SYNTAX_OK
chown -R $OWNER:$OWNER /opt/forexbot
echo ==6-RESTART==
systemctl restart $B
sleep 150
systemctl is-active $B
journalctl -u $B -n 100 >/tmp/j||true
grep -e rror -e raceback /tmp/j||echo clean
grep -e TSTOP /tmp/j||echo tstop-quiet
A=blend_paper.py
sudo -u $OWNER $P $A --status>/tmp/s
tail -n 30 /tmp/s
