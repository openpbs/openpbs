/*
 * Copyright (C) 1994-2021 Altair Engineering, Inc.
 * For more information, contact Altair at www.altair.com.
 *
 * This file is part of both the OpenPBS software ("OpenPBS")
 * and the PBS Professional ("PBS Pro") software.
 *
 * Open Source License Information:
 *
 * OpenPBS is free software. You can redistribute it and/or modify it under
 * the terms of the GNU Affero General Public License as published by the
 * Free Software Foundation, either version 3 of the License, or (at your
 * option) any later version.
 *
 * OpenPBS is distributed in the hope that it will be useful, but WITHOUT
 * ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or
 * FITNESS FOR A PARTICULAR PURPOSE.  See the GNU Affero General Public
 * License for more details.
 *
 * You should have received a copy of the GNU Affero General Public License
 * along with this program.  If not, see <http://www.gnu.org/licenses/>.
 *
 * Commercial License Information:
 *
 * PBS Pro is commercially licensed software that shares a common core with
 * the OpenPBS software.  For a copy of the commercial license terms and
 * conditions, go to: (http://www.pbspro.com/agreement.html) or contact the
 * Altair Legal Department.
 *
 * Altair's dual-license business model allows companies, individuals, and
 * organizations to create proprietary derivative works of OpenPBS and
 * distribute them - whether embedded or bundled with other software -
 * under a commercial license agreement.
 *
 * Use of Altair's trademarks, including but not limited to "PBS™",
 * "OpenPBS®", "PBS Professional®", and "PBS Pro™" and Altair's logos is
 * subject to Altair's trademark licensing policies.
 */

#include	<sys/stat.h>
#include	<signal.h>
#include	<sys/utsname.h>
#include	<limits.h>
#include	<sys/resource.h>

#include	"pbs_ifl.h"
#include	"net_connect.h"
#include	"log.h"
#include	"job.h"
#include	"mom_func.h"
#include	"placementsets.h"
#include	"pbs_undolr.h"
#include	"tpp.h"

extern int do_debug_report;
extern int termin_child;
extern int exiting_tasks;
extern int next_sample_time;
extern char	*log_file;
extern char	*path_log;
extern int mom_run_state;
extern int vnode_additive;
extern int kill_jobs_on_exit;
extern vnl_t *vnlp;
extern char *msg_corelimit;
extern vnl_t *vnlp_from_hook;
extern char	*ret_string;

extern void debug_report(void);
extern void	scan_for_exiting(void);
extern int read_config(char *);
extern void cleanup(void);
extern void initialize(void);
extern void	mom_vnlp_report(vnl_t *vnl, char *header);

/**
 * @brief
 *	signal handler for SIGTERM and SIGINT
 *	TERM kills running jobs
 *	INT  leaves them running
 *
 * @param[in] sig - signal number
 *
 * @return	Void
 *
 */

void
stop_me(int sig)
{
	sprintf(log_buffer, "caught signal %d", sig);
	log_event(PBSEVENT_SYSTEM | PBSEVENT_FORCE, PBS_EVENTCLASS_SERVER,
		LOG_NOTICE, msg_daemonname, log_buffer);

	switch (sig) {
		case SIGPIPE:
		case SIGUSR1:
#ifdef	SIGINFO
		case SIGINFO:
#endif
			return;

		default:
			break;
	}

	mom_run_state = 0;
	if (sig == SIGTERM)
		kill_jobs_on_exit = 1;
}

/**
 * @brief
 *	The finish of MOM's main loop
 *	Actually the heart of the loop
 *
 * @param[in] waittime - wait time
 *
 * @return Void
 *
 */
void
finish_loop(time_t waittime)
{
#ifdef PBS_UNDOLR_ENABLED
	if (sigusr1_flag)
		undolr();
#endif
	if (do_debug_report)
		debug_report();
	if (termin_child) {
		scan_for_terminated();
		waittime = 1;	/* want faster time around to next loop */
	}
	if (exiting_tasks) {
		scan_for_exiting();
		waittime = 1;	/* want faster time around to next loop */
	}

	if (waittime > next_sample_time)
		waittime = next_sample_time;
	DBPRT(("%s: waittime %lu\n", __func__, (unsigned long) waittime));

	/* wait for a request to process */
	if (wait_request(waittime, NULL) != 0)
		log_err(-1, msg_daemonname, "wait_request failed");
}

/**
 * @brief
 *	returns access permission of a file
 *
 * @return int
 * @retval permission
 *
 */
int
get_permission(char *perm) {
	if (strcmp(perm, "write") == 0)
		return (S_IWGRP|S_IWOTH);
	return 0;
}

