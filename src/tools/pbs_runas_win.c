/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
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
/**
 * @file
 *		pbs_runas_win.c
 *
 * @brief
 *		This file contains security related functions of PBS.
 *
 * Functions included are:
 * 	decrypt_pwd()
 * 	jobid_read_cred()
 * 	usage()
 * 	main()
 *
 */
#include <pbs_config.h>
#include <sys/types.h>
#include <sys/socket.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <stdio.h>
#include <unistd.h>
#include <stdlib.h>
#include <fcntl.h>
#include <string.h>
#include <netdb.h>
#include <ntsecapi.h>
#include "pbs_ifl.h"
#include "pbs_version.h"
#include <lmaccess.h>
#include <lm.h>
#include <conio.h>
#include <ctype.h>
#include "libpbs.h"
#include "list_link.h"
#include "attribute.h"
#include "server_limits.h"
#include "credential.h"
#include "ticket.h"
#include "batch_request.h"
#include "pbs_nodes.h"
#include "job.h"
#include "reservation.h"
#include "log.h"
#include <sys/stat.h>
#include <errno.h>
#include <assert.h>
#include <Userenv.h>

#define CMDLINE_LEN	4096
char	path_jobs[MAXPATHLEN+1];

/**
 * @brief
 * 	 	jobid_read_cred
 *		Check if this jobid has an associated credential file.  If it does,
 *		the credential file is opened and the credential is read into
 *		malloc'ed memory.
 *
 * @param[in]	jobid	-	Job Id.
 * @param[out]	cred	-	Encrypted password.
 * @param[out]	len	-	Length of the password.
 *
 * @return	int
 * @retval	1	: no cred
 * @retval	0	: there is cred
 * @retval	-1	: error
 */
int
jobid_read_cred(char *jobid, char **cred, size_t *len)
{
	char		name_buf[MAXPATHLEN+1];
	char		*hold = NULL;
	struct	stat	sbuf;
	int		fd;
	int		ret = -1;

	(void)strcpy(name_buf, path_jobs);
	(void)strcat(name_buf, jobid);
	(void)strcat(name_buf, JOB_CRED_SUFFIX);

	if ((fd = open(name_buf, O_RDONLY)) == -1) {
		if (errno == ENOENT)
			return 1;
		fprintf(stderr, "Failed to open %s\n errno=%d\n",
			name_buf, errno);
		return ret;
	}

	if (fstat(fd, &sbuf) == -1) {
		fprintf(stderr, "Failed to fstat %s\n errno=%d\n",
			name_buf, errno);
		goto done;
	}

	hold = malloc(sbuf.st_size);
	assert(hold != NULL);

	setmode(fd, O_BINARY);

	if (read(fd, hold, sbuf.st_size) != sbuf.st_size) {
		fprintf(stderr, "read error of %s\n errno=%d\n",
			name_buf, errno);
		goto done;
	}
	*len = sbuf.st_size;
	*cred = hold;
	hold = NULL;
	ret = 0;

done:
	close(fd);
	if (hold != NULL)
		free(hold);
	return ret;
}
/**
 * @brief
 * 		This function describes the usage of the file like helper doc.
 *
 * @param[in]	name	-	program name
 */
void
usage(char *prog)
{
	fprintf(stderr,
		"%s /user:<pbs_user> /jobid:<pbs_jobid> <prog> [<arg1> <arg2> ... <argN>\n", prog);
}
/**
 * @brief
 * 		main - the entry point in pbs_runas_win.c
 *
 * @param[in]	argc	-	argument count
 * @param[in]	argv	-	argument variables.
 *
 * @return	int
 * @retval	0	: success
 * @retval	!=0	: error code
 */
