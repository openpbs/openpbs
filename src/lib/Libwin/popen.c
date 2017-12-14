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
#include <stdio.h>
#include <io.h>
#include <windows.h>
#include <direct.h>
#include "win.h"
#include "log.h"
#include "libutil.h"
#include "win_remote_shell.h"
/**
 * @file	popen.c
 */
/**
 * @brief       Opens a process and initiates pipe streams to and from the process.
 *
 * @param[in]   cmd             : The command to be executed
 * @param[in]   type            : "r" for reading, "w" for writing
 * @param[out]  pio             : pipe i/o handles
 * @param[in]   proc_info       : process control struct
 *                              if NULL, does not support process tree termination and inherits parent process handles.
 *
 * @return      int
 * @retval      nonzero for success
 * @retval      0 for failure, sets errno
 */
int
win_popen(char	*cmd, const char *type, struct pio_handles *pio, struct proc_ctrl *proc_info)
{
	SECURITY_ATTRIBUTES     sa;
	STARTUPINFO             si = { sizeof(si) };
	BOOL                    fsuccess = FALSE;
	HANDLE                  hReadPipe_out = INVALID_HANDLE_VALUE;       /* pipes to handle reading process' output and error */
	HANDLE                  hReadPipe_err = INVALID_HANDLE_VALUE;
	HANDLE                  hWritePipe_out = INVALID_HANDLE_VALUE;
	HANDLE                  hWritePipe_err = INVALID_HANDLE_VALUE;
	HANDLE                  hReadPipe_in = INVALID_HANDLE_VALUE;	/* pipes to handle writing to process' stdin */
	HANDLE                  hWritePipe_in = INVALID_HANDLE_VALUE;
	HANDLE                  hRead_dummy = INVALID_HANDLE_VALUE;/* dummpy pipe read handle */
	HANDLE                  hWrite_dummy = INVALID_HANDLE_VALUE;/* dummpy pipe write handle */
	char	                cmd_line[PBS_CMDLINE_LENGTH + 1] = {'\0'};
	char                    cmd_shell[MAX_PATH + 1] = {'\0'};       /* path to cmd shell */
	char	                current_dir[MAX_PATH + 1] = {'\0'};
	char	                *temp_dir = NULL;
	int	                changed_dir = 0;

	sa.nLength = sizeof(sa);
	sa.lpSecurityDescriptor = NULL;
	sa.bInheritHandle = TRUE;

	pio->hWritePipe_out = INVALID_HANDLE_VALUE;
	pio->hReadPipe_out = INVALID_HANDLE_VALUE;
	pio->hWritePipe_err = INVALID_HANDLE_VALUE;
	pio->hReadPipe_err = INVALID_HANDLE_VALUE;
	pio->hWritePipe_in = INVALID_HANDLE_VALUE;
	pio->hReadPipe_in = INVALID_HANDLE_VALUE;
	pio->pi.hProcess = INVALID_HANDLE_VALUE;
	pio->pi.hThread = INVALID_HANDLE_VALUE;
	pio->hJob = INVALID_HANDLE_VALUE;

	/* pipe to read stdout of the process */
	if (CreatePipe(&hReadPipe_out, &hWritePipe_out, &sa, 0) == 0) {
		fprintf(stderr, "\npopen: pipe creation failed!\n");
		errno = GetLastError();
		return (0);
	}
	/* pipe to read stderr of the process */
	if (CreatePipe(&hReadPipe_err, &hWritePipe_err, &sa, 0) == 0) {
		fprintf(stderr, "\npopen: pipe creation failed!\n");
		errno = GetLastError();
		return (0);
	}

	si.dwFlags = STARTF_USESTDHANDLES;
	if (strcmp(type, "r") == 0) {
		/* 
		 * A blocking process will not block on input unless it has a valid input handle.
		 * This results in many issues like a blocking command gets blank as input
		 * and in case of many commands such inputs are constantly rejected and 
		 * the commands keep running infinitely waiting for correct input
		 * resulting in high CPU consupmtion.
		 * Create a dummpy pipe and use it's handle as stdin of child process. 
		 * This is required to block on process that need user input (wrongly)
		 * even when invoked for read only.
		 */
		if (CreatePipe(&hRead_dummy, &hWrite_dummy, &sa, 0) == 0) {
			fprintf(stderr, "\npopen: pipe creation failed!\n");
			errno = GetLastError();
			return (0);
		}
		si.hStdInput = hRead_dummy;
		si.hStdOutput = hWritePipe_out;
		si.hStdError = hWritePipe_err;
	} else if (strcmp(type, "w") == 0) {
		if (CreatePipe(&hReadPipe_in, &hWritePipe_in, &sa, 0) == 0) {
			fprintf(stderr, "\npopen: pipe creation failed!\n");
			errno = GetLastError();
			return (0);
		}
		si.hStdInput = hReadPipe_in;
		si.hStdOutput = hWritePipe_out;
		si.hStdError = hWritePipe_err;
		pio->hReadPipe_in = hReadPipe_in;
		pio->hWritePipe_in = hWritePipe_in;
	} else {
		return (0);
	}
	/*
	 * if no process control is requested OR if the process needs to be invoked using command shell,
	 * get a command shell
	 */
	if ((proc_info == NULL) || (proc_info->buse_cmd == TRUE)) {
		/* if we fail to get cmd shell(unlikely), use "cmd.exe" as shell */
		if (0 != get_cmd_shell(cmd_shell, _countof(cmd_shell)))
			(void)snprintf(cmd_shell, _countof(cmd_shell) - 1, "cmd.exe");
		(void)snprintf(cmd_line, _countof(cmd_line) - 1, "%s /c %s", cmd_shell, cmd);
	}
	else {
		(void)snprintf(cmd_line, _countof(cmd_line) - 1, "%s", cmd);
	}

	/* cmd.exe doesn't like UNC path for a current directory. */
	/* We can be cd-ed to it like in a server failover setup. */
	/* In such a case, need to temporarily cd to a local path, */
	/* before executing cmd.exe */

	current_dir[0] = '\0';
	_getcwd(current_dir, MAX_PATH+1);
	if ((strstr(current_dir, "\\\\") != NULL) || (proc_info != NULL && proc_info->is_current_path_network)) {	/* \\host\share or Z:\*/
		temp_dir = get_win_rootdir();
		if (chdir(temp_dir?temp_dir:"C:\\") == 0)
			changed_dir = 1;
	}
	/*
	 * create an un-named job object and assign this process to the job object
	 * if the process tree needs to be terminated on win_pclose().
	 */
	if (proc_info) {
		if (proc_info->flags)
			fsuccess = CreateProcess(NULL, cmd_line, &sa, &sa, proc_info->bInheritHandle,
				proc_info->flags, NULL, NULL, &si, &pio->pi);
		else
			fsuccess = CreateProcess(NULL, cmd_line, &sa, &sa, proc_info->bInheritHandle,
				CREATE_NO_WINDOW, NULL, NULL, &si, &pio->pi);

		close_valid_handle(&(hRead_dummy));
		close_valid_handle(&(hWrite_dummy));

		if (proc_info->need_ptree_termination && fsuccess) {
			pio->hJob = CreateJobObject(NULL, NULL);
			if ((pio->hJob == NULL) || (pio->hJob == INVALID_HANDLE_VALUE)) {
				fprintf(stderr, "\npopen: CreateJobObject() failed!\n");
				errno = GetLastError();
				return 0;
			}
			if (!AssignProcessToJobObject(pio->hJob, pio->pi.hProcess)) {
				fprintf(stderr, "\npopen: AssignProcessToJobObject() failed!\n");
				errno = GetLastError();
				return 0;
			}
		}
	}
	else {
		fsuccess = CreateProcess(NULL, cmd_line, &sa, &sa, TRUE,
			CREATE_NO_WINDOW, NULL, NULL, &si, &pio->pi);
	}
	close_valid_handle(&(hRead_dummy));
	close_valid_handle(&(hWrite_dummy));

	/* restore current working directory */
	if (changed_dir)
		chdir(current_dir);

	if (fsuccess) {
		if ((strcmp(type, "r") == 0) &&
			((proc_info == NULL) || !(proc_info->bnowait)))
			WaitForSingleObject(pio->pi.hProcess, INFINITE);
		/* if no process control requested or process is not opened suspended */
		if ((proc_info == NULL) || !(proc_info->bnowait))
			close_valid_handle(&(hWritePipe_out));	/* needed to un-hang empty ReadFile() */
		pio->hReadPipe_out = hReadPipe_out;
		pio->hReadPipe_err = hReadPipe_err;
		return (1);
	} else {
		fprintf(stderr, "\npopen: CreateProcess() failed!\n");
		errno = GetLastError();
		return (0);
	}

}
/**
 * @brief       Reads a process' output/error and send it to the standard output/error.
 *
 * @param[in]   pio             : pipe i/o handles
 *
 * @return      int
 * @retval      0 for success
 * @retval      errno for wait failure
 * @retval      -1 for invalid parameters
 */
