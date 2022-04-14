### Single-file bash CGI script for Time-based one-time password (TOTP). ###

  * Use it to run a configured script.
  * Administrative accounts can generate or re-generate user accounts.
  * Time-limited key codes are available
  * Authenticate with any standard TOTP application (like FreeOTP or Google Authenticator)

### Licence & author ###

This script is (c) 2022 jeremie.francois@gmail.com

It is distributed as CC-BY-SA (see https://creativecommons.org/licenses/by-sa/4.0/)

### Dependencies ###

This script only needs:

  * `oathtool` (eg. via `apt install`)
  * `base32`   (brought by `coreutils`, hence probably already installed)
  * a TOTP application. A good and opensource one is RedHat's:
    * https://play.google.com/store/apps/details?id=org.fedorahosted.freeotp
    * https://itunes.apple.com/us/app/freeotp-authenticator/id872559395?mt=8

Users need to record their QR code once after it is generated by an administrator.

Administrators are themselves identified by the same protocol.

### Project files ###

Not that many actually. The important ones are `index.cgi` and `secrets/timed_login.sh` (the
latter is just one example of action called by the former). Also, `secrets/totp/` contains
one file per user, with the corresponding TOTP generative data. The `secrets/reveal/` is
explained below.

```
.
├── .gitignore
├── index.cgi
├── README.md
└── secrets
    ├── reveal
    │   └── admin_reMOVe
    ├── totp
    │   ├── admin
    │   └── admin_qr_code.png
    ├── .htaccess
    ├── show_key.sh
    └── timed_login.sh
```

### Configuration ###

You can configure the script either with a local file named `secrets/totp_cgi.conf` or with a 
system-wide `/etc/totp_cgi.conf`. The following key/value pairs are handled (but remove remarks):

  * `ALLOWTOOL=...`          the tool to white-list users. Must be set. Default does nothing.
  * `HTTPS_ONLY=y`           'y' forbids running the interface without HTTPS (check, eg. let's encrypt)
  * `USERNAME=`              default username (eg 'guest')
  * `REVEALTIMEOUT=300`      expriring delay for revealing codes (5 minutes). Zero to disable.
  * `ADMINS=admin,jeremie`   comma-separated list of usernames who can create other users
  * `FQDN=totp.tecrd.com`    your fully qualified domain name (shown in the smartphone app)
  * `SERVICE=nextcloud`      the name of your service (shown in the smartphone app)
  * `XHEADER=<style type="text/css">...`  added to the HTTP header, eg. to help customize your HTML pages

#### White listing #### 

Probably the most important key to set is `ALLOWTOOL` because it lets you specify the script
that will be called when an authentication is sucessful. The command that the scripts run is:

```
$ALLOWTOOL allow "$REMOTE_ADDR" "$USERNAME"
```

It will run from within the `secrets/` directory.
Please note that it is called arguably unsafely **without quoting** (to make life easier).

A small "IP white listing" utility is provided as an example:

  * `whitelisters/timed_login.sh` to manage a more powerful user and time-based login file

##### Usage with NGINX #####

For NGINX you can use the following configuration:

```
ALLOWTOOL=./timed_login.sh allow "%USERNAME%" "%IP%" export nginx > nginx_allow.conf && sudo /usr/sbin/service nginx reload
```

With, e.g `/etc/sudoers.d/50-totp-whitelist`:

```
data ALL = (root) NOPASSWD: /usr/sbin/service nginx reload
```

#### Post-installation ####

Do not forget to delete or change
  * user `admin` after you use it to create new accounts.
  * the corresponding revealing key `secrets/reveal/admin_reMOVe`

To get the current TOTP code for this default user, you can use the `admin_reMOVe` revealing
key as described below or run `secrets/show_key.sh`.


### Administration ###

#### Regular admins ####

If your username is within the `ADMINS` configuration list you will be able to create user accounts.
To do so, click the default Admin link in the footer or use the special `.../index.cgi?admin` URL.
you will see a third field in the regsitration form where you can type a username after your own,
regular identification.

The script will generate a new TOTP-enabling QR code to be scanned by the respective user.
Any previous code for the user will be invalidated, so use it to revoke a former account (or delete
the respective file in `secrets/`).

**Important** : the generated user-specific QR code MUST be scanned by the TOTP smartphone application.
It will be shown only once, so you need the user to see it.
Try to avoid screen copies since the QR code shall be forgotten once recorded to avoid identity theft.
Better generate the account when the user is with you and ready to scan the code on your screen.

#### Revealing keys #### 

This feature allows **password** authentication, but with a configurable, longer timeout than TOTP.

Eg. if you need to tell the TOTP code to someone else, both of you must be pretty reactive since
it changes every 30 seconds. Or you need to provide a temporary access for someone that did not even
register (like a guest), or for someone who lost his phone, or did not install the TOTP application.

Hence, you can define 6-letter *keycodes* that help reveal the actual, current TOTP code for a
given user account. The key code are usable for a longer, configurable time.

How ? For now you need an SSH access to the server. Then simply `touch secrets/reveal/guest_SIXsix`
to create password `SIXsix` for user `guest`. This code can be used *in place of the TOTP* code for
the interface, in order to reveal the actual TOTP code (that will have to be typed). The user `guest`
will not even need to know or have the original subscription QR code.

Key codes expire 5 minutes after they are created by default (tune it globally with `REVEALTIMEOUT`
above). But you can cheat it by faking the creation date of the file: `touch -t 202206011200 jeremie_JerEMy`
creates a revealing code for user `jeremie` that will expire 5 minutes after 12h00 on 1st of June, 2022.

Limitation: key codes MUST be exactly 6-letter long, and alphanumeric only.


#### Localization ####

Localization is supported, and translations are defined at the end of the script itself.
The script knows the language based on the provided client navigator settings.

I am open to pull requests for more langages, and/but I want to keep it as one script !


### Web server configuration ###

Here are example of configurations. YMMV.

#### Apache2 (example) ####

If the CGI script is saved in `/usr/lib/cgi-bin/totp`, then
create `/etc/apache2/conf-available/serve-cgi-bin.conf`:


```
<IfModule mod_alias.c>
	<IfModule mod_cgi.c>
		Define ENABLE_USR_LIB_CGI_BIN
	</IfModule>

	<IfModule mod_cgid.c>
		Define ENABLE_USR_LIB_CGI_BIN
	</IfModule>

	<IfDefine ENABLE_USR_LIB_CGI_BIN>
		ScriptAlias /cgi-bin/ /usr/lib/cgi-bin/
		<Directory "/usr/lib/cgi-bin">
			AllowOverride None
			Options +ExecCGI -MultiViews +SymLinksIfOwnerMatch
			Require all granted
		</Directory>
	</IfDefine>
</IfModule>
```

Then `a2enconf serve-cgi-bin.conf`, restart apache and head to https://your.website.com/cgi-bin/totp


#### nginx and fcgiwrap ####

Install `nginx` and `fcgi`:

  * `apt-get install nginx fcgiwrap`
  * `cp /usr/share/doc/fcgiwrap/examples/nginx.conf /etc/nginx/fcgiwrap.conf`

If the script is located in `/home/toctoc`, then you
can add a block like this *within* the `/etc/nginx/sites-enabled` target:

```
	location /toctoc {
		gzip off;
		try_files $uri $uri/;
		fastcgi_index index.cgi;
		alias /home/;
		fastcgi_pass unix:/var/run/fcgiwrap.socket;
		location ~ /secrets {return 403;}
		include /etc/nginx/fastcgi_params;
		# Adjust non standard parameters
		fastcgi_param QUERY_STRING     $query_string;
		fastcgi_param REMOTE_USER      $remote_user;
	}
```

Then restart nginx and open http://your.website.com/totp_cgi/
