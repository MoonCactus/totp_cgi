#!/bin/bash -feu
# Self contained TOTP CGI bash script.

# This scripts helps generate and check accounts with help from a CGI-enabled HTTP server.
# You probably want to set ALLOWTOOL in (./secrets|/etc)/totp_cgi.conf  so as to do something when
# a user successfully authenticates, eg. './secrets/timed_login.sh allow "%USERNAME%" "%IP%" export nginx > ./secrets/nginx_allow.conf'

# Eg, if www is sudoer as "data ALL = (root) NOPASSWD: /usr/sbin/service nginx reload" :
#   ALLOWTOOL=./timed_login.sh allow "%USERNAME%" "%IP%" export nginx > nginx_allow.conf && sudo /usr/sbin/service nginx reload

# To create a new user you must be within the ADMINS (see /etc/totp_cgi.conf, default is username 'admin'),
# then you must use this URL to access to the service (even if that's not your name, it will only show an
# additional field to allow you to create a new user). Or just add it to your your footer.
#    http://127.0.0.1/cgi/totp/index.cgi?admin
#
# Nb: you can create a time-limited, priviledged right to see the current code in clear
# by eg. "touch [-t 202206011155] secrets/reveal/AddMIN", then get the TOTP code
# by typing `AddMIN` keyword in the 6-figure code.

set -o pipefail -eE -o functrace

get_config()
{
  key="$1"
  default="$2"
  value=$(sed -n "s/^\s*$key\s*=\s*//p" "$CONFIGFILE" 2>/dev/null || true)
  [[ -z "$value" ]] && value="$default"
  echo "$value"
}

CTX='start'
WORKDIR="$(dirname $(realpath $0))"

CONFIGFILE="$WORKDIR/secrets/totp_cgi.conf"
[[ -f "$CONFIGFILE" ]] || CONFIGFILE='/etc/totp_cgi.conf'


# Main configuration, with default parameters
HTTPS_ONLY=$(get_config HTTPS_ONLY 'y')         # refuse to run if not HTTPS
USERNAME=$(get_config USERNAME '')              # default username when set (eg 'nextcloud')
REVEALTIMEOUT=$(get_config REVEALTIMEOUT 300)   # expriring delay for admin reveal codes (5 minutes). Zero to disable.
ADMINS=$(get_config ADMINS admin)               # comma-separated list of users who can create other users

# White-listing administrative tool.
# Warning: it gets run by "eval" so that, eg. "sudo mytool" really is executed as sudo.
# Tokens %REMOTEIP% and %USERNAME% are replaced by their (sanitized) values before the call.
ALLOWTOOL=$(get_config ALLOWTOOL "")
DEBUG=$(get_config DEBUG 'no')                  # yes to debug the exact call to the white listing tool

# Generation data
FQDN=$(get_config FQDN "totp.tecrd.com")        # TOTP property:  fully qualified domain name
SERVICE=$(get_config SERVICE "TecRD")           # TOTP property: protected service

