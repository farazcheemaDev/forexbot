#!/bin/bash
# Writes /etc/forexbot-dash.env for the dashboard feed (deploy/forexbot-dash.service). Run it YOURSELF so the token is
# typed by you and never passes through anything else:
#     ssh -t forexbot-vm "bash /opt/forexbot/deploy/dash_env.sh"
# Forgiving about what is pasted (quotes, spaces, a leading NAME= are stripped) and it ASKS AGAIN on a bad answer - the
# first version exited on a quoted URL, the ssh session closed, and the token went into the PC's own shell. Before
# saving it checks the pair with Upstash (one SET); the token reaches curl on stdin, never as an argument.
OUT="${DASH_ENV_OUT:-/etc/forexbot-dash.env}"
umask 077

clean() {
  local v="$1"
  v="${v//[[:space:]]/}"
  v="${v//\"/}"
  v="${v//\'/}"
  v="${v#export}"
  v="${v#UPSTASH_REDIS_REST_URL=}"
  v="${v#UPSTASH_REDIS_REST_TOKEN=}"
  printf '%s' "${v%/}"
}

upstash() {   # upstash <path> - POST to the REST API with the token in a header read from stdin
  printf 'header = "Authorization: Bearer %s"\n' "$T" | curl -s -m 20 --config - -X POST "$U/$1" 2>&1
}

echo "Two questions. Paste with Ctrl+V or right-click, then press Enter. Ctrl+C quits without saving."
while :; do
  while :; do
    read -r -p "1/2  Upstash REST URL: " U
    U=$(clean "$U")
    case "$U" in https://?*) break ;; esac
    echo "     Not a URL - it looks like https://something.upstash.io . Try again."
  done
  while :; do
    read -r -s -p "2/2  Upstash REST TOKEN, the normal one (stays invisible while you paste): " T
    echo
    T=$(clean "$T")
    [ "${#T}" -ge 20 ] && break
    echo "     Nothing (or too little) arrived - copy the whole token and paste again."
  done
  R=$(upstash "set/forexbot:setup_check/ok")
  case "$R" in
    *'"OK"'*) upstash "del/forexbot:setup_check" > /dev/null; break ;;
    *NOPERM*|*[Rr]ead*[Oo]nly*) echo "     That is the READ-ONLY token - this one needs the normal token. Again:" ;;
    *) echo "     Upstash did not accept that URL + token (${R:0:100}). Again:" ;;
  esac
done
printf 'UPSTASH_REDIS_REST_URL=%s\nUPSTASH_REDIS_REST_TOKEN=%s\n' "$U" "$T" > "$OUT"
chmod 600 "$OUT"
echo "Checked with Upstash and saved $OUT (root only). Tell Claude it is done."
