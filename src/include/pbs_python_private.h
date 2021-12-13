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

#ifndef _PBS_PYTHON_PRIVATE_DEF
#define _PBS_PYTHON_PRIVATE_DEF

/*
 * This header file contains dependencies to be *ONLY* used by the embedded or
 * extesion Python/C routines. These are typically found in src/lib/Libpython.
 *
 * Always include this header file within #ifdef PYTHON
 *
 * IMPORTANT:
 *   Under no circumstance this header file should be included by sources out-
 *   side the src/lib/Libpython directory. Extranlize any needed functionalities
 *   provided by this routine using generic pointers and place them in <pbs_python.h>.
 *
 *   The motivation for doing this is care has been taken so that the actual python
 *   build environment CPPFLAGS and CFLAGS are passed to the compiler that acts on the
 *   source files that include this header file. There will be situations where this
 *   compiler flags could break or spit out warnings if it is passed to the whole build
 *   environment.
 *
 *
 *
 */

#include <Python.h>
#include <pbs_python.h> /* the pbs python external header file supporting
                             with or without built-in python */

/* The below is the C pbs python extension module */
#ifndef PBS_PYTHON_V1_MODULE_EXTENSION_NAME
#define PBS_PYTHON_V1_MODULE_EXTENSION_NAME "_pbs_v1"
#endif

/* The below is the pure pbs.v1 package */
#ifndef PBS_PYTHON_V1_MODULE
#define PBS_PYTHON_V1_MODULE "pbs.v1"
#endif

/* this is the dictionary containing all the types for the embedded interp */
#define PBS_PYTHON_V1_TYPES_DICTIONARY "EXPORTED_TYPES_DICT"

/*             BEGIN CONVENIENCE LOGGING MACROS                              */

/* Assumptions:
 *    log_buffer
 *    pbs_python_daemon_name
 */

#define LOG_EVENT_DEBUG_MACRO(_evtype)                                              \
	if (_evtype & PBSEVENT_DEBUG3)                                              \
		log_event(_evtype,                                                  \
			  PBS_EVENTCLASS_SERVER, LOG_DEBUG, pbs_python_daemon_name, \
			  log_buffer);                                              \
	else                                                                        \
		log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN | _evtype,               \
			  PBS_EVENTCLASS_SERVER, LOG_DEBUG, pbs_python_daemon_name, \
			  log_buffer);

#define DEBUG_ARG1_WRAP(_evtype, fmt, a)                        \
	do {                                                    \
		snprintf(log_buffer, LOG_BUF_SIZE - 1, fmt, a); \
		log_buffer[LOG_BUF_SIZE - 1] = '\0';            \
		LOG_EVENT_DEBUG_MACRO(_evtype);                 \
	} while (0)

#define DEBUG_ARG2_WRAP(_evtype, fmt, a, b)                        \
	do {                                                       \
		snprintf(log_buffer, LOG_BUF_SIZE - 1, fmt, a, b); \
		log_buffer[LOG_BUF_SIZE - 1] = '\0';               \
		LOG_EVENT_DEBUG_MACRO(_evtype);                    \
	} while (0)

#define DEBUG1_ARG1(fmt, a) DEBUG_ARG1_WRAP(PBSEVENT_DEBUG, fmt, a)
#define DEBUG2_ARG1(fmt, a) DEBUG_ARG1_WRAP(PBSEVENT_DEBUG2, fmt, a)
#define DEBUG3_ARG1(fmt, a) DEBUG_ARG1_WRAP(PBSEVENT_DEBUG3, fmt, a)
#define DEBUG1_ARG2(fmt, a, b) DEBUG_ARG2_WRAP(PBSEVENT_DEBUG, fmt, a, b)
#define DEBUG2_ARG2(fmt, a, b) DEBUG_ARG2_WRAP(PBSEVENT_DEBUG2, fmt, a, b)
#define DEBUG3_ARG2(fmt, a, b) DEBUG_ARG2_WRAP(PBSEVENT_DEBUG3, fmt, a, b)

#define LOG_ERROR_ARG2(fmt, a, b)                                  \
	do {                                                       \
		snprintf(log_buffer, LOG_BUF_SIZE - 1, fmt, a, b); \
		log_buffer[LOG_BUF_SIZE - 1] = '\0';               \
		(void) log_record(PBSEVENT_ERROR | PBSEVENT_FORCE, \
				  PBS_EVENTCLASS_SERVER, LOG_ERR,  \
				  pbs_python_daemon_name,          \
				  log_buffer);                     \
	} while (0)

#define IS_PBS_PYTHON_CMD(a) (((a) != NULL) && (strcmp((a), "pbs_python") == 0))

/*             END CONVENIENCE LOGGING MACROS                              */

/*
 * All Python Types from the pbs.v1 module
 */

/* declarations from common_python_utils.c */

extern void pbs_python_write_object_to_log(PyObject *, char *, int);

extern void pbs_python_write_error_to_log(const char *);
extern int pbs_python_modify_syspath(const char *, int);
extern int pbs_python_dict_set_item_integral_value(PyObject *,
						   const char *,
						   const Py_ssize_t);
extern int pbs_python_dict_set_item_string_value(PyObject *,
						 const char *,
						 const char *);
extern int pbs_python_object_set_attr_string_value(PyObject *,
						   const char *,
						   const char *);

extern int pbs_python_object_set_attr_integral_value(PyObject *,
						     const char *,
						     int);

extern int pbs_python_object_get_attr_integral_value(PyObject *,
						     const char *);

extern char *pbs_python_object_get_attr_string_value(PyObject *,
						     const char *);

extern char *pbs_python_object_str(PyObject *);

extern char *pbs_python_list_get_item_string_value(PyObject *, int);

extern PyObject *pbs_python_import_name(const char *, const char *);

/* declarations from module_pbs_v1.c */

extern PyObject *pbs_v1_module_init(void);
extern PyObject *pbs_v1_module_inittab(void);

/* declrations from pbs_python_svr_internal.c */

extern PyObject *
_pbs_python_event_get_param(char *name);

#endif /* _PBS_PYTHON_PRIVATE_DEF */
