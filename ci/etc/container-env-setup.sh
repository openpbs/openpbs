export container=docker
export TERM=xterm
if [ -e /etc/debian_version ]; then
  export DEBIAN_FRONTEND=noninteractive
fi
export LOGNAME=${LOGNAME:-"$(id -un)"}
export USER=${USER:-"$(id -un)"}
export TZ=UTC
export PBS_TZID=UTC
export PATH="$(printf "%s" "/usr/local/bin:/usr/local/sbin:${PATH}" | awk -v RS=: -v ORS=: '!($0 in a) {a[$0]; print}')"
export DOMAIN=$(hostname -d)
export PERL5LIB=${HOME}/AUTO/lib/perl5/site_perl
export PERL5LIB=${PERL5LIB}:${HOME}/AUTO/lib/site_perl
export PERL5LIB=${PERL5LIB}:${HOME}/AUTO/share/perl5
export PERL5LIB=${PERL5LIB}:${HOME}/AUTO/share/perl
export PBS_TEST_DEBUG=1
export PBS_TEST_VERBOSE=1
export PBS_PRINT_STACK_TRACE=1
export MAIL="${MAIL:-"/var/mail/$(id -un)"}"
