#!/bin/bash

### BEGIN CONFIG

CFG_LOGDIR=/var/log/dyndns-cgi
CFG_KEYFOLDER=/var/www/dyndns-cgi/keys
CFG_DNSSERVER=8.8.8.8
CFG_TTL=60

### END CONFIG

set -u

cd "$(dirname "$0")"

abort() {
    echo -e -n "HTTP/1.1 $1 $2\r\n"
    echo -e -n "Status: $1\r\n"
    echo -e -n "Content-Type: text/plain; charset=UTF-8\r\n"
    echo -e -n "\r\n"
    echo -e -n "${3:-$2}\n"
    exit
}

requireapp() {
    if ! command -v "$1" &> /dev/null; then
        abort 500 "Internal Server Error" "'$1' not installed"
    fi
}

log() {
    local msg=$1
    echo -e "[$(date +"%Y-%m-%dT%H:%M:%S%z")] ${REMOTE_ADDR:--} ${HTTP_X_ARGS_USERNAME:--} $msg" >> "$CFG_LOGDIR/update.log"
}

#-> Check dependencies

requireapp openssl
requireapp dig
requireapp nsupdate

#-> GET parameters

GET_MODE=${HTTP_X_ARGS_MODE:-all}
GET_USERNAME=${HTTP_X_ARGS_USERNAME:-}
GET_PASSWORD=${HTTP_X_ARGS_PASSWORD:-}
GET_DOMAIN=${HTTP_X_ARGS_DOMAIN:-}
GET_IP=${HTTP_X_ARGS_IP:-}
GET_IP4=${HTTP_X_ARGS_IP4:-}
GET_IP6=${HTTP_X_ARGS_IP6:-}
REQUEST_ADDR=${REMOTE_ADDR:-}

if [ -z "$GET_USERNAME" ] || [ -z "$GET_PASSWORD" ] || [ -z "$GET_DOMAIN" ]; then
    abort 400 "Bad Request" "Required parameters missing"
fi

if ! [[ $GET_MODE =~ ^(all|request|parameter)$ ]]; then
    abort 400 "Bad Request" "Invalid value for parameter 'mode'"
fi

#-> Check for key file

KEYFILE=$(realpath -e "$CFG_KEYFOLDER/hmac-$GET_USERNAME.enc")

if ! ( echo "$KEYFILE" | grep -P "^$CFG_KEYFOLDER" ); then
    log "User unknown"
    abort 401 "Unauthorized" "User unknown"
fi

#-> Try to decrypt

HMACKEY=$( cat "$KEYFILE" | pass=$GET_PASSWORD openssl enc -aes-256-cbc -d -iter 1000 -a -salt -pass env:pass; exit ${PIPESTATUS[1]} )
KEYSTATUS=$?

if [ $KEYSTATUS -ne 0 ]; then
    log "Key decryption failed"
    abort 401 "Unauthorized" "Key decryption failed"
fi

FULLKEY="hmac-sha512:$GET_USERNAME:$HMACKEY"

#-> Find primary NS

PRIMARYNS=$( dig +noall +authority "$GET_DOMAIN" SOA "@$CFG_DNSSERVER" | grep -P "^[^.].+\.\s+" | awk '{print $5}'; exit ${PIPESTATUS[1]} )
NSSTATUS=$?

if [ $NSSTATUS -ne 0 ] || [ -z "$PRIMARYNS" ]; then
    log "Unable to get primary nameserver"
    abort 400 "Bad Request" "Unable to get the primary nameserver"
fi

#-> Check for changes

QUERY4=$(dig -y "$FULLKEY" +short "$GET_DOMAIN" A "@$PRIMARYNS")
QUERY6=$(dig -y "$FULLKEY" +short "$GET_DOMAIN" AAAA "@$PRIMARYNS")

# enforce use of request IP
if [ "$GET_MODE" == "request" ]; then
    GET_IP=""
    GET_IP4=""
    GET_IP6=""
    GET_MODE=all
fi

# auto assign when there is only a generic IP parameter
if [ -z "$GET_IP4" ] && [ -z "$GET_IP6" ] && [ -n "$GET_IP" ] && [[ $GET_IP == *"."* ]]; then
    GET_IP4=$GET_IP
elif [ -z "$GET_IP4" ] && [ -z "$GET_IP6" ] && [ -n "$GET_IP" ] && [[ $GET_IP == *":"* ]]; then
    GET_IP6=$GET_IP
fi

# use request IP for IPv4 if not defined explicit
if [ "$GET_MODE" == "all" ] && [ -z "$GET_IP4" ] && [ -n "$REQUEST_ADDR" ] && [[ $REQUEST_ADDR == *"."* ]]; then
    GET_IP4=$REQUEST_ADDR
fi

# use request IP for IPv6 if not defined explicit
if [ "$GET_MODE" == "all" ] && [ -z "$GET_IP6" ] && [ -n "$REQUEST_ADDR" ] && [[ $REQUEST_ADDR == *":"* ]]; then
    GET_IP6=$REQUEST_ADDR
fi

# generate nsupdate commands
CHANGES=""
QUEUE=""
QUEUE="$QUEUE\nserver $PRIMARYNS"

# IPv4 update
if [ -n "$GET_IP4" ] && [ ! "$QUERY4" == "$GET_IP4" ]; then
    if [ -n "$QUERY4" ]; then
        QUEUE="$QUEUE\nupdate del ${GET_DOMAIN}. ${CFG_TTL} IN A"
    fi
    QUEUE="$QUEUE\nupdate add ${GET_DOMAIN}. ${CFG_TTL} IN A ${GET_IP4}"
    CHANGES="$CHANGES; a=$GET_IP4"
fi

# IPv6 update
if [ -n "$GET_IP6" ] && [ ! "$QUERY6" == "$GET_IP6" ]; then
    if [ -n "$QUERY6" ]; then
        QUEUE="$QUEUE\nupdate del ${GET_DOMAIN}. ${CFG_TTL} IN AAAA"
    fi
    QUEUE="$QUEUE\nupdate add ${GET_DOMAIN}. ${CFG_TTL} IN AAAA ${GET_IP6}"
    CHANGES="$CHANGES; aaaa=$GET_IP6"
fi

QUEUE="$QUEUE\nsend"

if [ "$(echo -e "$QUEUE" | wc -l)" -gt 3 ]; then
    NSUPDATE=$(echo -e "$QUEUE" | nsupdate -y "$FULLKEY" 2>&1)
    NSRESULT=$?

    if [ $NSRESULT -eq 0 ]; then
        log "Update success; $(echo "$CHANGES" | sed -r 's/^[ ;]+//g' | sed -r 's/[ ;]+$//g')"
        abort 200 OK "Update success; $(echo "$CHANGES" | sed -r 's/^[ ;]+//g' | sed -r 's/[ ;]+$//g')"
    else
        log "Update failed; Exit Code = $NSRESULT; $NSUPDATE"
        log "Queue:\n$QUEUE"
        abort 400 "Bad Request" "Update failed"
    fi

else
    abort 200 OK "No changes"
fi
