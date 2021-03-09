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

/**
 * @file    pbsTclInit.c
 *
 * @brief
 *		pbsTclInit - All the pbs specific code needed to make pbstclsh
 *		work is here.  The routine pbsTcl_Init() is to be called
 *		in place of Tcl_Init().
 *
 * Functions included are:
 * 	pbsTcl_Init()
 * 	main()
 */

#include	"pbs_version.h"
#include	"pbs_config.h"
#include	<stdlib.h>
#include	<string.h>
#include	<unistd.h>
#include	"tcl.h"
#include	"rm.h"
#include	"pbs_ifl.h"
#include	"pbs_internal.h"
#include	"log.h"
#include	"tpp.h"



#ifdef NAS /* localmod 099 */
extern	int	quiet;
#endif /* localmod 099 */

extern	void	add_cmds(Tcl_Interp *interp);

#define SHOW_NONE 0xff

/**
 * @brief
 * 		pbsTcl_Init	- Function to initialize Tcl interpreter based on the environment.
 *
 * @param[in,out]	interp	-	Interpreter for application.
 *
 * @return	int
 * @retval	TCL_OK	: everything looks good.
 * @retval	TCL_ERROR	: something got wrong!
 */
int
pbsTcl_Init(Tcl_Interp *interp)
{
	if (Tcl_Init(interp) == TCL_ERROR)
		return TCL_ERROR;
#if	TCLX
	if (Tclx_Init(interp) == TCL_ERROR)
		return TCL_ERROR;
#endif

	fullresp(0);
	add_cmds(interp);

	Tcl_SetVar(interp, "tcl_rcFileName", "~/.tclshrc", TCL_GLOBAL_ONLY);
	return TCL_OK;
}
/**
 * @brief
 * 		main - the entry point in pbsTclInit.c
 *
 * @param[in]	argc	-	argument count.
 * @param[in]	argv	-	argument variables.
 *
 * @return	int
 * @retval	0	: success
 */
int
main(int argc, char *argv[])
{
	char tbuf_env[256];
	int rc;
	struct tpp_config tpp_conf;
	fd_set selset;
	struct timeval tv;

	/*the real deal or just pbs_version and exit?*/

	PRINT_VERSION_AND_EXIT(argc, argv);
	if(set_msgdaemonname("pbs_tclsh")) {
		fprintf(stderr, "Out of memory\n");
		return 1;
	}
	set_logfile(stderr);

	/* load the pbs conf file */
	if (pbs_loadconf(0) == 0) {
		fprintf(stderr, "%s: Configuration error\n", argv[0]);
		return (1);
	}

	set_log_conf(pbs_conf.pbs_leaf_name, pbs_conf.pbs_mom_node_name,
			pbs_conf.locallog, pbs_conf.syslogfac,
			pbs_conf.syslogsvr, pbs_conf.pbs_log_highres_timestamp);

	if (!getenv("TCL_LIBRARY")) {
		if (pbs_conf.pbs_exec_path) {
			sprintf(tbuf_env, "%s/tcltk/lib/tcl%s", pbs_conf.pbs_exec_path, TCL_VERSION);
			setenv("TCL_LIBRARY", tbuf_env, 1);
		}
	}

	if (!pbs_conf.pbs_leaf_name) {
		char my_hostname[PBS_MAXHOSTNAME+1];
		if (gethostname(my_hostname, (sizeof(my_hostname) - 1)) < 0) {
			fprintf(stderr, "Failed to get hostname\n");
			return -1;
		}
		pbs_conf.pbs_leaf_name = get_all_ips(my_hostname, log_buffer, sizeof(log_buffer) - 1);
		if (!pbs_conf.pbs_leaf_name) {
			fprintf(stderr, "%s\n", log_buffer);
			fprintf(stderr, "%s\n", "Unable to determine TPP node name");
			return -1;
		}
	}

	/* call tpp_init */
	rc = set_tpp_config(&pbs_conf, &tpp_conf, pbs_conf.pbs_leaf_name, -1, pbs_conf.pbs_leaf_routers);
	if (rc == -1) {
		fprintf(stderr, "Error setting TPP config\n");
		return -1;
	}

	if ((tpp_fd = tpp_init(&tpp_conf)) == -1) {
		fprintf(stderr, "tpp_init failed\n");
		return -1;
	}

	/*
	 * Wait for net to get restored, ie, app to connect to routers
	 */
	FD_ZERO(&selset);
	FD_SET(tpp_fd, &selset);
	tv.tv_sec = 5;
	tv.tv_usec = 0;
	select(FD_SETSIZE, &selset, NULL, NULL, &tv);

	tpp_poll(); /* to clear off the read notification */

	Tcl_Main(argc, argv, pbsTcl_Init);
	return 0;
}
