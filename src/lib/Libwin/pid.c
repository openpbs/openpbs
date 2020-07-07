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

#include <stdio.h>
#include <errno.h>
#include "log.h"
#include <windows.h>
#include <tlhelp32.h>
#include "win.h"

static HANDLE	*pid_handles = NULL;
static int	pids_cnt = 0;
static int	pids_nextidx = 0;
/**
 * @file	pid.c
 */
/**
 * @brief
 * 	initializes the pid_handles table.
 *
 * @return	int
 * @retval	1 	on success
 * @retval	0 	on error.
 *
 */
int
initpids(void)
{
	int	i;

	pid_handles = (HANDLE *)calloc(MAXIMUM_WAIT_OBJECTS, sizeof(HANDLE));
	if (pid_handles == NULL)
		return (0);

	for (i=0; i < MAXIMUM_WAIT_OBJECTS; i++) {
		pid_handles[i] = INVALID_HANDLE_VALUE;
	}

	pids_cnt = MAXIMUM_WAIT_OBJECTS;
	return (1);
}

/**
 * @brief
 *	Aaddpid: adds the process handle to pid_handles table.
 *
 * @param[in] pid - process id
 *
 * @return	int
 * @retval	1 	if successful;
 * @retval	0 	otherwise
 *
 */
int
addpid(HANDLE pid)
{
	int	i;
	HANDLE	*hpids;

	for (i=0; i < pids_cnt; i++) {
		if (pid_handles[i] == INVALID_HANDLE_VALUE) {
			pid_handles[i] = pid;
			return 1;
		}
	}
	/* array filled up. Let's extend... */
	hpids = (HANDLE *)realloc(pid_handles, (pids_cnt*2)*sizeof(HANDLE));

	if (hpids == NULL) {
		log_errf(errno, __func__, "realloc failed for pid_handles, size (%u)", (pids_cnt*2)*sizeof(HANDLE));
		return 0;
	}

	pid_handles = hpids;
	pids_cnt *= 2;
	pid_handles[i] = pid;

	for (i++; i < pids_cnt; i++) {
		pid_handles[i] = INVALID_HANDLE_VALUE;
	}
	return (1);
}

/**
 * @brief
 *	print the process ids.
 */
void
printpids(void)
{
	int	i;

	for (i=0; i < pids_cnt; i++) {
		sprintf(log_buffer, "printpids: pid_handles[%d] = %d", i, pid_handles[i]);
		log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", log_buffer);
	}

	sprintf(log_buffer, "printpids: pids_cnt=%d pids_nextidx=%d", pids_cnt, pids_nextidx);
	log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", log_buffer);
}

/**
 * @brief
 * 	waitpid: if pid is -1, then it waits on all pids tracked by the calling process. Otherwise,
 *	it waits on the particular 'pid'. 'pid' if set must be tracked by the calling process.
 *	0 if WNOHANG and no child pid handle terminated.
 *
 * @param[in] pid - process id
 * @param[in] statp - status of process
 * @param[in] opt - option
 *
 * @par	NOTE: If no more child processes, then this returns -1 with errno set to ECHILD
 * 	NOTE: If waiting on child process returned WAIT_FAILED, then *statp is set -1
 * 	NOTE: This closes the pid to complete termination.
 *
 * @return	HANDLE
 * @retval	pid handle of the child that exited	success
 * @retval	-1					error
 * @retval	0 					if WNOHANG and no child pid handle terminated.
 *
 */
