/*
 * Copyright (C) 1994-2016 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *  
 * This file is part of the PBS Professional ("PBS Pro") software.
 * 
 * Open Source License Information:
 *  
 * PBS Pro is free software. You can redistribute it and/or modify it under the
 * terms of the GNU Affero General Public License as published by the Free 
 * Software Foundation, either version 3 of the License, or (at your option) any 
 * later version.
 *  
 * PBS Pro is distributed in the hope that it will be useful, but WITHOUT ANY 
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
 * 
 * Use of Altair’s trademarks, including but not limited to "PBS™", 
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
 * trademark licensing policies.
 *
 */
 /**
  * @file	pbs_renew.c
  */
#include <stdio.h>
#include <fcntl.h>
#include <unistd.h>
#include <errno.h>
#include <signal.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/time.h>
#include <krb5.h>

char	*who;
int	dbprt = 0;
int	dienow = 0;
#define	DBPRT	if (dbprt) fprintf

/**
 * @brief
 *	Don't do anything for an alarm signal.  We just want to
 *	break out of a wait.
 *	Set a flag for a term signal.  We need to die.
 *
 * @param[in] sig - signal number
 *
 * @return Void
 *
 */
void
gotsig(int sig) {
	DBPRT(stderr, "signal %d\n", sig);

	if (sig == SIGTERM)
		dienow = 1;

	return;
}

#define	GRACE	600

/**
 * @brief
 *	calculates the time required for renewal of credentials 
 *	
 * @param[on] endtime - timeline for credentials expiry.
 *
 * @return - Error Code
 * @retval   0  Success - meaning no need to change credentials
 * @retval   !0 Failure - meaning endtime exceeded, time to change credentials
 * 
 */
unsigned int
wakeup(time_t endtime)
{
	unsigned int		deadin;
	time_t			now;

	/*
	 **	Calculate how long to wait before doing a renewal.
	 */
	now = time(0);
	if (now > endtime) {	/* cred dead */
		DBPRT(stderr, "credentials expired\n");
		return 0;
	}
	deadin = endtime - now;
	if (deadin < GRACE) {			/* don't bother */
		DBPRT(stderr, "almost dead\n");
		return 0;
	}
	return deadin - (GRACE / 2);
}

int
main(int argc, char *argv[])
{
	char			errmsg[1024];
	struct sigaction	act;
	krb5_error_code		err;
	int			i;
	pid_t			pid;
	uid_t			uid;
	int			status;
	int			ret = 13;
	const char		*ccdefault;
	krb5_context		ktext;
	krb5_creds		creds;
	krb5_ccache		kache = NULL;
	krb5_principal		client = 0;
	krb5_cc_cursor		kursor;
	unsigned int		runfor = 0;

	/*test for real deal or just version and exit*/

	execution_mode(argc, argv);

	who = argv[0];
	if (argc == 1) {
		fprintf(stderr,
			"usage: %s [-d] command [arg(s)]\n", who);
		fprintf(stderr, "       %s --version\n", who);
		return 1;
	}

	uid = getuid();
	if ((uid != 0) && (geteuid() == 0))
		seteuid(uid);

	i = 1;
	if (strcmp(argv[1], "-d") == 0) {
		dbprt = 1;
		i++;
	}
	if ((pid = fork()) == -1) {
		sprintf(errmsg, "%s: fork", who);
		perror(errmsg);
		return 1;
	}
	if (pid == 0) {		/* child */
		char	**newv = &argv[i];

		execvp(newv[0], newv);
		/* should not get here */
		sprintf(errmsg, "%s: execvp %s", who, newv[0]);
		perror(errmsg);
		exit(99);
	}

	if ((err = krb5_init_context(&ktext)) != 0) {
		com_err(who, err, ": krb5_init_context");
		goto loop;
	}

	memset((char *)&creds, 0, sizeof(creds));
	ccdefault = krb5_cc_default_name(ktext);
	if ((err = krb5_cc_resolve(ktext, ccdefault, &kache)) != 0) {
		com_err(who, err, ": krb5_cc_resolve");
		goto loop;
	}

	if ((err = krb5_cc_get_principal(ktext, kache, &client)) != 0) {
		com_err(who, err, "(ticket cache %s)", ccdefault);
		goto loop;
	}

	/* fetch tgt directly from cache */
	if ((err = krb5_cc_start_seq_get(ktext, kache, &kursor)) != 0) {
		com_err(who, err, "krb5_cc_start_seq_get");
		goto loop;
	}
	err = krb5_cc_next_cred(ktext, kache, &kursor, &creds);
	(void)krb5_cc_end_seq_get(ktext, kache, &kursor);
	if (err != 0) {
		com_err(who, err, "krb5_cc_next_cred");
		goto loop;
	}

	sigemptyset(&act.sa_mask);
	act.sa_flags = 0;
	act.sa_handler = gotsig;
	sigaction(SIGALRM, &act, NULL);
	sigaction(SIGTERM, &act, NULL);

	runfor = wakeup(creds.times.endtime);

loop:
	for (;;) {
		time_t		credend = creds.times.endtime;

		if (runfor > 0) {
			DBPRT(stderr, "wait for %u seconds\n", runfor);
			alarm(runfor);
		}
		pid = wait(&status);
		alarm(0);
		if (pid == -1) {
			if (errno != EINTR) {
				sprintf(errmsg, "%s: wait", who);
				perror(errmsg);
				break;
			}
		}
		else if (pid > 0) {
			if (WIFEXITED(status))
				ret = WEXITSTATUS(status);
			DBPRT(stderr, "child %d reaped status %d\n", pid, ret);
			break;
		}
		if (dienow)
			break;

		runfor = 0;
		if ((err = krb5_get_renewed_creds(ktext, &creds,
			client, kache, NULL)) != 0) {
			com_err(who, err, ": krb5_get_renewed_creds");
			continue;
		}

		if ((err = krb5_cc_initialize(ktext, kache,
			creds.client)) != 0) {
			com_err(who, err, ": krb5_cc_initialize");
			continue;
		}
		if ((err = krb5_cc_store_cred(ktext, kache, &creds)) != 0) {
			com_err(who, err, ": krb5_cc_store_cred");
			continue;
		}
		if (creds.times.endtime == credend) {
			DBPRT(stderr, "endtime unchanged\n");
			runfor = 0;
		}
		else {
			DBPRT(stderr, "credentials renewed\n");
			runfor = wakeup(creds.times.endtime);
		}
	}

	krb5_cc_destroy(ktext, kache);
	krb5_free_context(ktext);
	return ret;
}
