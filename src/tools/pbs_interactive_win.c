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
 *		pbs_interactive_win.c
 *
 * @brief
 *		pbs_interactive process is used to register and unregister PBS_INTERACTIVE service.
 *		PBS_INTERACTIVE service is used to start/stop pbs_idled process in current
 *		active user's session.
 *		Also PBS_INTERACTIVE service, monitor the change in current active user's
 *		session and according to them PBS_INTERACTIVE service will start/stop pbs_idled process.
 *		start/stop of PBS_INTERACTIVE service is controlled PBS_MOM service.
 *		PBS_INTERACTIVE service can not be started manually it will only start
 *		whenever PBS_MOM will start it. However MOM will start PBS_INTERACTIVE service
 *		if $kbd_idle parameter is specified in MOM config and PBS_INTERACTIVE service
 *		is registered in Service Control Manager.
 *
 * Functions included are:
 * 	run_idled_command()
 * 	pbsinteractiveMainThread()
 * 	pbsinteractiveHandler()
 * 	pbsinteractiveMain()
 * 	main()
 *
 */

#include <pbs_config.h> /* the master config file */
#include "pbs_internal.h"
#include "pbs_version.h"
#include "win.h"

/**
 * This global variable is used to store start command string for pbs_idled daemon
 * which is used to control pbs_idle.exe (i.e. start)
 */
char idled_start_command[MAX_PATH];

/**
 * This global variable is used to store stop command string for pbs_idled daemon
 * which is used to control pbs_idle.exe (i.e. stop)
 */
char idled_stop_command[MAX_PATH];

/**
 * This global variable is used to indicate that we are shutting down
 * which is used to break out of the infinite loop inside the service
 */
int kill_on_exit = 0;

/**
 * This global variable is used to store service status handle
 * which is used while communication with Service Control Manager
 */
SERVICE_STATUS_HANDLE g_ssHandle = 0;

/**
 * This global variable is used to store current status of service
 * which is used while communication with Service Control Manager
 */
DWORD g_dwCurrentState = SERVICE_START_PENDING;

/**
 * This global variable is used to store handle of main thread
 * which is used to control main thread of service (i.e. start/stop/check)
 */
HANDLE pbsinteractiveThreadH = INVALID_HANDLE_VALUE;

/**
 * This global variable is used to store prev active session id
 * which is to control pbs_idle.exe (i.e. start/stop/check) while session changes
 */
static DWORD prev_activesessionid;

/**
 * This global variable is used to store prev active username
 * which is to control pbs_idle.exe (i.e. start/stop/check) while session changes
 */
static char *prev_username = NULL;

/**
 * This global variable is used to store name of pbs interative service
 * which is used to control the pbs interactive service (i.e. start/stop/check)
 */
const TCHAR *const g_PbsInteractiveName = __TEXT("PBS_INTERACTIVE");

/**
 * @brief
 *		run the given command in the active user's session by getting active user's token
 *
 * @param[in]	command	-	command to run in active user's session
 *
 * @return	int
 *
 * @retval	0	: On Success
 * @retval	1	: On Error
 *
 */
int
run_idled_command(char *command)
{
	PROCESS_INFORMATION pi;
	STARTUPINFO si;
	HANDLE hUserToken = INVALID_HANDLE_VALUE;

	if (command == NULL) {
		return 1;
	}

	ZeroMemory(&si, sizeof(si));
	si.cb= sizeof(si);
	si.lpDesktop = "winsta0\\default";
	ZeroMemory(&pi, sizeof(pi));

	/* Get current active user session's id. Return if no active session id */
	prev_activesessionid = get_activesessionid(1, NULL);
	if (prev_activesessionid == -1) {
		/* No active session so no need to start new process */
		return 0;
	}

	if (prev_username)
		free(prev_username);
	prev_username = get_usernamefromsessionid(prev_activesessionid, NULL);
	if (prev_username == NULL) {
		return 0;
	}

	/* Get current active user's token */
	hUserToken = get_activeusertoken(prev_activesessionid);
	if (hUserToken == INVALID_HANDLE_VALUE) {
		return 1;
	}

	/* run the given command in active user's session using active user's token (hUserToken)*/
	if (!CreateProcessAsUser(hUserToken, NULL, command, NULL, NULL, FALSE, CREATE_NO_WINDOW, NULL, NULL, &si, &pi)) {
		CloseHandle(hUserToken);
		return 1;
	}

	CloseHandle(hUserToken);
	return 0;
}

