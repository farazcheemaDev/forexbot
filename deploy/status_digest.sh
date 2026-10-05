# Azure portal > VM > Run command >
# RunShellScript
# READ-ONLY. Restarts nothing, changes no
# book. One paste, every crypto book, in
# under 4KB (Run command keeps only the
# last ~4KB, so the most important part,
# the demo bot's two-week verdict, prints
# LAST).
# Lines under 44 chars, no backslashes:
# Run command wraps near 50 and a wrapped
# tail RUNS as a command.
cd /opt/forexbot
export SYSTEMD_PAGER=cat
P=./.venv/bin/python
OWNER=$(stat -c %U blend_paper.py)
R="sudo -u $OWNER $P"
echo ==1-SERVICES==
for s in blend-paper combo-paper
do echo $s $(systemctl is-active $s)
done
for s in wick-paper combo-bot-demo
do echo $s $(systemctl is-active $s)
done
echo ==2-CRASH-BIDS-PAPER==
$R wick_paper.py --status 2>&1|tail -n 5
echo ==3-SEVEN-BOOKS-CORRECTED==
$R rebuild_equity.py 2>&1|tail -n 9
echo ==4-COMBO-PAPER==
$R combo_paper.py --status 2>&1|tail -n 10
echo ==5-DEMO-BOT-TWO-WEEK-CHECK==
A="--mode demo --report"
F=/tmp/digest_rep
$R combo_bot.py $A >$F 2>&1
X1="PASS when"
X2="every fill"
X3="reduce, close"
grep -v -e "$X1" -e "$X2" -e "$X3" $F
rm -f $F
echo ==END==
