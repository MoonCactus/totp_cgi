#!/bin/bash
# timed_login.sh : handles user logins (allow, deny, presence check, age check)
# Run with a bare --help for more information

set -feu -o pipefail

dbfile="./timed_login.db"
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

Default DBFILE is "./timed_login.db" in the current directory. It shall be writeable by the caller of this script.

allow USERID [IP]:
  Record provided user name and optional IP address together with the current timestamp
  Note that records without IP will not show up in apache or nginx exports

deny USERID
  Remove provided user name from the records

exists USERID
  Return positive if user name exists in the record

check USERID [ELAPSED]
  Default ELAPSED value is 3600 seconds.
  Return positive if and only user exists and it was allowed in the last ELAPSED seconds

export FORMAT [ELAPSED]
  FORMAT options can be (text|apache|nginx), default is text.
  Default ELAPSED is 3600 seconds.
  Dump lines of active logins formatted according to FORMAT:
    text   : EPOCH:IP:USERNAME
    apache : Allow from IP      # to be used as: <RequireAny> Include thisfile.cfg </RequireAny>
    nginx  : allow IP;          # to be used as: include thisfile.cfg; deny all;

Note: arguments are consumed iteratively, eg. add two new users and dump the valid ones:

  ./timed_login.sh --db /tmp/logins.db allow bob 12.33.44.55 allow mar:tin export text

EOT

if [[ ! -f "$dbfile" ]]; then
	touch "$dbfile" 2>/dev/null || fail "Cannot write to $dbfile from $(pwd). Check rights or use --db option."
fi

while [[ $# -gt 0 ]]; do

	action="${1-}"; shift || fail 'Missing argument'

	if [[ "$action" = "export" ]]; then
		format="text"; [[ ${1-} =~ ^(text|apache|nginx)$ ]] && format="$1" && shift
		maxage=3600; [[ ${1-} =~ ^[1-9][0-9]*$ ]] && maxage="$1" && shift
		oldest=$(( $(date +%s) - $maxage ))
		if [[ "$format" = "text" ]]; then
			awk 'BEGIN{FS=":";OFS=":";} { if($1>'$oldest') print $0;}' "$dbfile"
		elif [[ "$format" = "apache" ]]; then
			awk 'BEGIN{FS=":";OFS=":";} { if($2 && $1>'$oldest') {printf("Allow from %s # @%s via %s\n",$2,$1,$3)}}' "$dbfile" | cut -d: -f3-
		elif [[ "$format" = "nginx" ]]; then
			awk 'BEGIN{FS=":";OFS=":";} { if($2 && $1>'$oldest') {printf("allow %s; # @%s via %s\n",$2,$1,$3)}}' "$dbfile" | cut -d: -f3-
		fi
	else
		uid="${1-}"
		shift
		if [[ "$action" = "exists" ]]; then
			grep -q ":$uid$" "$dbfile" || exit 1
		elif [[ "$action" = "check" ]]; then
			maxage=3600; [[ ${1-} =~ ^[1-9][0-9]*$ ]] && maxage="$1" && shift
			t=$(grep ":$uid$" "$dbfile" | cut -d: -f1)
			[[ -z "$t" ]] && t=0  # unknown user
			(( $t < $(date +%s) - "$maxage" )) && exit 1
			
		else
			if [[ "$action" = "allow" ]]; then
				ip=''; [[ "${1-}" =~ ^[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}\.[0-9]{1,3}$ ]] && ip="$1" && shift
				new=$(grep -v ":$uid$" "$dbfile"; echo "$(date +%s):$ip:$uid" || true)
			elif [[ "$action" = "deny" ]]; then
				new=$(grep -v ":$uid$" "$dbfile" || true)
			else
				fail "Bad parameter or unknown action at or around '$action' parameter"
			fi
			echo "$new" > "$dbfile"
		fi
	fi

done
exit 0