/**
 * @brief
 *		PBS_INTERACTIVE service's main thread function.
 *
 * @param[in]	pv	-	pointer to argument structure
 *
 * @return	DWORD
 * @retval	0	: On Success
 * @retval	1	: On Error
 *
 */
DWORD WINAPI
pbsinteractiveMainThread(void *pv)
{
	DWORD new_activesessionid = 0;
	SERVICE_STATUS SvcSts;
	struct arg_param *p = (struct arg_param *)pv;
	char *ExeFile_path = NULL;
	char *new_username = NULL;

	/* Initialize service status structure */
	ZeroMemory(&SvcSts, sizeof(SvcSts));
	SvcSts.dwServiceType = SERVICE_WIN32_OWN_PROCESS|SERVICE_INTERACTIVE_PROCESS;
	SvcSts.dwCheckPoint = 0;
	SvcSts.dwControlsAccepted = SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN;
	SvcSts.dwWaitHint = 3000;

	/* Check for argument */
	if ((p) && (p->argc == 2)) {
		/*Argument found, copy given full path of pbs_idled binary to ExeFile_path variable */
		if ((ExeFile_path = _strdup(p->argv[1])) == NULL) {
			g_dwCurrentState = SERVICE_STOPPED;
			SvcSts.dwCurrentState = g_dwCurrentState;
			SvcSts.dwWin32ExitCode = ERROR_NOT_ENOUGH_MEMORY;
			if (g_ssHandle != 0) {
				SetServiceStatus(g_ssHandle, &SvcSts);
			}
			return 1;
		}
	} else {
		/* Argument not found, stop PBS_INTERACTIVE service */
		g_dwCurrentState = SERVICE_STOPPED;
		SvcSts.dwCurrentState = g_dwCurrentState;
		SvcSts.dwWin32ExitCode = ERROR_INVALID_DATA;
		if (g_ssHandle != 0) {
			SetServiceStatus(g_ssHandle, &SvcSts);
		}
		return 1;
	}

	/* Create command to start and stop pbs_idled process */
	snprintf(idled_start_command, MAX_PATH, "%s %s", ExeFile_path, "start");
	snprintf(idled_stop_command, MAX_PATH, "%s %s", ExeFile_path, "stop");
	free(ExeFile_path);

	if (run_idled_command(idled_start_command)) { /* start pbs_idled process */
		/* pbs_idled can not start, stop PBS_INTERACTIVE service */
		g_dwCurrentState = SERVICE_STOPPED;
		SvcSts.dwCurrentState = g_dwCurrentState;
		SvcSts.dwWin32ExitCode = ERROR_PROCESS_ABORTED;
		if (g_ssHandle != 0) {
			SetServiceStatus(g_ssHandle, &SvcSts);
		}
		return 1;
	}

	/* pbs_idled process successfully started, change status of PBS_INTERACTIVE service to RUNNING */
	g_dwCurrentState = SERVICE_RUNNING;
	SvcSts.dwCurrentState = g_dwCurrentState;
	if (g_ssHandle != 0) {
		SetServiceStatus(g_ssHandle, &SvcSts);
	}

	while (!kill_on_exit) {
		/* sleep for 1 ms to decrease load on CPU */
		Sleep(1);

		/* Get current active user's session id */
		new_activesessionid = get_activesessionid(1, NULL);
		if (new_activesessionid == -1) {
			continue;
		}

		/* get current active username */
		if (new_username)
			free(new_username);
		new_username = get_usernamefromsessionid(new_activesessionid, NULL);
		if (new_username == NULL) {
			continue;
		}

		/* Check whether change in current active user's session id */
		if ((prev_activesessionid != new_activesessionid) || (_stricmp(prev_username, new_username))) {
			/* Change in current active session */
			/* start pbs_idled process into new (current) active user's session */
			if (run_idled_command(idled_start_command)) {
				/* failed to start pbs_idle process, stop service */
				g_dwCurrentState = SERVICE_STOPPED;
				SvcSts.dwCurrentState = g_dwCurrentState;
				SvcSts.dwWin32ExitCode = ERROR_PROCESS_ABORTED;
				if (g_ssHandle != 0) {
					SetServiceStatus(g_ssHandle, &SvcSts);
				}
				return 1;
			}
		}
	}
	return 0;
}

