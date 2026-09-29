# Azure portal > VM > Run command >
# RunShellScript
# MOVES THE combo_bot DEMO TO THIS VM.
# STOP THE DEMO BOT ON YOUR PC FIRST: two
# bots on one account fight each other.
# Keys: paste the output of
# deploy/make_key_paste.ps1 first. This
# script never reads or prints them.
# It starts FRESH: its first poll nets the
# demo account to its own books, so what
# the PC bot left open is closed.
# Lines under 44 chars, no backslashes.
cd /opt/forexbot
set -e
export SYSTEMD_PAGER=cat
P=./.venv/bin/python
N=combo-bot-demo
D=/etc/systemd/system
E=/etc/forexbot.env
APP=$(pwd)
OWNER=$(stat -c %U blend_paper.py)
U1=https://github.com/farazcheemaDev
U2=/forexbot.git
echo ==1-SAFETY==
test -f $E||echo NO-KEYS-run-make_key_paste
test -f $E
grep -c BITGET_ $E
echo above-must-be-3-keys-file-ok
for S in longtrend-demo longtrend-paper
do
if systemctl is-active -q $S
then echo $S-RUNS-STOP-IT; exit 1
fi
done
if pgrep -f combo_bot.py
then echo ALREADY-RUNNING; exit 1
fi
echo no-other-bot-on-this-vm
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
C=$($G hash-object combo_bot.py)
C=$(echo $C|head -c 16)
test $C = 879e804e659324d3
echo BLOBS_OK
chown -R $OWNER:$OWNER /opt/forexbot
echo ==4-CCXT==
sudo -u $OWNER $P -m pip install -q ccxt
sudo -u $OWNER $P -m pip show ccxt|head -2
echo ==5-TESTS-stop-here-if-any-fail==
for X in combo_bot wick_live combo_paper
do
F=tests/test_$X.py
K=ok
sudo -u $OWNER $P $F >/tmp/t 2>&1||K=FAIL
tail -2 /tmp/t
test $K = ok
done
echo ==6-MEMORY==
free -m
echo ==7-INSTALL==
T=/tmp/$N.service
F=deploy/$N.service
sed "s|__APP_DIR__|$APP|g" $F >$T
sed -i "s|__USER__|$OWNER|g" $T
cp $T $D/$N.service
systemctl daemon-reload
systemctl enable --now $N
echo ==8-CHECK==
sleep 150
systemctl is-active $N
journalctl -u $N -n 80 >/tmp/c||true
grep -e rror -e raceback /tmp/c|head -8
grep REFUS /tmp/c|head -3
echo errors-above-if-any
L=logs/combo_bot_demo/combo_paper.log
tail -n 12 $L
