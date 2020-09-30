### pbs-mailer

OpenPBS can easily send a huge amount of emails to one user/email. pbs-mailer is a service for an aggregation of emails sent by OpenPBS to the same user/email. The first email is sent immediately and subsequent emails are sent after a configurable time period. The emails are squashed into one email.

### Building package

* RPM package: run  'release-rpm.sh'
* DEB package: run  'release-deb.sh'

### Manual instalation

Move pbs_mail.json, pbs_mail_saver, and pbs_mail_sender into an appropriate location.

### Configure the mailer

The configuration file is pbs_mail.json. This file is located in /opt/pbs/etc/ by default.

* pidfile - the daemon's PID file location
* sqlite_db - sqlite database location
* sendmail - path to sendmail
* gathering_period -  during this period the emails are gathered
* mailer_cycle_sleep - the length of sleep before the next sender periods begin
* add_servername - add the server name to the email
* send_begin_immediately - if true, the notification of beginning job or reservation is sent immediately (together with already gathered emails) - the gathering_period is shortened

### Configure the pbs_server

* Set the server attribute 'mailer' to 'pbs_mail_saver'. E.g.: 'set server mailer = /opt/pbs/bin/pbs_mail_saver'
* Start the pbs-mailer (pbs_mail_sender) service.

