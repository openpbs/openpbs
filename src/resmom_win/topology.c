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
