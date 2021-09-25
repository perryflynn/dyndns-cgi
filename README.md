# dyndns-cgi

A CGI wrapper for [RFC2136 nsupdate](https://serverless.industries/2020/09/27/dns-nsupdate-howto.en.html).

Compatible to AVM Fritz!Box, Ubiquiti EdgeRouter and many more.

## How it works

The HMAC keys to send updates to nameservers **are encrypted**.

The keyname and the passphrase are the username and password for the script.

### GET /cgi-bin/dyndns.cgi

The default endpoint.

Used by AVM Fritz!Box.

| GET parameter | Description | Example |
|---------------|-------------|---------|
| mode | Controls if the IP address should be picked from the query parameters or from the request header | `all`: parameters and request IP are used, `request`: request IP are used, `parameter`: query parameters are used |
| username | The name of the HMAC key used by nsupdate | `exampleddns` = `/var/www/dyndns-cgi/keys/hmac-exampleddns.enc` |
| password | Passphrase used to decrypt the HMAC key | |
| domain | The domain to update | ddns.example.com |
| ip4 | IPv4 address to use | 127.0.0.1 |
| ip6 | IPv6 address to use | ::1 |
| ip | IPv4 or IPv6 address to use, parameter is ignored when `ip4` or `ip6` are defined | 127.0.0.1 |

### GET /nic/dyndns

DynDNS Version 1.

Endpoint requires HTTP Basic Authentication.

| GET parameter | Description | Example |
|---------------|-------------|---------|
| host_id | The domain to update | ddns.example.com |
| myip | IPv4 or IPv6 address to use | 127.0.0.1 |

### GET /nic/update

DynDNS Version 2.

Used by Ubiqiti EdgeRouter.

Endpoint requires HTTP Basic Authentication.

| GET parameter | Description | Example |
|---------------|-------------|---------|
| hostname | The domain to update | ddns.example.com |
| myip | IPv4 or IPv6 address to use | 127.0.0.1 |

### Examples

```sh
# original endpoint
curl "https://ns.example.com/cgi-bin/dyndns.cgi?username=exampleddns&password=eeh2phioyaa6ro1eiphuaRiuthee8EiJ&ip4=127.0.0.1&ip6=::1"
```

```sh
# dyndns1
# picked from ubiquiti edge router
curl -u exampleddns:eeh2phioyaa6ro1eiphuaRiuthee8EiJ "https://ns.example.com/nic/dyndns?action=edit&started=1&hostname=YES&host_id=ddns.example.com&myip=127.0.0.1"
```

```sh
# dyndns2
# picked from ubiquiti edge router
curl -u exampleddns:eeh2phioyaa6ro1eiphuaRiuthee8EiJ "https://ns.example.com/nic/update?system=dyndns&hostname=ddns.example.com&myip=127.0.0.1"
```

## Install

### Packages

```sh
apt install dnsutils nginx-full libnginx-mod-http-lua fcgiwrap
```

### Files

Place files on your Debian/Ubuntu system just like they are in the [src/](src/) folder.

If you run another Linux Distribution you may need to do some changes.

### Configure NGINX

All required configs can be found in [src/etc/nginx/dyndns_cgi.conf](src/etc/nginx/dyndns_cgi.conf).

It must be included into a NGINX virtual host.

A example virtual host config can be found in [src/etc/nginx/sites-enabled/example.conf](src/etc/nginx/sites-enabled/example.conf).

### Generate a HMAC key and encrypt it

Generate a password:

```txt
perry@localhost ~$ pwgen 32 1
eeh2phioyaa6ro1eiphuaRiuthee8EiJ
```

Create a HMAC Key:

```txt
perry@localhost ~$ dnssec-keygen -a HMAC-SHA512 -b 512 -n HOST exampleddns
Kexampleddns.+165+26667

perry@localhost ~$ cat Kexampleddns.+165+26667.private
Private-key-format: v1.3
Algorithm: 165 (HMAC_SHA512)
Key: 0L0iTAPeXmyWbu0wJMsWw52GqVfeL22aZE2xmhlNcrXNdCgF3262ifx2yIuJs+T1H8CWdV+79HClWOzwvnn/LA==
Bits: AAA=
Created: 20210925150939
Publish: 20210925150939
Activate: 20210925150939
```

Encrypt the key with the password:

```txt
root@localhost ~# echo -n "0L0iTAPeXmyWbu0wJMsWw52GqVfeL22aZE2xmhlNcrXNdCgF3262ifx2yIuJs+T1H8CWdV+79HClWOzwvnn/LA==" | openssl enc -aes-256-cbc -e -iter 1000 -a -salt > /var/www/dyndns-cgi/keys/hmac-exampleddns.enc
enter aes-256-cbc encryption password: eeh2phioyaa6ro1eiphuaRiuthee8EiJ
Verifying - enter aes-256-cbc encryption password: eeh2phioyaa6ro1eiphuaRiuthee8EiJ
```

Add the key to your BIND9 nameserver:

```txt
key exampleddns {
    algorithm hmac-sha512;
    secret "0L0iTAPeXmyWbu0wJMsWw52GqVfeL22aZE2xmhlNcrXNdCgF3262ifx2yIuJs+T1H8CWdV+79HClWOzwvnn/LA==";
};
```

Of course you need now **add update policies to the zone** as well.
