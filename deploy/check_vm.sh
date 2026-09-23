# Paste into Azure portal > VM > Run command > RunShellScript.
# READ-ONLY. Runs no patch, restarts nothing, writes nothing.
# Answers one question: is blend_paper.py intact after the failed
# paste, and which version is on the box.
# Every line is short. The previous script failed because long
# lines get wrapped near 50 chars and the tail runs as a command.
# Quotes were never the problem - the shell prints a not-found
# command AFTER quote removal, which only made it look that way.
cd /opt/forexbot
echo ==1-IS-THE-BOOK-RUNNING==
systemctl is-active blend-paper || true
echo ==2-WHICH-VERSION-IS-ON-DISK==
sha256sum blend_paper.py
echo expected-PRE-fix-untouched:
echo d097160aa3c2cae8f5a7262ade6339130ddbb087b4f238e7da16abd277944e7c
echo expected-POST-fix-applied:
echo 15c8d624027e7018383edb3eb6b7ff32be5e813773d5c95c0e22728a4a32a363
echo neither-means-DAMAGED-restore-from-a-backup-below
echo ==3-IS-THE-FIX-PRESENT-both-0-or-both-1==
grep -c rec.get.risk_usd blend_paper.py || true
grep -c risk_usd=risk_usd blend_paper.py || true
echo 0-and-0-means-prefix-1-and-1-means-patched
echo ==4-LEFTOVER-JUNK-FROM-THE-FAILED-RUN==
ls -la blend_paper.py.new 2>/dev/null || echo none
ls -la bp.gz 2>/dev/null || echo none
echo ==5-BACKUPS-AVAILABLE==
ls -la logs/ | grep bak- || echo none
echo ==6-DOES-IT-STILL-PARSE==
OWNER=$(stat -c %U blend_paper.py)
sudo -u $OWNER ./.venv/bin/python -m py_compile blend_paper.py
echo SYNTAX_OK
echo ==7-LAST-LOG-LINES==
tail -n 14 logs/blend_paper.log
