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
#include <pbs_config.h>
#include <stdio.h>
#include <sys/types.h>
#include <errno.h>
#include <process.h>
#include <stdlib.h>
#include "log.h"
#include <ctype.h>
#include <string.h>
/**
 * @file	alarm.c
 */
static HANDLE g_hEvent = NULL;
static HANDLE g_hMutex = NULL;
static unsigned int initial_time;
static unsigned int delay_time = 0;

struct alarm_param {
	HANDLE	hthread;
	unsigned int timeout_secs;
	void 	(*func)(void);
};

unsigned _stdcall
alarm_thread(void *pv)
{

	struct alarm_param *a = (struct alarm_param *)pv;
	HANDLE	hthread = a->hthread;
	unsigned int timeout = a->timeout_secs;
	void (*func)(void) = a->func;

	(void)free(a);

	/* child waiting for an event, and clearing the event
	 object must be MUTEXED, to synchronize with parent
	 */
	if (WaitForSingleObject(g_hMutex,
		timeout*1000) == WAIT_OBJECT_0) {
		DWORD dw;

		dw = WaitForSingleObject(g_hEvent, timeout*1000);

		CloseHandle(g_hEvent);
		g_hEvent = NULL;
		ReleaseMutex(g_hMutex);

		if (dw == WAIT_TIMEOUT) {
			delay_time   = 0; /* clear this alarm */
			if (func)
				func();
		}

	}

	return (0);
}

/**
 * @brief
 *	win_alarm: calls func after the specified # of timeout_secs has expired.
 *	Set timeout_secs to 0 to reset alarm.
 *
 * @param[in] timeout_secs - time slice
 *
 * @return	unsigned int
 * @retval	number of seconds left in a prior alarm		success
 * @retval	0						error
 *
 */

unsigned int
win_alarm(unsigned int timeout_secs, void (*func)(void))
{
	DWORD	dwTID;
	HANDLE	h;
	HANDLE	hThreadParent;

	struct alarm_param *a;
	unsigned int rtn_time = 0;
	unsigned int now_time;

	/* create a mutex */
	if (g_hMutex == NULL) {
		g_hMutex = CreateMutex(0, FALSE, 0);
		if (g_hMutex == NULL)
			return (0);
	}

	now_time = time(0);
	if (delay_time != 0) {
		rtn_time = delay_time - (now_time - initial_time);
	}
	delay_time = timeout_secs;
	initial_time = now_time;

	/* alarm(0) */
	if (timeout_secs == 0) {
		if (g_hEvent != NULL)
			SetEvent(g_hEvent);  /* interrupt child */
		return (rtn_time);
	}


	/* alarm(timeout) */
	if (g_hEvent != NULL) { /* found an event handle to child! */

		SetEvent(g_hEvent);  /* interrupt child */
		/* wait until g_hEvent has been updated by child */
		if (WaitForSingleObject(g_hMutex,
			timeout_secs*1000) == WAIT_TIMEOUT) {
			/* error - the child thread still exists */
			return (0);
		}
		ReleaseMutex(g_hMutex);

	}

	if (g_hEvent == NULL) { /* no event handle */
		g_hEvent = CreateEvent(0, FALSE, FALSE, 0);
		if (g_hEvent == NULL)
			return (0);
	}

	a = (struct alarm_param *)malloc(sizeof(struct alarm_param));
	if (a == NULL)
		return (0);

	DuplicateHandle(
		GetCurrentProcess(),
		GetCurrentThread(),
		GetCurrentProcess(),
		&hThreadParent,
		0,
		FALSE,
		DUPLICATE_SAME_ACCESS);

	a->hthread = hThreadParent;
	a->timeout_secs = timeout_secs;
	a->func = func;

	h = (HANDLE) _beginthreadex(0, 0,  alarm_thread, a, 0, &dwTID);

	CloseHandle(h);
	return (rtn_time);
}
