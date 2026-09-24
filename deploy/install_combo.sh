# Azure portal > VM > Run command >
# RunShellScript
# Installs and starts the COMBINATION
# paper book (combo_paper.py, doc 14 s9)
# beside the seven blend books. It
# places NO orders and needs no keys.
# FIRST run pull_and_rebuild.sh so the
# VM has the latest code. This script
# does not pull, it only installs.
# Every line is under 44 chars and there
# are no backslashes: Run command wraps
# long lines and decodes backslashes.
cd /opt/forexbot
set -e
export SYSTEMD_PAGER=cat
P=./.venv/bin/python
N=combo-paper
D=/etc/systemd/system
APP=$(pwd)
OWNER=$(stat -c %U blend_paper.py)
echo ==1-VERIFY==
H1=2164809dc2ef2232
H2=ffd4a6f4af98d8b2
H3=7ef669da6de573c2
H4=6b013b058341b141
H=$H1$H2$H3$H4
G=$(sha256sum combo_paper.py|head -c 64)
test $G = $H
echo HASH_OK
chown -R $OWNER:$OWNER $APP
C=combo_paper.py
sudo -u $OWNER $P -m py_compile $C
echo SYNTAX_OK
X=tests/test_combo_paper.py
sudo -u $OWNER $P $X|tail -3
echo ==2-INSTALL==
T=/tmp/$N.service
F=deploy/$N.service
sed "s|__APP_DIR__|$APP|g" $F >$T
sed -i "s|__USER__|$OWNER|g" $T
cp $T $D/$N.service
systemctl daemon-reload
systemctl enable --now $N
echo ==3-CHECK==
sleep 150
systemctl is-active $N
free -m||true
journalctl -u $N -n 40 >/tmp/c||true
grep -e rror -e raceback /tmp/c||echo clean
tail -5 logs/combo_paper.log||true
sudo -u $OWNER $P combo_paper.py --status
