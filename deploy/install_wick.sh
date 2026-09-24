# Azure portal > VM > Run command >
# RunShellScript
# Pulls the latest code, then installs
# and starts the CRASH-BID paper book
# (wick_paper.py, doc 16) beside the
# other books. It places NO orders and
# needs no keys. The pull does not touch
# the running books' code: BLEND and
# COMBO below must print 2c14463759c26e68
# and 2164809dc2ef2232.
# Every line is under 44 chars and there
# are no backslashes: Run command wraps
# long lines and decodes backslashes.
set -e
cd /opt/forexbot
export SYSTEMD_PAGER=cat
P=./.venv/bin/python
N=wick-paper
D=/etc/systemd/system
APP=$(pwd)
OWNER=$(stat -c %U blend_paper.py)
U1=https://github.com/farazcheemaDev
U2=/forexbot.git
echo ==1-BACKUP==
K=bak-$(date -u +%Y%m%d-%H%M%S)
tar czf logs/books.$K.tgz logs/*_state.json
echo ==2-PULL==
git remote set-url origin $U1$U2
git fetch origin
git reset --hard origin/main
git log --oneline -1
B=$(sha256sum blend_paper.py|head -c 16)
C=$(sha256sum combo_paper.py|head -c 16)
echo BLEND $B COMBO $C
echo ==3-VERIFY==
H1=c888754af0ca437f
H2=9bbcd3dc5941ecae
H3=c697c1bd687860a1
H4=a22b1aebb3a20245
H=$H1$H2$H3$H4
W=wick_paper.py
G=$(sha256sum $W|head -c 64)
test $G = $H
echo HASH_OK
chown -R $OWNER:$OWNER $APP
sudo -u $OWNER $P -m py_compile $W
echo SYNTAX_OK
X=tests/test_wick_paper.py
sudo -u $OWNER $P $X >/tmp/wt
tail -2 /tmp/wt
echo ==4-INSTALL==
T=/tmp/$N.service
F=deploy/$N.service
sed "s|__APP_DIR__|$APP|g" $F >$T
sed -i "s|__USER__|$OWNER|g" $T
cp $T $D/$N.service
systemctl daemon-reload
systemctl enable --now $N
echo ==5-CHECK==
sleep 170
systemctl is-active $N
free -m||true
journalctl -u $N -n 40 >/tmp/w||true
grep -e rror -e raceback /tmp/w||echo clean
tail -4 logs/wick_paper.log||true
sudo -u $OWNER $P $W --status