HANDLE
waitpid(HANDLE pid, int *statp, int opt)
{
	DWORD	ret;
	HANDLE	rval;
	int	timeout;
	int	i;
	int	ref_idx;
	int	pass;

	if (opt == WNOHANG)
		timeout = 1000;		/* default 1 second timeout */
	else
		timeout = INFINITE;


	rval = (HANDLE)-1;	/* if no children */
	errno = ECHILD;
	*statp = 0;

	if (pids_nextidx == pids_cnt) {
		pids_nextidx = 0;
	}
	ref_idx = pids_nextidx;

	pass = 1;
	for (i=pids_nextidx; i < pids_cnt; i++) {

		if (pass != 1 && i == ref_idx) { /* 2nd pass and we've cycled through! */
			break;
		}

		if( pid_handles[i] != INVALID_HANDLE_VALUE && \
							(pid == (HANDLE)-1 || pid_handles[i] == pid) ) {
			errno = 0;
			ret = WaitForSingleObject(pid_handles[i], timeout);

			if (ret == WAIT_TIMEOUT)
				rval = 0;
			else if (ret == WAIT_FAILED) { /* notion of an abnormal exit */
				log_errf(-1, __func__, "WaitForSingleObject(%d, %d) failed i[%d/%d]", pid_handles[i], timeout, i, pids_cnt);
				rval = (HANDLE)-1;
				*statp = -1;
			} else {
				sprintf(log_buffer,"found pid_handles[%d]=%d to have exited", i, pid_handles[i]);
				log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", log_buffer);
				if (!GetExitCodeProcess(pid_handles[i], (DWORD *)statp))
					log_errf(-1, __func__, "GetExitCodeProcess failed for handle[%d], i[%d/%d]", pid_handles[i], i, pids_cnt);
				sprintf(log_buffer,"status=%d", *statp);
				log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | PBSEVENT_FORCE| PBSEVENT_DEBUG, PBS_EVENTCLASS_FILE, LOG_NOTICE, "", log_buffer);
				rval = pid_handles[i];
			}
			/* The following is iffy - should we close the handle or do it outside ? */
			if (ret != WAIT_TIMEOUT) {
				CloseHandle(pid_handles[i]);
				pid_handles[i] = INVALID_HANDLE_VALUE;
			}

			pids_nextidx = i+1;
			break;
		}

		if ((i+1) == pids_cnt) {
			i = -1;
			pass++;
		}
	}
	return (rval);
}

/**
 * @brief
 *	terminate a process using specified pid
 *
 * @param[in] pid - process id
 * @param[in] sig - signal number
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	error
 *
 */
int
kill(HANDLE pid, UINT sig)
{
	int	ret;

	ret = processtree_op_by_handle(pid, TERMINATE, sig);

	if (ret == -1) {
		return (-1);
	}
	return (0);
}

/**
 * @brief
 *		Perform the given operation <op> on process tree by using given parent process handle <hProcess> and close that handle.
 *
 * @param[in]
 *		hProcess - parent process handle on which <op> will performed
 *		op		 - operation to perform, one of SUSPEND, RESUME or TERMINATE
 *		exitcode - exit code for processes, this is used only if <op> = TERMINATE, otherwise 0
 *
 * @return
 *		int
 *
 * @retval
 *		>= 0 - No. of processes that were operated on
 *		-1   - Invalid parameter or Error
 */
int
processtree_op_by_handle(HANDLE hProcess, enum operation op, int exitcode)
{
	DWORD processId = 0;
	DWORD rc = 0;

	if (hProcess == INVALID_HANDLE_VALUE || hProcess == NULL)
		return -1;

	if (!GetExitCodeProcess(hProcess, &rc)) {
		log_errf(-1, __func__, "GetExitCodeProcess(%d,) failed", hProcess);
		return -1;
	}

	if (rc != STILL_ACTIVE)
		return 0;

	if ((processId = GetProcessId(hProcess)) <= 0) {
		errno = EINVAL; /* using EINVAL as GetProcessId() does not set SetLastError */
		log_errf(errno, __func__, "GetProcessId(%d,) failed", hProcess);
		return -1;
	}

	return (processtree_op_by_id(processId, op, exitcode));
}


/**
 * @brief
 *		Perform the given operation <op> on process tree by using given parent process id <process_ID>
 *
 * @param[in]
 *		process_ID - parent process id on which <op> will performed
 *		op		 - operation to perform, one of SUSPEND, RESUME or TERMINATE
 *		exitcode - exit code for processes, this is used only if <op> = TERMINATE, otherwise 0
 *
 * @return
 *		int
 *
 * @retval
 *		>= 0 - No. of processes that were operated on
 *		-1   - Invalid parameter or Error
 *
 */
