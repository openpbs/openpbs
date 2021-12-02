/*
 * Copyright (C) 1994-2021 Altair Engineering, Inc.
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

#include <pbs_config.h>
#include <wchar.h>
#include <Python.h>
#include "pbs_ifl.h"
#include "pbs_internal.h"
#include "log.h"

#ifdef WIN32

/**
 * @brief get_py_homepath
 * 	Find and return where python home is located
 *
 * NOTE: The caller must free the memory allocated by this function
 *
 * @param[in, out] homepath - buffer to copy python home path
 *
 * @return int
 * @retval 0 - Success
 * @retval 1 - Fail
 */

int
get_py_homepath(char **homepath)
{
#ifdef PYTHON
	static char python_homepath[MAXPATHLEN + 1] = {'\0'};
	if (python_homepath[0] == '\0') {
		snprintf(python_homepath, MAXPATHLEN, "%s/python", pbs_conf.pbs_exec_path);
		fix_path(python_homepath, 3);
		if (!file_exists(python_homepath)) {
			log_err(-1, __func__, "Python home not found!");
			return 1;
		}
	}
	*homepath = strdup(python_homepath);
	if (*homepath == NULL)
		return 1;
	return 0;
#else
	return 1;
#endif
}
#endif

/**
 * @brief get_py_progname
 * 	Find and return where python binary is located
 *
 * NOTE: The caller must free the memory allocated by this function
 *
 * @param[in, out] binpath - buffer to copy python binary path
 *
 * @return int
 * @retval 0 - Success
 * @retval 1 - Fail
 */
int
get_py_progname(char **binpath)
{
#ifdef PYTHON
	static char python_binpath[MAXPATHLEN + 1] = {'\0'};
	if (python_binpath[0] == '\0') {
#ifndef WIN32
		snprintf(python_binpath, MAXPATHLEN, "%s/python/bin/python3", pbs_conf.pbs_exec_path);
#else
		snprintf(python_binpath, MAXPATHLEN, "%s/python/python.exe", pbs_conf.pbs_exec_path);
		fix_path(python_binpath, 3);
#endif
		if (!file_exists(python_binpath)) {
#ifdef PYTHON_BIN_PATH
			snprintf(python_binpath, MAXPATHLEN, "%s", PYTHON_BIN_PATH);
			if (!file_exists(python_binpath))
#endif
			{
				log_err(-1, __func__, "Python executable not found!");
				return 1;
			}
		}
	}
	*binpath = strdup(python_binpath);
	if (*binpath == NULL)
		return 1;
	return 0;
#else
	return 1;
#endif
}
/**
 * @brief set_py_progname
 * 	Find and tell Python interpreter where python binary is located
 *
 * @return int
 * @retval 0 - Success
 * @retval 1 - Fail
 */
int
set_py_progname(void)
{
#ifdef PYTHON
	char *python_binpath = NULL;
	static wchar_t w_python_binpath[MAXPATHLEN + 1] = {'\0'};

	if (w_python_binpath[0] == '\0') {
		if (get_py_progname(&python_binpath)) {
			log_err(-1, __func__, "Failed to find python binary path!");
			return 1;
		}
		mbstowcs(w_python_binpath, python_binpath, MAXPATHLEN + 1);
		free(python_binpath);
	}
	Py_SetProgramName(w_python_binpath);
#ifdef WIN32
	/*
	 *  There is a bug in windows version of python resulting need to set python home explicitly.
	 */
	static wchar_t w_python_homepath[MAXPATHLEN + 1] = {'\0'};
	char *python_homepath = NULL;
	if (w_python_homepath[0] == '\0') {
		if (get_py_homepath(&python_homepath)) {
			log_err(-1, __func__, "Failed to find python home path!");
			return 1;
		}
		mbstowcs(w_python_homepath, python_homepath, MAXPATHLEN + 1);
		free(python_homepath);
	}
	Py_SetPythonHome(w_python_homepath);
#endif
	return 0;
#else
	return 0;
#endif
}
