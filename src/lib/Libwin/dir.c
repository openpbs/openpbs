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
#include <windows.h>
#include "win.h"
#include "log.h"
/**
 * @file	dir.c
 */
/**
 * @brief
 *	open given directory name.
 *
 * @param[in] name - directory name
 *
 * @return	pointer to dir struct
 * @retval	dir info		success
 * @retval	NULL			error
 *
 */
DIR *
opendir(const char *name)
{
	HANDLE  hdir;
	DIR     *dir;

	WIN32_FIND_DATA	data;

	char	search[_MAX_PATH+1];

	memset((char *)search, 0, sizeof(search));
	strncpy(search, name, _MAX_PATH);

	if (strlen(search)+3 > _MAX_PATH)
		return NULL;

	strncat(search, "/*", _MAX_PATH);

	hdir = FindFirstFile(search, &data);
	if (hdir == INVALID_HANDLE_VALUE) {
		log_errf(-1, __func__, "failed in FindFirstFile for %s", search);
		return NULL;
	}
	dir = (DIR *)malloc(sizeof(DIR));

	if (dir == NULL) {
		log_err(errno, __func__, "failed to allocate memory for dir");
		return NULL;
	}

	dir->handle = hdir;
	dir->pos = DIR_BEGIN;
	dir->entry = (struct dirent *)malloc(sizeof(struct dirent));

	if (dir->entry == NULL) {
		log_err(errno, __func__, "failed to allocate memory for dir->entry");
		(void)free(dir);
		return NULL;
	}

	strncpy(dir->entry->d_name, data.cFileName, _MAX_PATH);

	return (dir);
}

/**
 * @brief
 *	read content of specified directory.
 *
 * @param[in] - directory info
 *
 * @return	structure handle
 * @retval	pointer to dirent	success
 * @retval	NULL			error
 *
 */
struct dirent *
readdir(DIR *dir)
{
	WIN32_FIND_DATA data;
	int     rval;

	if (dir == NULL || dir->pos == DIR_END)
		return NULL;



	if (dir->pos == DIR_BEGIN) {
		dir->pos = DIR_MIDDLE;
		return (dir->entry);
	}

	rval = FindNextFile(dir->handle, &data);

	if (rval == 0) {
		dir->pos = DIR_END;
		if (GetLastError() != ERROR_NO_MORE_FILES)
			log_err(-1, __func__, "failed in FindNextFile");
		return NULL;
	}

	dir->pos = DIR_MIDDLE;
	strncpy(dir->entry->d_name, data.cFileName, _MAX_PATH);
	return (dir->entry);
}

/**
 * @brief
 *	 close directory
 *
 * @param[in] - hdir - pointer to dir
 *
 * @return	int
 * @retval	zero 	on success;
 * @retval	-1 	on failure
 *
 */
int
closedir(DIR *hdir)
{
	int ret;
	if (hdir == NULL)
		return (-1);

	ret = FindClose(hdir->handle);
	if (ret == 0) {
		log_err(-1, __func__, "failed in FindClose");
	}
	if (hdir->entry)
		(void)free(hdir->entry);

	(void)free(hdir);


	if (ret == 0)
		return (-1);

	return (0);

}

/**
 * @brief
 *	rename oldpath with newpath name.
 *
 * @param[in] oldpath - path
 * @param[in] newpath - path
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	error
 *
 */
int
link(const char *oldpath, const char *newpath)
{
	int	ret;

	ret = rename(oldpath, newpath);

	if (ret != 0) {
		errno = GetLastError();
		log_err(-1, __func__, "failed in rename");
		return (-1);
	}
	return (0);
}
