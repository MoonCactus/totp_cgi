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
	if [[ $# -ne 0 ]]; then
		printf "$@\n" > /dev/stderr
	else
		cat > /dev/stderr
	fi
	exit 1
}

[[ ${1-} =~ (^$|-h$|--help$) ]] && fail << EOT
Timestamp-based login handler.
Usage: $(basename $0) [-h|--help] [--db DBFILE] ( allow USERID [IP] | deny USERID | exists USERID | check USERID [ELAPSED] | export FORMAT [ELAPSED]).

Default DBFILE is /etc/timed_login. It shall be writeable by the caller of this script.

allow USERID [IP]:
  record provided user name and optional IP address together with the current timestamp

deny USERID
  remove provided user name from the records

exists USERID
  return positive if user name exists in the record

check USERID [ELAPSED]
  default ELAPSED value is 3600 seconds.
  return positive if and only user exists and it was allowed in the last ELAPSED seconds

export FORMAT [ELAPSED]
  FORMAT options can be (text|apache2|nginx), default is text.
  default ELAPSED is 3600 seconds.
  dump all valid logins, either as text or as a formated file that can be included by Apache2 or NGINX:
    When FORMAT is text: dumps records as "epoch:ipaddress:username"
    When FORMAT is Apache2, dumps records as 'Allow from IP', use "<RequireAny>\nInclude thisfile.cfg</RequireAny>\n"
    When FORMAT is NGINX, dumps records as "allow IP;", use "include thisfile.cfg;\ndeny all;\n"

EOT

[[ -f "$dbfile" ]] || touch "$dbfile" 2>/dev/null || fail "Cannot write to $dbfile. Check rights or use --db option."

action="${1-}"
if [[ "$action" = "export" ]]; then
	format=${2-text}
	maxage=${3-3600}
	[[ "$maxage" =~ ^[0-9]+$ ]] || fail "expected/malformed max age (seconds)"
	oldest=$(( $(date +%s) - $maxage ))
	if [[ "$format" = "text" ]]; then
		awk 'BEGIN{FS=":";OFS=":";} { if($1>'$oldest') print $0;}' "$dbfile"
	elif [[ "$format" = "apache2" ]]; then
		awk 'BEGIN{FS=":";OFS=":";} { if($1>'$oldest') {printf("Allow from %s # @%s via %s\n",$2,$1,$3)}}' "$dbfile" | cut -d: -f3-
	elif [[ "$format" = "nginx" ]]; then
		awk 'BEGIN{FS=":";OFS=":";} { if($1>'$oldest') {printf("allow %s; # @%s via %s\n",$2,$1,$3)}}' "$dbfile" | cut -d: -f3-
	else
		fail "Unknown export format."
	fi
else
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
fi
exit 0
