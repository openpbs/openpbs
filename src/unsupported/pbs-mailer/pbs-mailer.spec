Name:    pbs-mailer
Version: 1.0
Release: 1
Summary: pbs-mailer
BuildRequires: systemd, filesystem

License: Public Domain
Source0: pbs-mailer-%{version}.tar.gz

%define debug_packages %{nil}
%define debug_package %{nil} 

%description
pbs-mailer

%prep
%setup

%build

%install
install -D -m 644 pbs-mailer.service %{buildroot}%{_unitdir}/pbs-mailer.service
install -D -m 744 pbs_mail_saver %{buildroot}/opt/pbs/bin/pbs_mail_saver
install -D -m 744 pbs_mail_sender %{buildroot}/opt/pbs/bin/pbs_mail_sender
install -D -m 744 pbs_mail.json %{buildroot}/opt/pbs/etc/pbs_mail.json

%post
%systemd_post pbs-mailer.service

%preun
%systemd_preun pbs-mailer.service

%postun
%systemd_postun_with_restart pbs-mailer.service

%files
/opt/pbs/bin/pbs_mail_saver
/opt/pbs/bin/pbs_mail_sender
%{_unitdir}/pbs-mailer.service
%config /opt/pbs/etc/pbs_mail.json

%changelog
