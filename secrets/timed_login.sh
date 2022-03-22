#!/bin/bash
# timed_login.sh : handles user logins (allow, deny, presence check, age check)
# Run with a bare --help for more information

set -feu -o pipefail

dbfile="/etc/timed_login"
if [[ "${1-}" = '--db' ]]; then
	shift
	dbfile="$1"
	shift
fi

# Delay concurrent runs
LOCKFILE=/var/lock/$(basename $0).lock
while [ -f "$LOCKFILE" ]; do sleep 0.1; done
trap '{ rc=$?; rm -f '"$LOCKFILE"' ; exit $rc; }' EXIT
touch "$LOCKFILE"

fail()
{
	printf "$@\n" > /dev/stderr
	exit 1
}

[[ ${1-} =~ (^$|-h$|--help$) ]] && fail "Timestamp-based login handler.\nUsage: $(basename $0) [-h|--help] [--db DBFILE] ( allow USERID [IP] | deny USERID | exists USERID | check USERID [ELAPSED] ).\nDefault DBFILE is /etc/timed_login.\nDefault ELAPSED is 3600 seconds."

[[ -f "$dbfile" ]] || touch "$dbfile" 2>/dev/null || fail "Cannot write to $dbfile. Check rights or use --db option."

action="${1-}"
uid="${2-}"

if [[ "$action" = "exists" ]]; then
	grep -q ":$uid$" "$dbfile" || exit 1
elif [[ "$action" = "check" ]]; then
	maxage=${3-3600}
	[[ "$maxage" =~ ^[0-9]+$ ]] || fail "expected/malformed max age (seconds)"
	t=$(grep ":$uid$" "$dbfile" | cut -d: -f1)
	[[ -z "$t" ]] && t=0  # unknown user
	(( $t < $(date +%s) - "$maxage" )) && exit 1
else
	if [[ "$action" = "allow" ]]; then
		ip="${3-}"
		[[ "$ip" =~ ^[0-9.]*$ ]] || fail "expected/malformed IP"
		new=$(grep -v ":$uid$" "$dbfile"; echo "$(date +%s):$ip:$uid")
	elif [[ "$action" = "deny" ]]; then
		new=$(grep -v ":$uid$" "$dbfile")
	else
		fail "Unknown action"
	fi
	echo "$new" > "$dbfile"
fi
exit 0
