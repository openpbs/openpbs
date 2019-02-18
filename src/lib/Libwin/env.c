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
#include <stdio.h>
#include <windows.h>
#include <direct.h>
#include <Userenv.h>
#include <shlobj.h>
#include "win.h"
#include "pbs_ifl.h"
extern int GetComputerDomainName(char domain_name[]);

static char	homepath[MAXPATHLEN+1] = "";
static char	sysrootdir[MAXPATHLEN+1] = "";
static char	sysdrive[MAXPATHLEN+1] = "";
static char	temp_path[MAXPATHLEN+1] = "";
static char	user_domain[PBS_MAXHOSTNAME+1] = "";
static char	value_buf[ENV_BUF_SIZE] = "";
/**
 * @file	env.c
 */
/**
 * @brief
 * 	_setenv_win: Set an environment variable
 *
 * @param[in] key - string holding key for environment variable
 * @param[in] value - string holding value for environment variable
 * @param[in] interrupt - int value to override existing value, not used in Windows
 *
 * @return	int
 * @retval	0		success
 * @retval	non-zero	error

 */
int
_setenv_win(char* key, char* value, int overwrite)
{
	errno = 0;

	if(!GetEnvironmentVariable(key, value_buf, ENV_BUF_SIZE) && !overwrite)
		if(!GetLastError() == ERROR_ENVVAR_NOT_FOUND)
			return 0;

	if(!SetEnvironmentVariable(key, value)){
		errno = GetLastError();
		return errno;
	}

	return 0;
}
/**
 * @brief
 * 	_getenv_win: Get value of an environment variable
 *
 * @param[in] key - string holding key for environment variable
 * @param[in] value - string buffer where value for environment variable will be returned
 * @param[in] buffer size - int value to specify max length
 *
 * @return	char*
 * @retval	value of key in the environment 	success
 * @retval	NULL								error

 */
char *
_getenv_win(char *key)
{
	errno = 0;
	memset(value_buf, 0, sizeof(value_buf));

	if(!GetEnvironmentVariable(key, value_buf, ENV_BUF_SIZE)){
		if(GetLastError() == ERROR_ENVVAR_NOT_FOUND){
			errno = ERROR_ENVVAR_NOT_FOUND;
			return NULL;
		}
	}

	return value_buf;
}
/**
 * @brief
 * 	save_env: gets/sets some important environment variable values that can
 *	be accessed later.
 *
 * @par	NOTE: Some windows calls like socket() and gethostbyname() are
 *	dependent on having certain environment variables like
 *	SYSTEMROOT and SYSTEMDRIVE be set in order to work. This
 *	call will do just that.
 */
void
save_env(void)
{
	char	*upath, *up, *drive;
	char    drive_info[10];	/* A: ... Z: */
	char    env_string[2*MAXPATHLEN+1];

	/* Don't run this function if previously ran already */
	if( (strcmp(homepath, "") != 0) && \
	    (strcmp(sysrootdir, "") != 0) && \
	    (strcmp(sysdrive, "") != 0) && \
	    (strcmp(temp_path, "") != 0) && \
            (strcmp(user_domain, "") != 0) ) {  /* not saved */
		return;
	}

	/* The following figures out the default value for HOMEPATH */

	drive = getenv("SystemDrive");

	if (drive == NULL) {
		drive = getenv("SYSTEMDRIVE");

		if (drive == NULL) {
			sprintf(drive_info, "%c:", (_getdrive() + 'A' - 1));
			drive = (char *)drive_info;
		}
	}
	sprintf(homepath, "%s\\", drive);

	upath = getenv("ALLUSERSPROFILE");
	if (upath) {
		strcpy(homepath, upath);
		up =  strrchr(homepath, '\\');
		if (up)
			*up = '\0';
	}

	/* The following figures out the  value for SYSTEMROOT */
	strcpy(sysrootdir, "C:\\WINNT");
	upath = getenv("SYSTEMROOT");
	if (upath) {
		strcpy(sysrootdir, upath);
	} else {
		upath = getenv("SystemRoot");

		if (upath)
			strcpy(sysrootdir, upath);
		else
			SHGetFolderPath(NULL, CSIDL_WINDOWS, NULL,
				SHGFP_TYPE_DEFAULT, sysrootdir);
	}

	/* Set the SYSTEMROOT and SystemRoot environment variables */
	setenv("SYSTEMROOT", sysrootdir, 1);

	setenv("SystemRoot", sysrootdir, 1);

	/* The following figures out the value for SYSTEMDRIVE */
	strcpy(sysdrive, "C:");
	if (drive) {
		strcpy(sysdrive, drive);
	}

	/* Set the SYSTEMDRIVE and SystemDrive environment variables */
	setenv("SYSTEMDRIVE", sysdrive, 1);

	setenv("SystemDrive", sysdrive, 1);

	/* The following figures out the value for TEMP */
	strcpy(temp_path, "");
	upath = getenv("TEMP");
	if (upath) {
		strcpy(temp_path, upath);
	}

	/* The following figures out the value for USERDOMAIN */
	strcpy(user_domain, "");
	upath = getenv("USERDOMAIN");
	if (upath) {
		strcpy(user_domain, upath);
	} else {
		GetComputerDomainName(user_domain);
	}
}

/**
 * @brief
 * 	get_saved_env: return the corresponding value for the following:
 *	"HOMEPATH", "SYSTEMROOT", "SYSTEMDRIVE", "TEMP", and "USERDOMAIN".
 *
 * @param[in] e - string holding value for environment variables
 *
 * @return	string
 * @retval	environment var value	success
 * @retval	NULL			error
 *
 */
char *
get_saved_env(char *e)
{

	if( (strcmp(homepath, "") == 0) && \
	    (strcmp(sysrootdir, "") == 0) && \
	    (strcmp(sysdrive, "") == 0) && \
	    (strcmp(temp_path, "") == 0) && \
            (strcmp(user_domain, "") == 0) ) {  /* not saved */
		save_env();
	}

	if (strcmp(e, "HOMEPATH") == 0)
		return (homepath);
	if (strcmp(e, "SYSTEMROOT") == 0)
		return (sysrootdir);
	if (strcmp(e, "SYSTEMDRIVE") == 0)
		return (sysdrive);
	if (strcmp(e, "TEMP") == 0)
		return (temp_path);
	if (strcmp(e, "USERDOMAIN") == 0)
		return (user_domain);
	return NULL;
}
