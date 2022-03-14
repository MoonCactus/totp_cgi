#!/bin/bash
set -feu -o pipefail
# Helper to allow/deny access based on IP.
# You need to make www-data a sudoer on this script and to include this
# file from your /etc/apache2/site-enabled web site configuration, with
#   Include /usr/lib/cgi-bin/toctoc/secrets/apacheRequire.cfg


# Make it less dependent on the context (and so "reset" works when called from cron each night)
export PATH=/usr/local/bin:/usr/bin:/bin

APACHE_INCLUDE="/usr/lib/cgi-bin/toctoc/secrets/apacheAllow.cfg"     # old syntax: 'Allow from '
APACHE_INCLUDE2="/usr/lib/cgi-bin/toctoc/secrets/apacheRequire.cfg"  # new syntax: 'Require ip '

fail()
{
	echo "Fail:$@" > /dev/stderr
	exit 1
}

[[ $# -eq 0 ]] && fail "Usage: $0 reset | allow <IP> | deny <IP>"

ACTION="${1-}"
shift

if [[ "$ACTION" = "reset" ]]; then
	echo -n > "$APACHE_INCLUDE"
	echo "Whitelist reinitialized"
else
	IP="${1-}"
	[[ "$IP" =~ ^[0-9.]+$ ]] || fail "expected/malformed IP"
	cfgline="Allow from $IP"

	if [[ "$ACTION" = "allow" ]]; then
		if grep -q "$cfgline" "$APACHE_INCLUDE"; then
			echo "Was already allowed"
			exit 0
		fi
		echo "$cfgline" >> "$APACHE_INCLUDE" ||
			fail "CGI Error: could not add you to the allowed list (please report error)"
		echo "Added to whitelist"

	elif [[ "$ACTION" = "deny" ]]; then
		if ! grep -q "$cfgline" "$APACHE_INCLUDE"; then
			echo "Was already denied"
			exit 0
		fi
		sed -i "/$cfgline/d" "$APACHE_INCLUDE" &&
			echo "Deleted from whitelist"

	else
		fail "Unknown action"
	fi
fi

# For backward compatibility
sed 's/Allow from /Require ip /' "$APACHE_INCLUDE" > "$APACHE_INCLUDE2"

service apache2 reload || fail "committing changes"
exit 0