main(int argc, char *argv[])
{
	int 	i;
	int	ecode = 0;
	char 	pbsuser[UNLEN+1];
	char 	jobid[PBS_MAXSVRJOBID+1];
	char 	*p = NULL;
	char	cmd_line[CMDLINE_LEN];
	char	actual_cmd_line[CMDLINE_LEN*2];
	char	*usercred_buf = NULL;
	size_t	usercred_len = 0;
	struct  passwd *pwdp = NULL;
	char	msg[LOG_BUF_SIZE];
	int     flags = CREATE_DEFAULT_ERROR_MODE|CREATE_NEW_PROCESS_GROUP|CREATE_UNICODE_ENVIRONMENT;
	LPVOID  user_env = NULL;
	STARTUPINFO             si = { 0 };
	PROCESS_INFORMATION     pi = { 0 };
	int			rc;
	HANDLE	hToken = INVALID_HANDLE_VALUE;
	i = 1;
	strcpy(jobid, "");
	strcpy(pbsuser, "");
	while (i < argc) {

		if (strncmp(argv[i], "/user:", 6) == 0) {

			p = strchr(argv[i], ':');
			strcpy(pbsuser, p+1);

			i++;
		} else if (strncmp(argv[i], "/jobid:", 7) == 0) {
			char *p;

			p = strchr(argv[i], ':');
			strcpy(jobid, p+1);

			i++;
		} else {
			break;
		}
	}

	/* process command line */
	strcpy(cmd_line, "");
	while (i < argc) {
		strcat(cmd_line, " ");
		strcat(cmd_line, replace_space(argv[i], ""));
		i++;
	}

	if (strlen(cmd_line) == 0) {
		fprintf(stderr, "No command line argument!\n");
		usage(argv[0]);
		exit(1);
	}

	if (strlen(pbsuser) == 0) {
		fprintf(stderr, "No pbsuser argument!\n");
		usage(argv[0]);
		exit(2);
	}

	if (strlen(jobid) == 0) {
		fprintf(stderr, "No jobid argument!\n");
		usage(argv[0]);
		exit(3);
	}

	if (pbs_loadconf(0) == 0) {
		fprintf(stderr, "Failed to read pbs.conf!\n");
		exit(4);
	}

	if (pbs_conf.pbs_mom_home) {
		if (pbs_conf.pbs_home_path != NULL)
			free(pbs_conf.pbs_home_path);
		pbs_conf.pbs_home_path = \
                        shorten_and_cleanup_path(pbs_conf.pbs_mom_home);
	}

	sprintf(path_jobs, "%s/mom_priv/jobs/", pbs_conf.pbs_home_path);


	jobid_read_cred(jobid, &usercred_buf, &usercred_len);

	if ((usercred_len == 0) || (usercred_buf == NULL)) {
		fprintf(stderr, "No password for user %s found.\n", pbsuser);
		exit(5);
	}

	if ((pwdp = \
     		logon_pw(pbsuser, usercred_buf, usercred_len, pbs_decrypt_pwd, 1,
		msg)) == NULL) {

		fprintf(stderr, "Failed to create user security token: %s\n", msg);
		ecode = 6;
		goto done;

	}
	si.cb = sizeof(si);
	si.lpDesktop = NULL;

	sprintf(actual_cmd_line, "cmd /c %s", cmd_line);
	if (pwdp->pw_userlogin == INVALID_HANDLE_VALUE) {
		if (!OpenProcessToken(GetCurrentProcess(), TOKEN_QUERY, &hToken)) {
			printf("OpenProcessToken failed. GetLastError returned: %d\n", GetLastError());
			return NULL;
		}
		CreateEnvironmentBlock(&user_env, hToken, FALSE);
	} else
	CreateEnvironmentBlock(&user_env, pwdp->pw_userlogin, FALSE);

	if (pwdp->pw_userlogin != INVALID_HANDLE_VALUE) {
		rc = CreateProcessAsUser(pwdp->pw_userlogin, NULL, actual_cmd_line,
			NULL, NULL, TRUE, flags, user_env, NULL, &si, &pi);

		if (!rc) {
			fprintf(stderr, "CreateProcessAsUser %s failed: error=%d\n",
				actual_cmd_line, GetLastError());
		}
	} else {
		rc = CreateProcess(NULL, actual_cmd_line,
			NULL, NULL, TRUE, flags, user_env, NULL, &si, &pi);
		if (!rc) {
			fprintf(stderr, "CreateProcess %s failed: error=%d\n",
				actual_cmd_line, GetLastError());
		}
	}

	if (!rc) {
		ecode = 7;
		goto done;
	}

	WaitForSingleObject(pi.hProcess, INFINITE);
	CloseHandle(pi.hProcess);
	CloseHandle(pi.hThread);

	ecode = 0;

	done:	if (usercred_buf) {
		(void)free(usercred_buf);
		usercred_buf = NULL;
		usercred_len = 0;
	}

	if (pwdp && (pwdp->pw_userlogin != INVALID_HANDLE_VALUE))
		CloseHandle(pwdp->pw_userlogin);

	if (user_env)
		DestroyEnvironmentBlock(user_env);

	exit(ecode);

}
