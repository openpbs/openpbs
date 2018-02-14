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
 * @file	pbs_dcelogin.c
 * @brief
 * The purpose of this program is to establish a DCE login context for a user,
 * keep that context refreshed, and exec whatever program was passed in via
 * the command line arguments array (argv[]).
 * @details
 * Command line argument argv[1] is to be the user's name and argv[2] should be
 * the name of a program that this program is to exec.  All remaining args,
 * if any, will become the argument vector for the program being exec'd.
 *
 * This program needs the user's password to establish a DCE login context.
 * It is to get this by reading a pipe.  The pipe is established by the caller,
 * and loaded with the password.  The caller must create the environment
 * variable PBS_PWPIPE and set its value to that of the descriptor for the read
 * end of the pipe.
 *
 * Once the login context is successfully setup, the program forks and execv's
 * whatever program was specified for the second  argument, passing it the
 * remaining arguments.  So if the second argument happens to be the job shell,
 * it will execv that shell.
 * The parent process will wait for the child to terminate and, while waiting,
 * periodically refresh the login context, which was setup to be shared by all
 * child processes.
 *
 * If the environment variable PBS_PWPIPE doesn't exist, its value is a bogus
 * file descriptor, or the password information appears bogus, the program
 * issues the exit system call with value 254.
 *
 * If a DCE login context cannot be acquired for the user, no fork followed
 * by an execv occurs.  Instead, this program will just execv the specified
 * program straight away.  The reason for doing things this way rather than
 * exiting with a nonzero exit status is that a login context may not be
 * required for the specific work that should execute.  If it doesn't, there is
 * no reason to insist apriori that a context exist.  Should a context in fact
 * be needed, certain operations will fail and that, presumably, would be noted
 * and termination would occur.
 * The down side of this approach might be that a lot of computation gets done
 * before reaching a point where a DCE login context is needed. This would
 * result in wasting compuational resources.
 */


#include <stdio.h>
#include <string.h>
#include <fcntl.h>
#include <unistd.h>
#include <stdlib.h>
#include <errno.h>
#include <time.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <sys/time.h>
#include <dce/sec_login.h>
#include <dce/dce_error.h>
#include <dce/passwd.h>

#define	SHORT_TIME		600	/* 10 minutes */

/* Global Data - make it local in final version */

sec_login_handle_t	lcon;
dce_error_string_t	err_string;
sec_passwd_rec_t	pwdrec;
sec_passwd_str_t	tmp_passwd;
char			*username;
int			inq_st;
int			handler_refreshed_context;
int			have_login_context;


/**
 * @brief
 *	fill_pwdrec -  fills in the fields of  sec_passwd_rec_t structure.  This
 *	structure is passed in the sec_login_validate_identity call.
 *
 * @param[in] pwd - password
 * @param[out] p_pwdrec - structure to hold password
 *
 * @return Void
 *
 */
void
fill_pwdrec(char *pwd, sec_passwd_rec_t *p_pwdrec)
{
	static sec_passwd_str_t        t_passwd;

	strncpy((char *)&t_passwd[0], pwd, sec_passwd_str_max_len);
	p_pwdrec->version_number = sec_passwd_c_version_none;
	p_pwdrec->pepper = NULL;
	p_pwdrec->key.key_type = sec_passwd_plain;
	p_pwdrec->key.tagged_union.plain = &(t_passwd[0]);
}


/**
 * @brief
 *	compute_refresh_time - We have a refreshed login context, use it in
 * 	computing the next refresh time point.
 *
 * 	This function is the merge (and modification) of the two original functions,
 * 	compute_expire_delta() and compute_alarm_time().
 *
 * @param[in] lcon - structure handle for sec_login
 *
 * @return -  time_t
 * @retval    0             if remaining TGT lifetime < 10minutes or,
 *                          if computed refresh time exceeds expiration time
 * @retval    (now + computed refresh_delta)    otherwise.
 *
 */
time_t
compute_refresh_time(sec_login_handle_t lcon)
{
	error_status_t	st;
	signed32	expire_time = -1;
	time_t		expire_delta, refresh_delta, refresh_time;
	time_t		now = time(NULL);

	/* get lifetime of the context's tgt */

	expire_delta = -1;
	(void)sec_login_get_expiration(lcon, &expire_time, &st);
	if (st != error_status_ok) {
		dce_error_inq_text(st, err_string, &inq_st);
		fprintf(stderr,
			"failed getting login context expiration time - %s\n",
			err_string);
	} else if (expire_time <= 0) {
		fprintf(stderr,
			"Got a bad context expiration time for context\n");
	}
	else	/* compute expire delta */
		expire_delta = expire_time - now;

	/* life of tgt < 10 minutes, don't bother doing refreshes */
	if (expire_delta <= SHORT_TIME)
		return 0;

	refresh_delta = expire_delta * 80 / 100;
	if (refresh_delta < SHORT_TIME)
		refresh_delta = SHORT_TIME;

	refresh_time = refresh_delta + now;
	if (refresh_time > expire_time)
		return 0;

	return refresh_time;
}

