#!/bin/bash

VERSION="1.0"

rm pbs-mailer-$VERSION -rf
mkdir -p pbs-mailer-$VERSION

cp pbs-mailer.spec pbs-mailer-$VERSION/
cp pbs_mail_saver pbs-mailer-$VERSION/
cp pbs_mail_sender pbs-mailer-$VERSION/
cp pbs_mail.json pbs-mailer-$VERSION/
cp debian/pbs-mailer.service pbs-mailer-$VERSION/

tar -cvzf pbs-mailer-${VERSION}.tar.gz pbs-mailer-$VERSION
rm pbs-mailer-$VERSION -rf

mkdir -p ~/rpmbuild/SOURCES/
mv pbs-mailer-${VERSION}.tar.gz ~/rpmbuild/SOURCES/

rpmbuild -ba pbs-mailer.spec