XHEADER=$(get_config XHEADER "<style type="text/css">
  BODY             { font-family:serif; text-align:center; }
  INPUT[type=text] { text-align:center; margin-bottom: 0.5em; font-family:monospace; }
  INPUT[type=submit] { margin: 4px; }
  .small           { font-size:0.8em; }
  .light           { color:#888; }
  .hilite          { color:#FF0000; padding:8px; }
  .header          { border-bottom:1px solid #EEE; padding-bottom:8px;}
  .footer          { border-top:1px solid #EEE; padding-top:8px; font-size:0.8em; }
  #qrcode          { margin:1em; }
</style>")                                      # inserted in every generated html page (to hold CSS or JS, eg.)


################### Internationalization
# We are extracting the data from the end of this script

i18n()
{
  key="${1-i18nNoKey}"
  shift
  lang=${HTTP_ACCEPT_LANGUAGE-en}
  lang=${lang:0:2}
  [[ "$lang" =~ [a-z]{2,} ]] || lang='en'

  r=$(sed -n -e "/^#### I18N:$lang/,\${s/^\s*${key}[: \s]\s*//p}" "$0" | head -1)
  [[ -z "$r" ]] && r="${key}"
  printf "$r" "$@"
}


################### Panel: Dump HTTP head

http_head()  # title
{
  cat << EOF
<html>
<head>
  <meta http-equiv="Content-type" content="text/html;charset=UTF-8">
  <meta name="ROBOTS" content="noindex">
EOF
  [[ ${XHEADER} ]] && sed 's/^/  /' <<< "${XHEADER}"
  [[ $# -ge 1 ]] && sed 's/^/  /' <<< "$@"
  printf "</head>\n<body>\n"
}

http_body()
{
  cat
}

http_tail()
{
  printf "</body>\n</html>\n"
}


################### Panel: Show error

error()
{
  trap '' EXIT
  httpcode="$1"
  shift

  printf "Status: $httpcode\r\n"
  printf "Content-type:text/html\r\n\r\n"
  

  MSG="$@"
  redirect='<!-- <meta http-equiv="Refresh" content="3; URL=https://service.valorhiz.com/cgi-bin/toctoc"> -->'
  echo "$MSG" | grep 'Internal CGI error' && redirect=''

  context=
  [[ $httpcode =~ ^5 ]] && context="ctx:$CTX"

  http_head "<title>$httpcode</title>$redirect"
  http_body << EOT
  <h1>$(i18n httperror $httpcode)</h1>
  <div>$MSG</div>
  <div class='small light'>$context</div>
  <div id="footer">$(i18n footer)</div>
EOT
  http_tail
	exit 0
}


################### Panel: Show login form

show_form()
{
  csscreate='style="display:none;"'
  if [[ ${1-} = '--admin' ]]; then
    shift
    csscreate='style="display:visible"'
  fi
  
  printf "Status: 200 OK\r\n"
  printf "Content-type:text/html\r\n\r\n"

  http_head "<title>$(i18n titlemain)</title>"
  http_body << EOT
  $(i18n header)
  <form action="">
    <div class='hilite'>$@</div>
    <div id='divname'>
      <div>$(i18n username)</div>
      <input type="text" size="12" minlength="3" maxlength="12" id="username" name="username" value="$USERNAME">
    </div>
    <div id='divcode'>
      <div>$(i18n htcode6)</div>
      <input type="text" autofocus size="6" minlength="6" maxlength="6" id="totpcode" name="totpcode">
    </div>
    <div class='small light' id='divcreate' $csscreate>
      <div>$(i18n newusername)</div>
      <input type="text" size="12" minlength="3" maxlength="12" id="newuser" name="newuser" value="">
    </div>
    <input type="submit" value="$(i18n submit)">
  </form>
  <div id="footer">$(i18n footer YEEES)</div>
EOT
  http_tail
  trap '' EXIT
  exit 0
}


################### Panel: Show success

show_success()
{
  CTX='ok'
  # All right
  printf "Status: 200 OK\r\n"
  printf "Content-type:text/html\r\n\r\n"

  http_head "<title>$(i18n titlesecured)</title>"
  http_body << EOT
  $(i18n header)
  <div>$(i18n goodcode "$REMOTE_ADDR")</div>
  <div id="footer">$(i18n footer)</div>
EOT
  http_tail
}


################### Panel: success creating a new account

create_account()
{
  CTX='createaccount'
  [[ ! "$NEWUSER" =~ ^[A-Za-z0-9_]+$ ]] && error 400 $(i18n errnewuser)
  [[ ! "$SERVICE" ]] && error 500 $(i18n errnewservice)
  [[ ! "$FQDN" ]] && error 500 $(i18n errnewfqdn)
  which qrencode &> /dev/null || error 500 $(i18n errnewqrtool)

  ID="$SERVICE:$NEWUSER@$FQDN"
  SECRET=$(tr -dc A-Za-z0-9 </dev/urandom | head -c 10 | base32 || true)
  URL="otpauth://totp/${SERVICE}:${NEWUSER}@${FQDN}?secret=${SECRET}&issuer=${SERVICE}"

  b64=$(qrencode -s 1 -l H "${URL}" -o - | base64 | tr -d "\n")
  CSSIMG=$(printf '<img width=%dpx style="image-rendering:crisp-edges;" src="data:image/png;base64,%s" title="%s">\n' $((57*5)) "$b64" "totp_qrcode_${NEWUSER}.png")

  CTX='saveaccount'
  echo "$SECRET" > "$WORKDIR/secrets/totp/$NEWUSER" || error 500 "$(i18n errnewsave $NEWUSER)"

  CTX='shownewaccount'
  printf "Status: 200 OK\r\n"
  printf "Content-type:text/html\r\n\r\n"

  http_head "<title$(i18n newtitle)</title>"
  http_body << EOT
  $(i18n createtitle)
  <div class='small'>
    $(i18n goodcode "$REMOTE_ADDR")
  </div>

  $(i18n newheader)
  <div>
    $(i18n newbody "$NEWUSER")
  </div>
  <div id='qrcode'>
    <div>$CSSIMG</div>
    $(i18n newqrtitle "$SERVICE")
    $(i18n newqruser "$NEWUSER</b>@$FQDN")   
  </div>
  <div class='small light'>
    $(i18n newcheck)
  </div>

  <div id="footer">$(i18n footer)</div>
EOT
  http_tail
  trap '' EXIT
}


################### Main

trap 'RC=$?; error 500 "Internal CGI error #${RC} at line ${LINENO}"' EXIT

test -d "$WORKDIR/secrets/" || error 500 "$(i18n errfolders)"
which oathtool &>/dev/null || error 500 "$(i18n errtools)"
which base32 &>/dev/null || error 500 "$(i18n errtools)"

if [[ "${REMOTE_ADDR-noncgi}" != 127.0.0.1 ]] || [[ "${SERVER_ADDR-noncgi}" != 127.0.0.1 ]]; then
  if [[ "${HTTPS_ONLY-noncgi}" = 'y' ]] && [[ "${REQUEST_SCHEME-noncgi}" != 'https' ]]; then
    printf "Status: 403 Forbidden\r\n"
    printf "Content-type:text/html\r\n\r\n"
    i18n errhttps
    exit 0
  fi
fi

#### No parameters (main form)
CTX='qry'

if [[ -z ${QUERY_STRING} ]]; then
  show_form
elif [[ ${QUERY_STRING} = 'admin' ]]; then
  show_form --admin
fi


#### Parameters (username and reveal code or TOTP key)
CTX='params'

# TODO: better parse the uri (eg. against parameter order!)
IFS='=&' read -r \
  keyuser USERNAME \
  keycode USERCODE \
  newuser NEWUSER \
<<< ${QUERY_STRING} || true

sleep 1 # Pretty simple way to mitigate brute force attacks
[[ "$USERNAME" =~ ^[A-Za-z0-9_]+$ ]] || error 400 $(i18n illegaluser)

#### Reveal code provided
CTX='reveal'

if [[ -n "$REVEALTIMEOUT" ]] && [[ "$USERCODE" =~ ^[A-Za-z0-9_]+$ ]]; then
  fk="$WORKDIR/secrets/reveal/${USERNAME}_${USERCODE}"
  if [[ -f "$fk" ]]; then
    if (( $(date +%s) - $(date +%s -r "$fk") > "$REVEALTIMEOUT" )); then
      show_form $(i18n keyctmo)
    else
      KEY=$(oathtool -b --totp "$(cat '$fk' | tr -d '\n')")
      show_form $(i18n codereveal "$KEY")
    fi
  fi
fi

#### User/code
CTX='check'

[[ "$USERCODE" =~ ^[0-9_]{6}$ ]] || error 400 $(i18n illegalcode)

ukey="$WORKDIR/secrets/totp/$USERNAME"
[[ -f "$ukey" ]] || error 403 $(i18n nouserekey "$USERNAME")  # really a 404 but do not tell ;)
SECRET=$(cat $ukey | tr -d "\n")
base32 -d &>/dev/null <<< "$SECRET" || error 405 $(i18n brokenkey "$USERNAME")

CTX='oath'
SRVCODE=$(oathtool -b --totp "${SECRET}" || error 403 $(i18n wrongkey "$USERNAME"))

if [[ "$SRVCODE" != "$USERCODE" ]]; then
  CTX='wrongcode'
  show_form $(i18n wrongcode)
fi

if [[ -n "$ALLOWTOOL" ]]; then
  CTX="whitelist:$ALLOWTOOL"
  set +e
  # Yes, this is dangerous, but the given arguments are safe
  execstr=$(echo "cd %WORKDIR%/secrets && $ALLOWTOOL" | sed -e "s|%WORKDIR%|$WORKDIR|" -e "s|%IP%|$REMOTE_ADDR|" -e "s|%USERNAME%|$USERNAME|")
  CTX="whitelist:$execstr"
  if [[ "$DEBUG" = 'yes' ]]; then
    reply="WOULD_CALL: $execstr"
    errno=666
  else
    reply=$(eval "$execstr" 2>&1)
    errno=$?
  fi
  set -e
  if [[ $errno != 0 ]]; then
    error 501 "$(i18n errwhitelist)<pre>$reply</pre>"
  fi
fi


if [[ "$NEWUSER" ]] && grep -q "$USERNAME" <<< "$ADMINS"; then
  create_account
else
  show_success
fi

trap '' EXIT
exit 0


######################## Localized strings follows ########################
#
# This is parsed data, be cautious while editing  (see i18n function above)
#


cat << 'EOT' &>/dev/null

#### I18N:fr

titlemain     Jeton d'accès requis
header        <h1 class='header'>Jeton d'accès</h1>
footer        <div class='footer'>&copy; <a href='https://github.com/MoonCactus'>totp-cgi</a> / <a href="?admin">admin</a></div>

username      Votre identifiant
htcode6       Votre code à 6 chiffres<div class='small'>(ou mot-clé spécial)</div>
submit        Tester
keyctmo       L'accès par ce mot-clé est périmé !
codereveal    Le code à saisir est %s<div class='small'>Appuyez sur F5 s'il est périmé.</div>
wrongcode     Désolé, ce code est périmé ou invalide. Rééssayez !
illegaluser   Utilisateur illegal.
illegalcode   Le code doit faire 6 chiffres.
nouserekey    Echec d'identification,<br/>voyez vos administrateurs.
brokenkey     Format de clé inattendu.
expiredkey    Clé expirée ou erronnée, réessayez !
titlesecured  ☠ Authentifié
goodcode      <div>Le code est bon,</br>vous êtes authentifiés !</div>\n<div style='padding:8px;' class='small light'>%s</div>
  
httperror     Erreur %s
errwhitelist  Votre authentification est correcte<br/>mais il y a eu un problème interne.<br/>Dites-le aux administrateurs système !
errfolders    Installation CGI incomplète (fichiers).
errtools      Installation CGI incomplète (outils).
errhttps      L'acces http:// est désactivé, utilisez https:// à la place.

createtitle   Création de compte
newusername   <div title='Si vous êtes un administrateur'>Créer un nouveau compte (*)</div>
errnewuser    Nom d'utilisateur cible illegal. N'utiliser que des lettres, chiffres, tiret ou caractère souligné.
errnewservice SERVICE n'est pas configuré
errnewfqdn    FQDN n'est pas configuré
errnewqrtool  L'outil 'qrencode' n'est pas installé
errnewsave    Impossible d'enregister<br/>le nouvel utilisateur "%s".

newtitle      ☠ Générateur de code TOTP
newheader     <h1 class='header'>Nouveau compte TOTP</h1>
newqruser     <div>Utilisateur: <b>%s</b></div>
newqrtitle    <div>Service: <b>%s</b></div>
newbody       </div>Voici le QR code de <b>%s</b><br/><a href='https://play.google.com/store/apps/details?id=org.fedorahosted.freeotp'>Android</a> ou <a href='https://itunes.apple.com/us/app/freeotp-authenticator/id872559395?mt=8'>iOS</a></div><div style='margin-top:0.5em;' class='small'>Tout code précédent a été invalidé.</div>
newcheck      Puis testez-le <a href='?'>ici</a>.


#### I18N:en  (must be last)

titlemain     Security token needed
header        <h1 class='header'>Access token</h1>
footer        <div class='footer'>&copy; <a href='https://github.com/MoonCactus'>totp-cgi</a> / <a href="?admin">admin</a></div>
username      Your identifier
htcode6       Your 6-digit code<div class='small'>(or special keyword)</div>
submit        Test
keyctmo       This keyword access is outdated!
codereveal    The code to type is %s<div class='small'>Press F5 if it expired.</div>
wrongcode     Sorry, this revealing code is outdated or invalid. Try again!
illegaluser   Illegal user.
illegalcode   Code must be 6-digit long.
nouserekey    Identification failure,<br/>check with your admins.
brokenkey     Unexpected key format.
expiredkey    Wrong or outdated code, try again.
titlesecured  ☠ Authenticated
goodcode      <div>This code is OK,</br>you are authenticated!</div>\n<div class='small light' style='padding:8px;'>%s</div>
  
httperror     Error %s
errwhitelist  Your credientials are OK,<br/>but an internal error occurred.<br/>Please tell the system admins !
errfolders    Incomplete CGI install (folders).
errtools      Incomplete CGI install (tools).
errhttps      Acces via http:// is disabled, use https:// instead.

createtitle   Account creation
newusername   <div title='If you are an administrator'>Create a new account (*)</div>
errnewuser    Illegal new user name. Use letters, digit, underscore and caret.
errnewservice Missing SERVICE in configuration.
errnewfqdn    Missing FQDN in configuration.
errnewqrtool  Missing 'qrencode' tool.
errnewsave    Failed to record the new<br>user "%s" into secret store.

newtitle      ☠ TOTP code generator
newheader     <h1 class='header'>New TOTP account</h1>
newqruser     <div>User: <b>%s</b></div>
newqrtitle    <div>Service: <b>%s</b></div>
newbody       <div>Here the QR code de <b>%s</b><br/><a href='https://play.google.com/store/apps/details?id=org.fedorahosted.freeotp'>Android</a> or <a href='https://itunes.apple.com/us/app/freeotp-authenticator/id872559395?mt=8'>iOS</a></div><div class='small' style='margin-top:0.5em;'>Any former code was invalided.</div>
newcheck      Then check it <a href='?'>here</a>.

#### End of localized strings
EOT