/**
 * @brief
 *      renews the login context after certain time
 *
 * @param[in] lcon - structure handle for sec_login
 *
 * @return - time_t
 * @retval   retry_time(now + SHORT_TIME)  -  refresh failure
 *					      validation failure
 * @retval   refresh_time                     Success
 *
 */
time_t
do_refresh(sec_login_handle_t lcon)
{
	error_status_t		st;
	time_t			now = time(NULL);
	time_t			retry_time = now + SHORT_TIME;
	boolean32		reset_passwd;
	sec_login_auth_src_t	auth_src;

	if (!sec_login_refresh_identity(lcon, &st)) {

		/* fail refresh */

		if (st == error_status_ok) {
			fprintf(stderr,
				"sec_login_refresh_identity fail - reason??\n");
		} else {
			dce_error_inq_text(st, err_string, &inq_st);
			fprintf(stderr, "identity refresh fail - %s\n",
				err_string);
		}
		return retry_time;

	} else {

		/* refresh successful, try to validate */

		fill_pwdrec((char*)&tmp_passwd[0], &pwdrec);
		if (!sec_login_validate_identity(lcon, &pwdrec,
			&reset_passwd, &auth_src, &st)) {

			/* fail validate */

			if (st == error_status_ok) {
				fprintf(stderr,
					"sec_login_validate_identity fail - reason??\n");
			} else {
				dce_error_inq_text(st, err_string, &inq_st);
				fprintf(stderr, "validate refresh fail - %s\n",
					err_string);
			}

			return retry_time;
		} else {	/* refreshed and validated */

			/* verify login_context is from trusted security server     */
			/* needed for error_status_ok from sec_login_get_expiration */

			if (!sec_login_certify_identity(lcon, &st)) {
				dce_error_inq_text(st, err_string, &inq_st);
				fprintf(stderr,
					"failed certification of login_context for %s -  %s\n",
					username, err_string);
			}
		}
	}
	return (compute_refresh_time(lcon));
}

/**
 * @brief
 *	Removes the dce login context in case of fork fail
 *  	or child finishes its task.
 *
 * @return - Error code
 * @retval   -1  Failure
 * @retval   0   Success
 *
 */
int
remove_context()
{
	error_status_t		st;

	if (have_login_context) {
		sec_login_purge_context(&lcon, &st);
		if (st != error_status_ok) {
			dce_error_inq_text(st, err_string, &inq_st);
			fprintf(stderr,
				"Error purging DCE login context for %s - cache not destroyed\n",
				username, err_string);

			return (-1);
		}
		have_login_context = 0;
	}
	return (0);
}

/**
 * @brief
 *	establishes the dce login context by validating the security credentials
 *	username and password.
 *
 * @param[in] username - username for  validation
 *
 * @return - Error code
 * @retval   253 -  sec_login_setup_identity was not successful
 *	     254 -  the validate call did not return success
 * @retval   0      Success
 *
 */
int
establish_login_context(char *username)
{
	error_status_t		st;
	sec_login_auth_src_t	auth_src;
	boolean32		reset_passwd;

	if (sec_login_setup_identity((unsigned_char_p_t)username,
		sec_login_no_flags, &lcon, &st)) {

		/* now validate the login context information */

		fill_pwdrec((char*)&tmp_passwd[0], &pwdrec);
		if (sec_login_validate_identity(lcon, &pwdrec,
			&reset_passwd, &auth_src, &st)) {

			/* verify login_context is from trusted security server */

			if (!sec_login_certify_identity(lcon, &st)) {
				dce_error_inq_text(st, err_string, &inq_st);
				fprintf(stderr,
					"Didn't certify login_context for %s -  %s\n",
					username, err_string);
			}

			/* notify user if password valid period expired */

			if (reset_passwd) {
				fprintf(stderr, "Password must be changed for %s\n",
					username);
			}

			/* authentication frm netwrk security server or local host? */

			if (auth_src == sec_login_auth_src_local) {
				fprintf(stderr,
					"Credential source for %s is local registry\n",
					username);
			}

			if (auth_src == sec_login_auth_src_overridden) {
				fprintf(stderr,
					"Credential source for %s is overridden\n",
					username);
			}

			/* finally, set this context as the current context */
			/* DCE cache files created upon success on this step*/

			sec_login_set_context(lcon, &st);
			if (st != error_status_ok) {
				dce_error_inq_text(st, err_string, &inq_st);
				fprintf(stderr, "Couldn't set context for %s - %s\n",
					username, err_string);
			}
			/* end of sequece (validate, certify, set context) */

		} else { /* the validate call did not return success */
			if (st != error_status_ok) {
				dce_error_inq_text(st, err_string, &inq_st);
				fprintf(stderr,
					"Unable to validate security context for %s - %s\n",
					username, err_string);
			} else {
				fprintf(stderr,
					"sec_login_validate_identity failed - reason??\n");
			}
			return (254);
		}

	} else { /* sec_login_setup_identity was not successful */

		if (st != error_status_ok) {
			dce_error_inq_text(st, err_string, &inq_st);
			fprintf(stderr,
				"Unable to setup login entry for %s because %s\n",
				username, err_string);
		} else {
			fprintf(stderr,
				"sec_login_setup_identity failed - reason??\n");
		}
		return (253);

	}
	return (0);
}


