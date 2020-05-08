/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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
 * @file    pbs_open_demux.c
 *
 * @brief
 * Run a task and send it's output to pbs_demux
 */
#include <windows.h>
#include <stdio.h>
#include <stdlib.h>
#include <process.h>
#include "win.h"
#include "log.h"
#include "win_remote_shell.h"
#include "pbs_ifl.h"


int
main(int argc, char *argv[])
{
	char            cmd_str[PBS_CMDLINE_LENGTH] = {'\0'};
	char            demux_hostname[PBS_MAXHOSTNAME + 1] = {'\0'};
	char*           momjobid = NULL;
	char            logbuff[LOG_BUF_SIZE] = { '\0' };
	int             i = 0;
	char            pipeName[PIPENAME_MAX_LENGTH] = {'\0'};
	HANDLE          hPipe_cmdshell = INVALID_HANDLE_VALUE;
	char            pipename_append[PIPENAME_MAX_LENGTH] = {'\0'};
	STARTUPINFO     si;
	DWORD           nBytesWrote = 0;
	char            this_host[PBS_MAXHOSTNAME + 1] =  {'\0'};
	char            cmd_shell[MAX_PATH + 1] = {'\0'};       /* path to cmd shell */
	char            cmdline[PBS_CMDLINE_LENGTH]={'\0'};
	DWORD           exit_code = 0;
	DWORD	        err_code = 0;

	if (argc < 4)
		exit(1);

	momjobid = argv[1];
	(void)strncpy_s(demux_hostname, _countof(demux_hostname), argv[2], _TRUNCATE);
	(void)strncpy_s(cmd_str, _countof(cmd_str), argv[3], _TRUNCATE);
	for (i=4; argv[i]; i++) {
		(void)strncat_s(cmd_str, _countof(cmd_str), " ", _TRUNCATE);
		(void)strncat_s(cmd_str, _countof(cmd_str), argv[i], _TRUNCATE);
	}

	ZeroMemory(&si, sizeof(si));
	si.cb = sizeof(si);

	if (winsock_init()) {
		return 1;
	}

	/* connect to remote host's IPC$ */
	if (!connect_remote_resource(demux_hostname, "IPC$", TRUE)) {
		log_err(-1, __func__, "Connect to remote host's IPC failed");
		winsock_cleanup();
		exit(1);
	}
	snprintf(pipeName, _countof(pipeName) - 1, "\\\\%s\\pipe\\%s%s", demux_hostname, momjobid, "_pbs_demux_");
	/* connect to job's pbs_demux at remote host. */
	if (INVALID_HANDLE_VALUE ==
		(hPipe_cmdshell = do_WaitNamedPipe(pipeName, NMPWAIT_WAIT_FOREVER, GENERIC_WRITE))) {
		log_err(-1, __func__, "Failed to obtain a valid handle to the named pipe");
		winsock_cleanup();
		exit(1);
	}

	if (gethostname(this_host, (sizeof(this_host) - 1))) {
		log_err(-1, __func__, "Failed to get hostname");
		winsock_cleanup();
		exit(1);
	}
	/* write hostname to this pipe */
	if (!WriteFile(hPipe_cmdshell, this_host, strlen(this_host), &nBytesWrote, NULL) || nBytesWrote == 0) {
		DWORD dwErr = GetLastError();
		if (dwErr == ERROR_NO_DATA) {
			sprintf(logbuff, "Write to pipe failed with error %lu", dwErr);
			log_err(-1, __func__, logbuff);
			winsock_cleanup();
			exit(1);
		}
	}
	disconnect_close_pipe(hPipe_cmdshell);
	/* wait for a client to connect */
	/*
	 * create named pipes for standard output, error, input
	 * qsub will sit on these pipes
	 */
	(void)strncpy_s(pipename_append, _countof(pipename_append), momjobid, _TRUNCATE);
	(void)strncat_s(pipename_append, _countof(pipename_append), "mom_demux", _TRUNCATE);
	(void)strncat_s(pipename_append, _countof(pipename_append), this_host, _TRUNCATE);
	if ((err_code = create_std_pipes(&si, pipename_append, 0)) != 0) {
		sprintf(logbuff, "Failed to create pipe with error %lu", err_code);
		log_err(-1, __func__, logbuff);
		winsock_cleanup();
		exit(1);
	}
	if ((err_code = connectstdpipes(&si, 0)) != 0) {
		/* close the standard out/err handles before returning */
		sprintf(logbuff, "Failed to connect to std pipe with error %lu", err_code);
		log_err(-1, __func__, logbuff);
		close_valid_handle(si.hStdOutput);
		close_valid_handle(si.hStdError);
		winsock_cleanup();
		exit(1);
	}
	if (0 != get_cmd_shell(cmd_shell, _countof(cmd_shell)))
		(void)strncpy_s(cmd_shell, _countof(cmd_shell) - 1, "cmd.exe", _TRUNCATE);
	(void)strncat_s(cmdline, _countof(cmdline) - 1, cmd_shell, _TRUNCATE);
	(void)strncat_s(cmdline, _countof(cmdline) - 1, " /c", _TRUNCATE);
	(void)strncat_s(cmdline, _countof(cmdline) - 1, cmd_str, _TRUNCATE);
	/* run the command, flush the file buffers */
	err_code = run_command_si_blocking(&si, cmdline, &exit_code, 0, SW_HIDE, NULL);
	if (err_code == 0) {
		if (si.hStdOutput != INVALID_HANDLE_VALUE)
			FlushFileBuffers(si.hStdOutput);
		if (si.hStdError != INVALID_HANDLE_VALUE)
			FlushFileBuffers(si.hStdError);
	} else {
		sprintf(logbuff, "Failed to run command %s with error %lu", cmdline, err_code);
		log_err(-1, __func__, logbuff);
	}
	/* disconnect all named pipes and close handles */
	disconnect_close_pipe(si.hStdOutput);
	disconnect_close_pipe(si.hStdError);
	winsock_cleanup();
	exit(0);
}