/**
 * @brief
 *		PBS_INTERACTIVE service's handler function.
 *
 * @param[in]	dwControl	-	control signal from SCM
 *
 * @return	Nothing. (void)
 *
 */
void WINAPI
pbsinteractiveHandler(DWORD dwControl)
{
	SERVICE_STATUS SvcSts;

	/* Initialize service status structure */
	ZeroMemory(&SvcSts, sizeof(SvcSts));
	SvcSts.dwServiceType        = SERVICE_WIN32_OWN_PROCESS|SERVICE_INTERACTIVE_PROCESS;
	SvcSts.dwCurrentState       = g_dwCurrentState;
	SvcSts.dwControlsAccepted   = SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN;

	switch (dwControl) {
		case SERVICE_CONTROL_STOP:
		case SERVICE_CONTROL_SHUTDOWN:
			/* stop PBS_INTERACTIVE service */
			g_dwCurrentState    = SERVICE_STOP_PENDING;
			SvcSts.dwCurrentState   = g_dwCurrentState;
			SvcSts.dwCheckPoint     = 1;
			SvcSts.dwWaitHint       = 1000;
			if (g_ssHandle != 0) {
				SetServiceStatus(g_ssHandle, &SvcSts);
			}

			/* stop running pbs_idled process */
			(void)run_idled_command(idled_stop_command);

			kill_on_exit = 1;
			CloseHandle(pbsinteractiveThreadH);
			break;

		default:
			if (g_ssHandle != 0) {
				SetServiceStatus(g_ssHandle, &SvcSts);
			}
			break;
	}
}

/**
 * @brief
 *		PBS_INTERACTIVE service's main function.
 *
 * @param[in]	dwArgc	-	number of agrument
 * @param[in]	rgszArgv	-	pointer to argument
 *
 * @return
 *		Nothing. (void)
 *
 */
void WINAPI
pbsinteractiveMain(DWORD dwArgc, LPTSTR *rgszArgv)
{
	DWORD dwTID;
	DWORD dwWait;
	DWORD i;
	SERVICE_STATUS SvcSts;
	struct arg_param *pap;

	/* Register service control handler for PBS_INTERACTIVE service*/
	g_ssHandle = RegisterServiceCtrlHandler(g_PbsInteractiveName, pbsinteractiveHandler);
	if (g_ssHandle == 0) {
		ErrorMessage("RegisterServiceCtrlHandler");
	}

	/* Check for argument */
	if (dwArgc > 1) {
		/* Argumet found, create argument structure to pass given argument into main thread of PBS_INTERACTIVE service */
		pap = create_arg_param();
		if (pap == NULL)
			ErrorMessage("create_arg_param");

		pap->argc = dwArgc;
		for (i=0; i < dwArgc; i++) {
			if ((pap->argv[i] = _strdup(rgszArgv[i])) == NULL) {
				free_arg_param(pap);
				ErrorMessage("strdup");
			}

		}
	} else {
		/* Argument not found, pass NULL argument instead of argument structure into main thread of PBS_INTERACTIVE service */
		pap = NULL;
	}

	/* Create and start execution of main thread of PBS_INTERACTIVE service */
	pbsinteractiveThreadH = (HANDLE)_beginthreadex(0, 0, pbsinteractiveMainThread, pap, 0, &dwTID);
	if (pbsinteractiveThreadH == 0) {
		free_arg_param(pap);
		ErrorMessage("CreateThread");
	}

	/* Wait to finish main thread of PBS_INTERACTIVE service for infinite time */
	dwWait = WaitForSingleObject(pbsinteractiveThreadH, INFINITE);
	if (dwWait != WAIT_OBJECT_0) {
		free_arg_param(pap);
		ErrorMessage("WaitForSingleObject");
	}

	/* Execution of main thread of PBS_INTERACTIVE service is finished, stop PBS_INTERACTIVE service */
	free_arg_param(pap);

	ZeroMemory(&SvcSts, sizeof(SvcSts));
	SvcSts.dwServiceType        = SERVICE_WIN32_OWN_PROCESS|SERVICE_INTERACTIVE_PROCESS;
	SvcSts.dwCurrentState       = SERVICE_STOPPED;
	SvcSts.dwControlsAccepted   = SERVICE_ACCEPT_STOP | SERVICE_ACCEPT_SHUTDOWN;

	if (g_ssHandle != 0) {
		SetServiceStatus(g_ssHandle, &SvcSts);
	}
}