int
processtree_op_by_id(DWORD processId, enum operation op, int exitcode)
{
	HANDLE hProcessSnap = INVALID_HANDLE_VALUE;
	HANDLE hThreadSnap = INVALID_HANDLE_VALUE;
	HANDLE hThread = INVALID_HANDLE_VALUE;
	HANDLE hProcess = INVALID_HANDLE_VALUE;
	THREADENTRY32 te32 = { sizeof(te32) };
	PROCESSENTRY32 pe32 = { sizeof(pe32) };
	int process_count = 0;
	int ret = -1;

	if (processId <= 0)
		return -1;

	if (op >= UNKNOWN)
		return -1;

	hProcessSnap = CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, processId);
	if (hProcessSnap == INVALID_HANDLE_VALUE) {
		log_errf(-1, __func__, "CreateToolhelp32Snapshot(SNAPPROCESS, %ld) failed", processId);
		return -1;
	}

	if (!Process32First(hProcessSnap, &pe32)) {
		log_errf(-1, __func__, "Process32First(%d) failed", hProcessSnap);
		CloseHandle(hProcessSnap);
		return -1;
	}

	do {
		if (processId == pe32.th32ParentProcessID) {
			ret = processtree_op_by_id(pe32.th32ProcessID, op, exitcode);
			if (ret != -1) {
				process_count += ret;
			} else {
				CloseHandle(hProcessSnap);
				return -1;
			}
		}
	} while (Process32Next(hProcessSnap, &pe32));

	CloseHandle(hProcessSnap);

	/*
	 * if op == TERMINATE then terminate process at process level instead
	 * of thread level because TerminateThread call is not safe as per MSDN
	 *
	 * if op = SUSPEND or RESUME then suspend or resume process at thread level
	 * by using SuspendThread or ResumeThread
	 */
	if (op == TERMINATE) {
		hProcess = OpenProcess(PROCESS_ALL_ACCESS, TRUE, processId);
		if (!hProcess) {
			log_errf(-1, __func__, "OpenProcess(PROCESS_ALL_ACCESS, TRUE, %ld) failed", processId);
			return -1;
		}
		/*
		 * OpenProcess() may return a handle to next lower process Id
		 * if given process id doesn't exist. It will be disastorous
		 * if we kill this arbitrary process, thus always make sure that the handle returned
		 * belongs to intended process id by calling GetProcessId() on returned handle.
		 */
		if (GetProcessId(hProcess) == processId) {
			ret = TerminateProcess(hProcess, exitcode);
			if (ret) {
				CloseHandle(hProcess);
				return (++process_count);
			} else {
				log_errf(-1, __func__, "TerminateProcess(%d, %d) failed", hProcess, exitcode);
				CloseHandle(hProcess);
				return -1;
			}
		} else {
			errno = EINVAL; /* using EINVAL as GetProcessId() does not set SetLastError */
			log_errf(errno, __func__, "GetProcessId(%d) != %ld", hProcess, processId);
			return -1;
		}
	}

	hThreadSnap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, processId);
	if (hThreadSnap == INVALID_HANDLE_VALUE) {
		log_errf(-1, __func__, "CreateToolhelp32Snapshot(SNAPTHREAD, %ld) failed", processId);
		return -1;
	}

	if (!Thread32First(hThreadSnap, &te32)) {
		log_errf(-1, __func__, "Thread32First(%d) failed", hThreadSnap);
		CloseHandle(hThreadSnap);
		return -1;
	}

	do {
		if (te32.th32OwnerProcessID == processId) {
			hThread = OpenThread(THREAD_SUSPEND_RESUME, TRUE, te32.th32ThreadID);
			if (!hThread) {
				log_errf(-1, __func__, "OpenThread(THREAD_SUSPEND_RESUME, TRUE, %ld) failed", te32.th32ThreadID);
				CloseHandle(hThreadSnap);
				return -1;
			} else {
				if (op == SUSPEND) { /* Suspend Thread */
					if (SuspendThread(hThread) == -1) {
						log_errf(-1, __func__, "SuspendThread(%d) failed", hThread);
						CloseHandle(hThread);
						CloseHandle(hThreadSnap);
						return -1;
					}
				} else if (op == RESUME) { /* Resume Thread */
					if (ResumeThread(hThread) == -1) {
						log_errf(-1, __func__, "ResumeThread(%d) failed", hThread);
						CloseHandle(hThread);
						CloseHandle(hThreadSnap);
						return -1;
					}
				}
				CloseHandle(hThread);
			}
		}
	} while (Thread32Next(hThreadSnap, &te32));

	CloseHandle(hThreadSnap);

	process_count++;
	return process_count;
}