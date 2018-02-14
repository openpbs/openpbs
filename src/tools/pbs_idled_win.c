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
 *		pbs_idled_win.c
 *
 * @brief
 *		pbs_idled is a background process which measures the userﾒs
 *		activity/inactivity by accessing the last access time of keyboard/mouse
 *		and informs the MOM about them through "idled_touch" file in PBS_HOME/spool/
 *		directory.
 *		start/stop of pbs_idled process is controlled by either PBS_INTERACTIVE service
 *		or logon/logoff script.
 *
 * Functions included are:
 * 	update_utime()
 * 	stop_prev_pbs_idle()
 * 	usage_idle()
 * 	main()
 *
 */

#include <pbs_config.h> /* the master config file */
#include "pbs_internal.h"
#include "pbs_version.h"
#include "win.h"
#include <tlhelp32.h>
#include <share.h>


#define idlepoll_buffsize 512
#define PROG_NAME "pbs_idled"

/**
 * This global variable is used to store full path of idled_touch file
 * which is used while updating time stamp to mom
 */
char idle_touchFile[MAX_PATH];

/**
 * This global variable is used to store full path of idle_poll_file file
 * which is used while reading idle poll time written by mom into idle_poll_file
 */
char idle_pollFile[MAX_PATH];

/**
 * @brief
 *		detect users activity/inactivity
 *		according to user's activity/inactivity update the time stamp of idle_touch file
 *		in PBS_HOME/spool/ directory
 *
 * @return
 *		Nothing (void)
 *
 * @par MT-safe: No
 */
void
update_utime()
{
	LASTINPUTINFO key_mouse_press = { sizeof(LASTINPUTINFO), 0 };
	static DWORD press_time_prev = 0; /* previous keyboard/mouse access time */
	FILE *fd = NULL;
	int idle_poll = 1;
	char idlepoll_buf[idlepoll_buffsize];

	for (;;) {
		/* open the idle_pollFile in shared mode
		 * so that if more that one pbs_idled is running
		 * (ofcource as diff. user) can also open and read file
		 */
		fd = _fsopen(idle_pollFile, "r", SH_DENYNO);
		if (fd != NULL) {
			/* idle_poll_file exist */
			/* Read idle_poll time from idle_poll_file */
			fgets(idlepoll_buf, idlepoll_buffsize, fd);
			fclose(fd);
			idle_poll = strtol(idlepoll_buf, NULL, 10);
			/* is idle_poll time > 0?, if Yes then continue, otherwise assign default idle_poll time */
			if (idle_poll <= 0)
				idle_poll = 1;
		}
		sleep(idle_poll);
		GetLastInputInfo(&key_mouse_press);
		if (key_mouse_press.dwTime > press_time_prev) { /* is change? */
			/* Change in last access time, update time stamp of idle_touch file */
			_utime(idle_touchFile, NULL);
			/* reset prev access time to current values */
			press_time_prev = key_mouse_press.dwTime;
		}
	}
}

/**
 * @brief
 *		Stop the running background pbs_idled process.
 *
 * @return
 *		Nothing (void)
 *
 */
void
stop_prev_pbs_idle()
{
	char *id = "stop_prev_pbs_idle";
	PROCESSENTRY32 proc;
	HANDLE hProcessSnap = INVALID_HANDLE_VALUE;
	char *process_owner = NULL;
	char *current_fqdn = NULL;

	current_fqdn = getlogin_full();
	if (!strcmp(current_fqdn, "")) {
		return;
	}

	proc.dwSize = sizeof(proc);

	/* Get Snapshot of all running processes */
	hProcessSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0);
	if (hProcessSnap == INVALID_HANDLE_VALUE)
		return;

	/* Find first process in snapshot */
	if (!Process32First(hProcessSnap, &proc)) {
		CloseHandle(hProcessSnap);
		return;
	}

	do {
		/* Find runnnig pbs_idled process other than current process */
		if ((!strncmp(proc.szExeFile, PROG_NAME, 9))
			&& (proc.th32ProcessID != GetCurrentProcessId())) {
			process_owner = get_processowner(proc.th32ProcessID, NULL, NULL, 0, NULL, 0);
			if ((process_owner != NULL) && (!_stricmp(current_fqdn, process_owner))) {
				/* found running pbs_idled process try to terminate them */
				processtree_op_by_id(proc.th32ProcessID, TERMINATE, 0);
			} else {
				continue;
			}
		}
	} while (Process32Next(hProcessSnap, &proc));

	if (hProcessSnap)
		CloseHandle(hProcessSnap);
}

/**
 * @brief
 *		Display usage of pbs_idled process.
 *
 * @param[in]	prog	-	Name of process (argv[0])
 *
 * @return	Nothing (void)
 *
 */
void
usage_idle()
{
	fprintf(stderr,	"\nUSAGE:\n");
	fprintf(stderr, "\t%s [ start | stop ]\n", PROG_NAME);
	fprintf(stderr, "\t%s --version\n", PROG_NAME);
	exit(1);
}

/**
 * @Brief
 *      This is main function of pbs_idled process.
 *
 * @return	int
 * @retval	0	: On Success
 *
 */
int
main(int argc, char *argv[])
{
	int start = 0;
	int stop = 0;
	HWND hWindow;

	/* The real deal or output pbs_version and exit? */
	execution_mode(argc, argv);

	if (argc == 2 && _stricmp(argv[1], "start") == 0) {
		start = 1;
	} else if (argc == 2 && _stricmp(argv[1], "stop") == 0) {
		stop = 1;
	} else {
		usage_idle(PROG_NAME);
	}

	pbs_loadconf(0);
	snprintf(idle_touchFile, MAX_PATH, "%s/%s", pbs_conf.pbs_home_path, "spool/idle_touch");
	snprintf(idle_pollFile, MAX_PATH, "%s/%s", pbs_conf.pbs_home_path, "spool/idle_poll_time");

	if (start) {
		/* Hide main window */
		if ((hWindow =  GetConsoleWindow()) != NULL) {
			ShowWindow(hWindow, SW_HIDE);
			UpdateWindow(hWindow);
			/* here, we do not want to close window but we are just hiding window
			 * so no need to close hWindow handle
			 */
		}

		/* First stop any running pbs_idled process as current user */
		/* Because only one instant of pbs_idled can run as current user */
		stop_prev_pbs_idle();

		/* Goto continues loop */
		update_utime();
	} else if (stop) {
		/* Stop the running pbs_idled process */
		stop_prev_pbs_idle();
	}
	return 0;
}
