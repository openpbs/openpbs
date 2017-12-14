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
 * @file wrap_tcl_win.c
 *
 * @brief
 *		All the pbs specific code needed to make pbswish
 *		work is here.  The routine pbsTk_Init() is to be called
 *		in place of Tk_Init().
 *
 * Functions included are:
 * 	main()
 */

#include <stdio.h>
#include <sys/stat.h>
#include <pbs_config.h>

#include <string.h>
#include <stdlib.h>
#include "pbs_ifl.h"
#include "pbs_internal.h"

#include <windows.h>
#include "win.h"

/**
 * @brief
 * 		main function of wrap_tcl_win, which will creates a tcl wrapper process Windows.
 */
int
main(int argc, char *argv[])
{
	char	dirname[MAXPATHLEN+1];
	char	shortname[MAXPATHLEN+1];
	char	filename[MAXPATHLEN+1];

	char	pbs_wish_rel[MAXPATHLEN+1];
	char	pbs_cmd_rel[MAXPATHLEN+1];

	char	pbs_wish_dbg[MAXPATHLEN+1];
	char	pbs_cmd_dbg[MAXPATHLEN+1];

	char	pbs_wish_inst[MAXPATHLEN+1];
	char	pbs_cmd_inst[MAXPATHLEN+1];

	char	pbs_wish_def[MAXPATHLEN+1];
	char	pbs_cmd_def[MAXPATHLEN+1];

	char	pbs_wish_path[MAXPATHLEN+1];
	char	pbs_cmd_path[MAXPATHLEN+1];

	char	cmdbuf[4096];	/* should be sufficient! */
	char	*pc, *pc1, *pc2;
	struct	stat sb;
	int		i;
	STARTUPINFO             si = { 0 };
	PROCESS_INFORMATION     pi = { 0 };
	int	rc;

	pc1 = strrchr(argv[0], '/');
	pc2 = strrchr(argv[0], '\\');

	pbs_loadconf(0);

	if (pc1 > pc2)
		pc = pc1;
	else
		pc = pc2;

	if (pc) {
		strcpy(filename, pc+1);
		*pc = '\0';
		strcpy(dirname, argv[0]);
		if (pc == pc1)
			*pc = '/';
		else
			*pc = '\\';

	} else {
		strcpy(filename, argv[0]);
		strcpy(dirname, ".");
	}

	pc = strchr(filename, '.');
	if (pc) {
		*pc = '\0';
		strcpy(shortname, filename);
		*pc = '.';
	} else {
		strcpy(shortname, filename);
	}

	sprintf(pbs_wish_rel, "%s/../../Release/pbs_wish.exe", dirname);
	sprintf(pbs_cmd_rel, "%s/../%s.src", dirname, shortname);

	sprintf(pbs_wish_dbg, "%s/../../Debug/pbs_wish.exe", dirname);
	sprintf(pbs_cmd_dbg, "%s/../%s.src", dirname, shortname);

	if (pbs_conf.pbs_exec_path) {
		sprintf(pbs_wish_inst, "%s/bin/pbs_wish.exe", pbs_conf.pbs_exec_path);
		sprintf(pbs_cmd_inst, "%s/lib/%s/%s.src", pbs_conf.pbs_exec_path, shortname, shortname);
	} else {
		pbs_wish_inst[0] = '\0';
		pbs_cmd_inst[0] = '\0';
	}

	strcpy(pbs_wish_def, "C:/Program Files/pbs/bin/pbs_wish.exe");
	sprintf(pbs_cmd_def, "C:/Program Files/pbs/lib/%s/%s.src", shortname, shortname);


	if ((stat(pbs_wish_rel, &sb) == 0) && S_ISREG(sb.st_mode) && (stat(pbs_cmd_rel, &sb) == 0) &&
		S_ISREG(sb.st_mode)) {
		strcpy(pbs_wish_path, pbs_wish_rel);
		strcpy(pbs_cmd_path, pbs_cmd_rel);
	} else if ((stat(pbs_wish_dbg, &sb) == 0) && S_ISREG(sb.st_mode) && (stat(pbs_cmd_dbg, &sb) == 0) &&
		S_ISREG(sb.st_mode)) {
		strcpy(pbs_wish_path, pbs_wish_dbg);
		strcpy(pbs_cmd_path, pbs_cmd_dbg);
	} else if ((stat(pbs_wish_inst, &sb) == 0) && S_ISREG(sb.st_mode) && (stat(pbs_cmd_inst, &sb) == 0) &&
		S_ISREG(sb.st_mode)) {
		strcpy(pbs_wish_path, pbs_wish_inst);
		strcpy(pbs_cmd_path, pbs_cmd_inst);
	} else if ((stat(pbs_wish_def, &sb) == 0) && S_ISREG(sb.st_mode) && (stat(pbs_cmd_def, &sb) == 0) &&
		S_ISREG(sb.st_mode)) {
		strcpy(pbs_wish_path, pbs_wish_def);
		strcpy(pbs_cmd_path, pbs_cmd_def);
	} else {
		fprintf(stderr, "Did not find a suitable pbs_wish_path and pbs_cmd_path!");
		exit(1);
	}

	sprintf(cmdbuf, "\"%s\" \"%s\"", pbs_wish_path, pbs_cmd_path);
	for (i=1; i < argc; i++) {
		strcat(cmdbuf, " ");
		strcat(cmdbuf, argv[i]);
	}

	si.cb = sizeof(si);
	si.lpDesktop = NULL;

	rc = CreateProcess(NULL, cmdbuf, NULL, NULL, TRUE, CREATE_NO_WINDOW,
		NULL, NULL, &si, &pi);
	if (rc)
		WaitForSingleObject(pi.hProcess, INFINITE);
	else {
		printf("CreateProcess(%s) failed with error=%d\n",
			cmdbuf, GetLastError());
	}

	CloseHandle(pi.hThread);
	CloseHandle(pi.hProcess);
}