int
win_pread2(pio_handles *pio)
{
	int return_code = 0;
	if (pio == NULL)
		return -1;
	/* loop for reading the process output */
	while (1) {
		if (1 == handle_stdoe_pipe(pio->hReadPipe_out, std_output))
			break;
		if (1 == handle_stdoe_pipe(pio->hReadPipe_err, std_error))
			break;
		/* find out if the process is signalled */
		return_code = WaitForSingleObject(pio->pi.hProcess, 0);
		if (return_code == WAIT_TIMEOUT)
			continue;
		else if (return_code == WAIT_OBJECT_0) {/* process exited */
			/* read any pending data before exiting the loop */
			(void)handle_stdoe_pipe(pio->hReadPipe_out, std_output);
			(void)handle_stdoe_pipe(pio->hReadPipe_err, std_error);
			break;
		}
		else {/* wait failed */
			errno = GetLastError();
			return errno;
		}
	}
	return 0;
}
/**
 * @brief 
 *	win_pread() returns RAW bytes.
 *
 * @par	Note:
 *	So any one who is making call to win_pread() should take care of 
 * 	Null terminating the buffer if required. 
 *
 * @param[in] pio - pipe i/o handle
 * @param[out] output - read content
 * @param[in] len - size of content
 *
 * @return	int
 * @retval	size of read content	success
 */