int
main(int argc, char *argv[])
{
	int			i;
	int			rc;
	pid_t			pid, retpid;
	int			status;
	char			*program;
	char			*pdesc;
	char			*pc;
	int			pw_pipe;
	int			expire_delta;
	int			refresh_time;


	/* call me redundant, but it's satisfying to see this */
	handler_refreshed_context = 0;
	have_login_context = 0;
	pid = 0;

	/*test for real deal or just version and exit*/

	execution_mode(argc, argv);

	if (argc < 3) {
		fprintf(stderr, "usage: %s user program [arg(s)]\n", argv[0]);
		fprintf(stderr, "       %s --version\n", argv[0]);
		exit(254);
	}

	/* In the event we inherited creds from the parent, ignore them. */
	if (getenv("KRB5CCNAME") != NULL) {
		unsetenv("KRB5CCNAME");
	}

	/* read password from descriptor, close descriptor */

	if ((pdesc = getenv("PBS_PWPIPE")) == NULL) {
		fprintf(stderr, "PBS_PWPIPE not in the environment\n");
		exit  (254);
	}
	pw_pipe = atoi(pdesc);
	if (errno != 0) {
		fprintf(stderr, "Value of PBS_PWPIPE is bad\n");
		exit  (254);
	}
	for (;;) {
		i = read(pw_pipe, &tmp_passwd[0], sec_passwd_str_max_len);
		if (i == -1 && errno == EINTR)
			continue;
		break;
	}
	close(pw_pipe);

	username = argv[1];
	program = strdup(argv[2]);

	/* when execv-ing a shell interpreter, cause it to be a login shell */
	if (argc == 3) {
		if (pc = strrchr(argv[2], (int)'/')) {
			*pc = '-';
			argv[2] = pc;
		}
	}

	/* Attempt to establish login context for user */
	if (rc=establish_login_context(username)) {
		have_login_context = 0;
	} else {
		have_login_context = 1;
		rc=252;
	}

	/*
	 * If we have a login context, fork the child that will become
	 * the job. The parent sticks around to refresh the context
	 * periodically.
	 *
	 * If we don't have a login context, exec the job over ourself.
	 */
	if (have_login_context) {
		if ((pid = fork()) == -1) {
			perror("fork");
			(void)remove_context();
			exit(254);
		}
	}

	if (pid == 0) { /* exec the program */
		if (execv(program, &argv[2]) == -1) {
			/* execv system call failed */
			perror("execv");
			fprintf(stderr, "pbs_dcelogin: execv system call failed\n");
			exit(rc);
		}
		/* child should never get here */
		exit(99);
	}

	/*
	 * go into a loop which will every so often refresh the
	 * the DCE login context while it waits for the child to terminate
	 */

	refresh_time = compute_refresh_time(lcon);
	for (;;) {
		if ((retpid = waitpid(pid, &status, WNOHANG)) == -1) {
			perror("pbs_dcelogin: waitpid");
			break;
		}
		else if (retpid > 0)		/* child finished */
			break;

		/* see if it is time to refresh */
		if (0 < refresh_time && refresh_time <= time(NULL))
			refresh_time = do_refresh(lcon);
		sleep(5);
	}

	/* after removing any created DCE login context and credential cache
	 * files, pass back the exit status of the job
	 */

	(void)remove_context();

	if (retpid == pid) {
		if (WIFEXITED(status)) {
			exit(WEXITSTATUS(status));
		} else if (WIFSIGNALED(status)) {
			exit(WTERMSIG(status));
		} else if (WIFSTOPPED(status)) {
			exit(WSTOPSIG(status));
		} else {
			exit(253);
		}
	} else {
		exit(254);
	}
}