/**
 * @Brief
 *      This is main function of pbs_interactive process.
 *
 * @return	int
 *
 * @retval	0	: On Success
 *
 */
int
main(int argc, char *argv[])
{
	int reg = 0;
	int unreg = 0;
	SC_HANDLE SvcHandle;
	SC_HANDLE SvcManager;
	char ModuleName[MAX_PATH];

	/* The real deal or output pbs_version and exit? */
	execution_mode(argc, argv);

	if (argc > 1) {
		if (strcmp(argv[1], "-R") == 0) {
			reg = 1;
		} else if (strcmp(argv[1], "-U") == 0) {
			unreg = 1;
		} else {
			fprintf(stderr,	"\nUSAGE:\n");
			fprintf(stderr, "\t%s [ -R | -U ]\n", argv[0]);
			fprintf(stderr,	"\t%s -R -> To Register PBS_INTERACTIVE Service\n", argv[0]);
			fprintf(stderr,	"\t%s -U -> To Unregister PBS_INTERACTIVE Service\n", argv[0]);
			return 1;
		}
	}

	if (reg || unreg) { /* register or unregister service */
		SvcManager = OpenSCManager(0, 0, SC_MANAGER_ALL_ACCESS);
		if (SvcManager == 0) {
			ErrorMessage("OpenSCManager");
		}

		if (reg) { /* register service */
			GetModuleFileName(0, ModuleName, sizeof(ModuleName)/sizeof(*ModuleName));
			printf("Installing %s service \n", g_PbsInteractiveName);
			SvcHandle = CreateService(SvcManager,
				g_PbsInteractiveName,
				g_PbsInteractiveName,
				SERVICE_ALL_ACCESS,
				SERVICE_WIN32_OWN_PROCESS|SERVICE_INTERACTIVE_PROCESS,
				SERVICE_DEMAND_START,
				SERVICE_ERROR_NORMAL,
				ModuleName,
				0, 0, 0,
				NULL, NULL);
			if (SvcHandle) {
				printf("Service %s installed successfully \n", g_PbsInteractiveName);
			} else {
				if (SvcManager)
					CloseServiceHandle(SvcManager);
				ErrorMessage("CreateService");
			}

			if (SvcHandle) {
				CloseServiceHandle(SvcHandle);
			}
		} else if (unreg) { /* unregister service */
			printf("Uninstalling %s service \n", g_PbsInteractiveName);
			SvcHandle = OpenService(SvcManager, g_PbsInteractiveName, DELETE);
			if (SvcHandle) {
				if (DeleteService(SvcHandle)) {
					printf("Service %s uninstalled successfully \n", g_PbsInteractiveName);
					if (SvcHandle)
						CloseServiceHandle(SvcHandle);
				} else {
					if (SvcManager)
						CloseServiceHandle(SvcManager);
					if (SvcHandle)
						CloseServiceHandle(SvcManager);
					ErrorMessage("DeleteService");
				}
			} else {
				if (SvcManager)
					CloseServiceHandle(SvcManager);
				ErrorMessage("OpenSevice");
			}
		}
		if (SvcManager) {
			CloseServiceHandle(SvcManager);
		}
	} else { /* start PBS_INTERACTIVE service */
		SERVICE_TABLE_ENTRY ServiceTable[] = {
			{(TCHAR *)g_PbsInteractiveName, pbsinteractiveMain },
			{ 0 }
		};

		if (!StartServiceCtrlDispatcher(ServiceTable)) {
			ErrorMessage("StartServiceCntrlDispatcher");
		}
	}

	return 0;
}
