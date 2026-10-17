#!/bin/bash
# Writes /etc/forexbot-dash.env for the dashboard feed (deploy/forexbot-dash.service). Run it YOURSELF so the token is
# typed by you and never passes through anything else:
#     ssh -t forexbot-vm "bash /opt/forexbot/deploy/dash_env.sh"
# The token prompt hides what you type. The file is root-only (600).
set -e
read -r -p "Upstash REST URL (starts with https://): " U
read -r -s -p "Upstash REST token - the read-WRITE one (input hidden): " T
echo
case "$U" in https://*) ;; *) echo "The URL must start with https://"; exit 1 ;; esac
[ "${#T}" -ge 20 ] || { echo "That token looks too short - copy the whole REST token"; exit 1; }
umask 077
printf 'UPSTASH_REDIS_REST_URL=%s\nUPSTASH_REDIS_REST_TOKEN=%s\n' "$U" "$T" > /etc/forexbot-dash.env
chmod 600 /etc/forexbot-dash.env
echo "Saved /etc/forexbot-dash.env (root only). Tell Claude it is done."
