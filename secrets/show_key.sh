#!/bin/bash -feu
keyfile=${1-totp/admin}
if [[ "$keyfile" =~ (^$|-h$|--help$) ]]; then
	printf "$(basename $0) username.key\nKeep showing current TOTP key for the given user key file (eg. secrets/admin.key)\n"
	exit 1
fi
if [[ ! -f "$keyfile" ]]; then
	printf "Failed to find $keyfile; check your paths.\n"
	exit 1
fi

echo "Showing current TOTP for '$keyfile':"
prevk=
while :
do
	k=$(oathtool -b --totp $(cat "$keyfile" | tr -d "\n"))
	if [[ "$k" = "$prevk" ]]; then
		printf "."
	else
		printf "\n$k  "
		prevk="$k"
	fi
	sleep 1
done