/**
 * @brief
 *	Verify whether PBS_INTERACTIVE process is running.
 *	As this is not useful for *nix platform, so returns HANDLER_SUCCESS.
 *
 * @return handler_ret_t
 * @retval Success
 *
 */

handler_ret_t
check_interactive_service() {
	return HANDLER_SUCCESS;
}

/**
 * @brief
 *	returns username
 *
 * @return string
 * @retval user name
 *
 */
char *
getuname(void)
{
	static char *name = NULL;
	struct utsname	n;

	if (name == NULL) {
		if (uname(&n) == -1)
			return NULL;
		sprintf(ret_string, "%s %s %s %s %s", n.sysname,
			n.nodename, n.release, n.version, n.machine);
		name = strdup(ret_string);
	}
	return name;
}

/**
 * @brief
 *	Function to catch HUP signal.
 *	Set call_hup = 1.
 * @param[in] sig - signal number
 *
 * @return Void
 *
 */
void
catch_hup(int sig)
{
	sprintf(log_buffer, "caught signal %d", sig);
	log_event(PBSEVENT_SYSTEM, 0,  LOG_INFO, "catch_hup", log_buffer);
	call_hup = HUP_REAL;
}

/**
 * @brief
 *	Do a restart of resmom.
 *	Read the last seen config file and
 *	Clean up and reinit the dependent code.
 *
 * @return Void
 *
 */
void
process_hup(void)
{
	/**
	 * When call_hup == HUP_REAL, the catch_hup function has been called.
	 * When call_hup == HUP_INIT, we couldn't start a job so the ALPS
	 * inventory needs to be refreshed.
	 * When real_hup is false, some actions don't need to be done.
	 */
	int	real_hup = (call_hup == HUP_REAL);
	int num_var_env;

	call_hup = HUP_CLEAR;

	if (real_hup) {
		log_event(PBSEVENT_SYSTEM, 0, LOG_INFO, __func__, "reset");
		log_close(1);
		log_open(log_file, path_log);

		if ((num_var_env = setup_env(pbs_conf.pbs_environment)) == -1) {
			mom_run_state = 0;
			return;
		}
	}

	/*
	 ** See if we need to get rid of the previous vnode state.
	 */
	if (!vnode_additive) {
		if (vnlp != NULL) {
			vnl_free(vnlp);
			vnlp = NULL;
		}
		if (vnlp_from_hook != NULL) {
			vnl_free(vnlp_from_hook);
			vnlp_from_hook = NULL;
		}
	}

	if (read_config(NULL) != 0) {
		cleanup();
		log_close(1);
		tpp_shutdown();
		exit(1);
	}

	cleanup();
	initialize();

#if	MOM_ALPS /* ALPS needs libjob support */
	/*
	 * This needs to be called after the config file is read.
	 */
	ck_acct_facility_present();
#endif	/* MOM_ALPS */

	if (!real_hup)		/* no need to go on */
		return;
}

/**
 * @brief
 *	signal handler for SIG_USR2
 *
 * @return Void
 *
 */

void
catch_USR2(int sig)
{
	do_debug_report = 1;
}

/**
 * @brief
 *	Cause useful information to be logged.  This function is called from
 *	MoM's main loop after catching a SIGUSR2.
 *
 * @return Void
 *
 */

void
debug_report(void)
{
extern void	mom_CPUs_report(void);

	mom_CPUs_report();
	mom_vnlp_report(vnlp, NULL);
	do_debug_report = 0;
}

/**
 * @brief
 *	Got an alarm call.
 *
 * @param[in] sig - signal number
 *
 * @return Void
 *
 */
void
toolong(int sig)
{
	log_event(PBSEVENT_SYSTEM, 0, LOG_NOTICE, __func__, "alarm call");
	DBPRT(("alarm call\n"))
}

/**
 * @brief
 *	Prints usage for prog
 *
 * @param[in] prog - char pointer which holds program name
 *
 * @return Void
 *
 */

void
usage(char *prog)
{
	const char *configusage = "%s -s insert scriptname inputfile\n"
			"%s -s [ remove | show ] scriptname\n"
			"%s -s list\n";
	fprintf(stderr,
		"Usage: %s [-C chkdirectory][-d dir][-c configfile][-r|-p][-R port][-M port][-L log][-a alarm][-n nice]\n", prog);
	fprintf(stderr, "or\n");
	fprintf(stderr, configusage, prog, prog, prog);
	fprintf(stderr, "%s --version\n", prog);
	exit(1);
}
