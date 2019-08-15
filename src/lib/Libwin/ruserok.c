/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
 * FOR A PARTICULAR PURPOSE.
 * See the GNU Affero General Public License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * For a copy of the commercial license terms and conditions,
 * go to: (http://www.pbspro.com/UserArea/agreement.html)
 * or contact the Altair Legal Department.
 *
 * Altair’s dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of PBS Pro and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair’s trademarks, including but not limited to "PBS™",
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's
 * trademark licensing policies.
 *
 */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <io.h>
#include "win.h"
#include "pbs_ifl.h"
#include "log.h"
/**
 * @file	ruserok.c
 */
/**
 * @brief
 * 	match_rhosts_entry; matches the rhosts entries in rhosts file.
 *
 * @param[in] path - file path
 * @param[in] rhost - remote host content
 * @param[in] ruser - remote user name
 *
 * @return	int
 * @retval	1	if it found a "rhosts ruser" entry in  rhosts file.
 * @retval	0	if not found
 * @retval	-1	if user's .rhosts could not be read
 *
 * @par	Note:If username entry in path is quoted means that it has special
 *	chars like spaces and will be matched.
 *
 */

static int
match_rhosts_entry(char *path, char *rhost, char *ruser)
{
	MY_FILE	*fp;
	char	buf[512+1];
	char	*luser;
	char	*lhost;
	char	ruserq[512+1];
	char	logb[LOG_BUF_SIZE] = {'\0' } ;

	if ((fp=my_fopen(path, "r")) == NULL) {
		sprintf(logb,
			"open of file %s failed! Need SYSTEM or Everyone read access",
			path);
		log_err(-1, "match_rhosts_entry", logb);
		return (-1);
	}

	sprintf(ruserq, "\"%s\"", ruser);

	while (my_fgets(buf, sizeof(buf), fp) != NULL) {
		buf[strlen(buf)-1] = '\0';

		lhost = strtok((char *)buf, " \t");
		luser = strtok(NULL, " \t");
		sprintf(logb,"match_rhosts_entry: scanning (%s,%s)...", lhost, luser);
		log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", logb);
		if( (lhost && strcmpi(lhost, rhost) == 0) && \
		    (luser && \
			(strcmpi(luser, ruser) == 0 ||
			strcmpi(luser, ruserq) == 0))) {
			my_fclose(fp);
			return (1);
		}
	}
	sprintf(logb,"match_rhosts_entry: did not match (%s,%s) in %s", rhost,
		ruser, path);
	log_err(-1, "match_rhosts_entry", logb);
	my_fclose(fp);
	return (0);
}
/**
 * @brief
 * 	match_hosts_equiv_entry;
 *	The format of a hosts.equiv is as follows:
 *
 *	[+|-] [hostname] [username]
 *	+ means to allow access
 *	- means to deny access
 *	if [hostname] is given, then all accounts at [hostname] are allowed to
 *	access SIMILARLY named accounts on LOCALHOST
 *	if [username] is given, then [username] at any remote hosts is allowed to
 *	access ANY account (except root) on LOCALHOST.
 *	if both [hostname] [username] are given, then [username] @ [hostname] is
 *	allowed access to ANY account on LOCALHOST.
 *
 * @par	NOTE: If [username] entry in path is quoted means that it has special
 *	chars like spaces and will be matched.
 *
 * @return	int
 * @retval	1	if ruser@rhost will have access to luser@LOCALHOST
 * @retval	0	if any error
 *
 */
static int
match_hosts_equiv_entry(char *path, char *rhost, char *ruser, char *luser)
{
	MY_FILE	*fp;
	char	buf[512+1];
	char	wruser[512+1];
	char	*pc, *pc0, *pc1;
	int	i, len;
	char	*h[3];
	char	logb[LOG_BUF_SIZE] = {'\0' } ;

	if ((fp=my_fopen(path, "r")) == NULL)
		return (0);

	while (my_fgets(buf, sizeof(buf), fp) != NULL) {
		len=strlen(buf)-1;
		if (buf[len] == '\n')
			buf[len] = '\0';

		i=0;
		h[0] = NULL;
		h[1] = NULL;
		h[2] = NULL;

		wruser[0] = '\0';
		pc0 = strchr(buf, '\"');
		pc1 = strrchr(buf,'\"');
		if (pc0 && pc1 && (pc1 > pc0)) {
			pc0++;
			*pc1 = '\0';
			strcpy(wruser, pc0);
			*pc1 = '\"';
		}

		pc = strtok((char *)buf, " \t");
		while (pc && i < 3) {
			h[i] = pc;
			i++;
			if (strchr(pc, '\"'))	/*quoted username due to space*/
				break;
			pc = strtok(NULL, " \t");
		}

		sprintf(logb,"match_hosts_equiv_entry: scanning (%s,%s,%s)...wruser=%s",
			(h[0]?h[0]:"null"),
			(h[1]?h[1]:"null"),
			(h[2]?h[2]:"null"), wruser);
		log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG,PBS_EVENTCLASS_FILE, LOG_NOTICE, "", logb);
		switch (i) {
			case 0:
				continue;
			case 1:
				if (strcmpi(h[0], "+") == 0)
					goto match;	/* '+', access to all */
				if( strcmpi(h[0], ruser) == 0 || \
			    strcmpi(wruser, ruser) == 0 )
					goto match;	/* [username], username access to all */
				if( strcmpi(h[0], rhost) == 0 && \
			    		strcmpi(ruser, luser) == 0 )
					goto match;	/* [hostname], ruser access to luser */
				/* if ruser == luser */
				break;
			case 2:
				if (strcmpi(h[0], "+") == 0) {
					if( strcmpi(h[1], ruser) == 0  || \
				strcmpi(wruser, ruser) == 0 )
						goto match;/*[+ username],username access to all*/
					if( strcmpi(h[1], rhost) == 0 && \
					strcmpi(ruser, luser) == 0 )
						goto match; /* [+ hostname], ruser access to
						     /* luser if ruser == luser */
				} else if( strcmpi(h[0], rhost) == 0 && \
				   (strcmpi(h[1], ruser) == 0 || \
				    strcmpi(wruser, ruser) == 0) ) {
					goto match; /* [hostname username], */
					/* username@hostname has access to
					 /* luser */
				}
				break;
			case 3:
				if( strcmpi(h[0], "+") == 0 && \
			    strcmpi(h[1], rhost) == 0 && \
			    (strcmpi(h[2], ruser) == 0 || \
			     strcmpi(wruser, ruser) == 0) )
					goto match; /* [+ hostname username], */
				/* username@hostname has access to */
				/* luser */
				break;
		}
	}

	sprintf(logb,"match_hosts_equiv: did not match (%s,%s (luser=%s)) in %s",
		rhost, ruser, luser, path);
	log_err(-1, "match_hosts_equiv_entry", logb);
	my_fclose(fp);
	return (0);

	match:	my_fclose(fp);
	return (1);
}

