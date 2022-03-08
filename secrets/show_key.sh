#!/bin/bash -feu
user=${1-admin}
echo "Showing current key for $user:"
while :
do
	oathtool -b --totp $(cat "$user.key" | tr -d "\n")
	sleep 1
done
