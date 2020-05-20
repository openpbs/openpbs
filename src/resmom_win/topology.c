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

#include <windows.h>
#include <stdio.h>

#include "pbs_error.h"
#include "log.h"
#include "win.h"

typedef BOOL (WINAPI *LPFN_GLPI)(
    PSYSTEM_LOGICAL_PROCESSOR_INFORMATION,
    PDWORD);

/**
 * @brief
 *	count the number of physical sockets in the machine using
 *  GetLogicalProcessorInformation()
 *
 * @return	no. of sockets
 *
 */
int
count_sockets(void) {
	LPFN_GLPI glpi;
	BOOL done = FALSE;
	PSYSTEM_LOGICAL_PROCESSOR_INFORMATION buffer = NULL;
	PSYSTEM_LOGICAL_PROCESSOR_INFORMATION ptr = NULL;
	DWORD returnLength = 0;
	DWORD processorPackageCount = 0;
	DWORD byteOffset = 0;

	glpi = (LPFN_GLPI)GetProcAddress(GetModuleHandle(TEXT("kernel32")),
										"GetLogicalProcessorInformation");
	if (NULL == glpi) {
		log_err(-1, __func__,
				"GetLogicalProcessorInformation is not supported.");
		return (0);
	}

	while (!done) {
		DWORD rc = glpi(buffer, &returnLength);

		if (FALSE == rc) {
			if (GetLastError() == ERROR_INSUFFICIENT_BUFFER) {
				if (buffer)
					free(buffer);

				buffer =
					(PSYSTEM_LOGICAL_PROCESSOR_INFORMATION)malloc(returnLength);

				if (NULL == buffer) {
					log_err(PBSE_SYSTEM, __func__, "Error: Allocation failure");
					return (-1);
				}
			} else {
				sprintf(log_buffer, "Error %d", GetLastError());
				log_err(PBSE_SYSTEM, __func__, log_buffer);
				return (0);
			}
		} else {
			done = TRUE;
		}
	}

	ptr = buffer;

	while (byteOffset + sizeof(SYSTEM_LOGICAL_PROCESSOR_INFORMATION) <=
			returnLength) {
		if (ptr->Relationship == RelationProcessorPackage) {
			processorPackageCount++;
		}
		byteOffset += sizeof(SYSTEM_LOGICAL_PROCESSOR_INFORMATION);
		ptr++;
	}
	return processorPackageCount;
}

/**
 * @brief
 *	count the number of GPU in the machine using
 *  EnumDisplayDevices()
 *
 * @return	no. of gpu's
 *
 */
int
count_gpus(void) {
	DISPLAY_DEVICE dd;
	DWORD deviceNum;
	int gpucount = 0;
	char DeviceString[1024];

	dd.cb = sizeof(DISPLAY_DEVICE);
	deviceNum = 0;
	DeviceString[0] = '\0';

	while (EnumDisplayDevices(NULL, deviceNum, &dd, 0)) {
		if (!(dd.StateFlags & DISPLAY_DEVICE_MIRRORING_DRIVER) &&
			strncmp(DeviceString, dd.DeviceString, strlen(dd.DeviceString))) {
			gpucount++;
			strcpy(DeviceString, dd.DeviceString);
		}
		deviceNum++;
	}

	return gpucount;
}

/**
 * @brief
 *	count the number of Xeon Phi
 *
 * @return	no. of xeon phi's
 *
 */
int
count_mics(void) {
	return 0;
}