/**
 * @brief
 * 	check whether to allow access for users.
 *
 * @param[in] rhost - remote hosts
 * @param[in] superuser - val to indicate whether superuser
 * @param[in] ruser - remote user
 * @param[in] luser - local user
 *
 * @return	int
 * @retval	0	if access is allowed
 * @retval	-1	if access is denied
 * @retval	-2	if user does not exist
 * @retval	-3	problem reading user's .rhosts file.
 * 
 * @par	Note:
 *	Checks if (ruser,rhost) can access account
 *	luser@LOCALHOST. The hosts.equiv or user's .rhosts is consulted.
 *
 */
int
ruserok(const char *rhost, int superuser, const char *ruser, const char *luser)
{
	char	hosts_equiv[MAXPATHLEN+1];
	char	rhosts[MAXPATHLEN+1];
	struct  stat sbuf;
	int	rc = 1;
	struct  passwd *pw;
	int	user_impersonate = 0;
	char	logb[LOG_BUF_SIZE] = {'\0' } ;

	/* see if local user exists! */
	if ((pw = getpwnam((char *)luser)) == NULL) {
		sprintf(logb,"user %s does not exist!", luser);
		log_err(-1, "ruserok", logb);
		return (-2);
	}

	/* Let's construct the hosts.equiv file */
	sprintf(hosts_equiv, "%s\\system32\\drivers\\etc\\hosts.equiv",
		get_saved_env("SYSTEMROOT"));
	if (stat(hosts_equiv, &sbuf) != 0) {
		sprintf(hosts_equiv, "%s\\hosts.equiv",
			get_saved_env("SYSTEMROOT"));
	}

	/* check hosts.equiv file if luser is not superuser */
	if( !superuser && \
		chk_file_sec(hosts_equiv, 0, 0, WRITES_MASK^FILE_WRITE_EA, 0) == 0 && \
		  match_hosts_equiv_entry(hosts_equiv, rhost, ruser, luser) )
		return (0);

	/* check luser's .rhosts file */
	/* Let's construct the $HOME/.rhosts file */
	/* have to read .rhosts as user */
	if (pw->pw_userlogin != INVALID_HANDLE_VALUE) {
		ImpersonateLoggedOnUser(pw->pw_userlogin);
		user_impersonate =1;
	}

	strcpy(rhosts, getRhostsFile(pw->pw_name, pw->pw_userlogin));

	rc = match_rhosts_entry(rhosts, rhost, ruser);
	if (user_impersonate)
		RevertToSelf();

	if (rc == 1)		/* ok */
		return (0);
	else if (rc < 0)	/* some error occurred */
		return (-3);
	else			/* absolutely no match */
		return (-1);
}