int
win_pread(pio_handles *pio, char *output, int len)
{
	DWORD	nRead;
	int		ret;
	ret = ReadFile(pio->hReadPipe_out, output, len, &nRead, NULL);
	return (nRead);
}

/**
 * @brief
 *      win_pwrite() writes 
 *
 * @par Note:
 *      So any one who is making call to win_pwrite() should take care of
 *      Null terminating the buffer if required.
 *
 * @param[out] pio - written to
 * @param[in] output - content to be writen
 * @param[in] len - size of content
 *
 * @return      int
 * @retval      size of written content    success
 */
int
win_pwrite(pio_handles *pio, char *output, int len)
{
	DWORD	nWritten;
	WriteFile(pio->hWritePipe_in, output, len, &nWritten, NULL);
	return (nWritten);
}
/**
 * @brief 
 *	Closes all handles (i.e. pipe handles and process thread handle),
 * 	opened by win_popen(), except the process handle which can be monitored later.
 *
 * @param[in] pio : pipe i/o handles
 *
 * @return void
 */
void
win_pclose2(pio_handles *pio)
{
	if (pio) {
		if (pio->hWritePipe_out)        close_valid_handle(&(pio->hWritePipe_out));
		if (pio->hReadPipe_out)	        close_valid_handle(&(pio->hReadPipe_out));
		if (pio->pi.hThread)            close_valid_handle(&(pio->pi.hThread));
		if (pio->hWritePipe_in)	        close_valid_handle(&(pio->hWritePipe_in));
		if (pio->hReadPipe_in)	        close_valid_handle(&(pio->hReadPipe_in));
	}
}
/**
 * @brief 
 *	Closes all handles (i.e. pipe handles, process handle, thread handle, job handle),
 *  	opened by win_popen(), terminate the job object if not NULL, else terminate the process.
 *
 * @param[in] pio : pipe i/o handles
 *
 * @return void
 */
void
win_pclose(pio_handles *pio)
{
	DWORD rc = 0;
	if (pio) {
		win_pclose2(pio);
		if ((pio->pi.hProcess != NULL) && (pio->pi.hProcess != INVALID_HANDLE_VALUE)) {
			/* Terminate the jobs object or the process only if it is not already exited */
			if ((GetExitCodeProcess(pio->pi.hProcess, &rc)) && (rc == STILL_ACTIVE)) {
				if (pio->hJob != INVALID_HANDLE_VALUE && pio->hJob != NULL)
					TerminateJobObject(pio->hJob, 0);
				else
					TerminateProcess(pio->pi.hProcess, 0);
			}
		}
		close_valid_handle(&(pio->pi.hProcess));
		close_valid_handle(&(pio->hJob));
	}
}

