/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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
 * @file    sched_func.c
 *
 *@brief
 * 		sched_func.c - various functions dealing with schedulers
 *
 */
#include <pbs_config.h>

#ifdef PYTHON
#include <Python.h>
#endif

#include <ctype.h>
#include <errno.h>
#include <string.h>
#include <memory.h>

#include <pbs_python.h>
#include "pbs_share.h"
#include "pbs_sched.h"
#include "log.h"
#include "pbs_ifl.h"
#include "pbs_db.h"
#include "pbs_error.h"
#include "pbs_sched.h"
#include "pbs_share.h"
#include "resource.h"
#include "sched_cmds.h"
#include "server.h"
#include <server_limits.h>
#include "svrfunc.h"

extern struct server server;

/* Functions */
#ifdef PYTHON
extern char *pbs_python_object_str(PyObject *);
#endif /* PYTHON */


extern pbs_db_conn_t *svr_db_conn;

/**
 * @brief	Helper function to write job sort formula to a sched's sched_priv
 *
 * @param[in]	formula - the formula to write
 * @param[in]	sched_priv_path - path to scheduler's sched_priv
 *
 * @return	int
 * @return 	PBSE_NONE for Success
 * @return	PBSE_ error code for Failure
 */
static int
write_job_sort_formula(char *formula, char *sched_priv_path)
{
	char pathbuf[MAXPATHLEN];
	FILE *fp;

	snprintf(pathbuf, sizeof(pathbuf), "%s/%s", sched_priv_path, FORMULA_FILENAME);
	if ((fp = fopen(pathbuf, "w")) == NULL) {
		return PBSE_SYSTEM;
	}

	fprintf(fp, "### PBS INTERNAL FILE DO NOT MODIFY ###\n");
	fprintf(fp, "%s\n", formula);
	fclose(fp);

	return PBSE_NONE;
}

/**
 * @brief
 * 	validate_job_formula - validate that the sorting forumla is in the
 *	correct form.  We do this by calling python and having
 *	it catch exceptions.
 *
 */
int
validate_job_formula(attribute *pattr, void *pobject, int actmode)
{
	char *formula;
	char *errmsg = NULL;
	struct resource_def *pres;
	char buf[1024];
	char *globals1 = NULL;
	int globals_size1 = 1024;
	char *globals2 = NULL;
	int globals_size2 = 1024;
	char *script = NULL;
	int script_size = 2048;
	PyThreadState *ts_main = NULL;
	PyThreadState *ts_sub = NULL;
	pbs_sched *psched = NULL;
	int rc = 0;
	int err = 0;

	if (actmode == ATR_ACTION_FREE)
		return (0);

#ifndef PYTHON
	return PBSE_INTERNAL;
#else

	formula = pattr->at_val.at_str;
	if (formula == NULL)
		return PBSE_INTERNAL;

	if (pobject == &server) {
		/* check if any sched's JSF is set to a different, incompatible value */
		for (psched = (pbs_sched *) GET_NEXT(svr_allscheds);
				psched != NULL;
				psched = (pbs_sched *) GET_NEXT(psched->sc_link)) {
			attribute *jsf_attr = NULL;

			jsf_attr = &(psched->sch_attr[SCHED_ATR_job_sort_formula]);
			if (jsf_attr->at_flags & ATR_VFLAG_SET) {
				if (strcmp(jsf_attr->at_val.at_str, formula) != 0)
					return PBSE_SVR_SCHED_JSF_INCOMPAT;
			}
		}
	} else {
		/* Check if server's JSF is set to a different value */
		if ((server.sv_attr[SRV_ATR_job_sort_formula].at_flags & ATR_VFLAG_SET) &&
				strcmp(server.sv_attr[SRV_ATR_job_sort_formula].at_val.at_str, formula) != 0)
			return PBSE_SVR_SCHED_JSF_INCOMPAT;
	}

	if (!Py_IsInitialized())
		return PBSE_INTERNAL;

	globals1 = malloc(globals_size1);
	if(globals1 == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}

	globals2 = malloc(globals_size2);
	if(globals2 == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}

	strcpy(globals1, "globals1={");
	strcpy(globals2, "globals2={");

	/* We need to create a python dictionary to pass to python as a list
	 * of valid symbols.
	 */

	for (pres = svr_resc_def; pres; pres = pres->rs_next) {
		/* unknown resource is used as a delimiter between builtin and custom resources */
		if (strcmp(pres->rs_name, RESOURCE_UNKNOWN) != 0) {
			snprintf(buf, sizeof(buf), "\'%s\':1,", pres->rs_name);
			if(pbs_strcat(&globals1, &globals_size1, buf) == NULL) {
				rc = PBSE_SYSTEM;
				goto validate_job_formula_exit;
			}
			if (pres->rs_type == ATR_TYPE_LONG ||
				pres->rs_type == ATR_TYPE_SIZE ||
				pres->rs_type == ATR_TYPE_LL ||
				pres->rs_type == ATR_TYPE_SHORT ||
				pres->rs_type ==  ATR_TYPE_FLOAT) {
				if(pbs_strcat(&globals2, &globals_size2, buf) ==  NULL) {
					rc = PBSE_SYSTEM;
					goto validate_job_formula_exit;
				}
			}

		}
	}

	snprintf(buf, sizeof(buf), "\'%s\':1, '%s':1, \'%s\':1,\'%s\':1, \'%s\':1, \'%s\':1, \'%s\':1, \'%s\': 1}\n",
		FORMULA_ELIGIBLE_TIME, FORMULA_QUEUE_PRIO, FORMULA_JOB_PRIO,
		FORMULA_FSPERC, FORMULA_FSPERC_DEP, FORMULA_TREE_USAGE, FORMULA_FSFACTOR, FORMULA_ACCRUE_TYPE);
	if (pbs_strcat(&globals1, &globals_size1, buf) == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}
	if (pbs_strcat(&globals2, &globals_size2, buf) == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}

	/* Allocate a buffer for the Python code */
	script = malloc(script_size);
	if (script == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}
	*script = '\0';

	/* import math and initialize variables */
	sprintf(buf,
		"ans = 0\n"
		"errnum = 0\n"
		"errmsg = \'\'\n"
		"try:\n"
		"    from math import *\n"
		"except ImportError as e:\n"
		"    errnum=4\n"
		"    errmsg=str(e)\n");
	if (pbs_strcat(&script, &script_size, buf) == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}
	/* set up our globals dictionary */
	if (pbs_strcat(&script, &script_size, globals1) == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}
	if (pbs_strcat(&script, &script_size, globals2) == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}
	/* Now for the real guts: The initial try/except block*/
	sprintf(buf,
		"try:\n"
		"    exec(\'ans=");
	if (pbs_strcat(&script, &script_size, buf) == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}
	if (pbs_strcat(&script, &script_size, formula) == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}
	sprintf(buf, "\', globals1, locals())\n"
		"except SyntaxError as e:\n"
		"    errnum=1\n"
		"    errmsg=str(e)\n"
		"except NameError as e:\n"
		"    errnum=2\n"
		"    errmsg=str(e)\n"
		"except Exception as e:\n"
		"    pass\n"
		"if errnum == 0:\n"
		"    try:\n"
		"        exec(\'ans=");
	if (pbs_strcat(&script, &script_size, buf) == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}
	if (pbs_strcat(&script, &script_size, formula) == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}
	sprintf(buf, "\', globals2, locals())\n"
		"    except NameError as e:\n"
		"        errnum=3\n"
		"        errmsg=str(e)\n"
		"    except Exception as e:\n"
		"        pass\n");
	if (pbs_strcat(&script, &script_size, buf) == NULL) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}

	/* run the script in a subinterpreter */
	ts_main = PyThreadState_Get();
	ts_sub = Py_NewInterpreter();
	if (!ts_sub) {
		rc = PBSE_SYSTEM;
		goto validate_job_formula_exit;
	}
	err = PyRun_SimpleString(script);

	/* peek into the interpreter to get the values of err and errmsg */
	if (err == 0) {
		PyObject *module;
		PyObject *dict;
		PyObject *val;
		err = -1;
		if ((module = PyImport_AddModule("__main__"))) {
			if ((dict = PyModule_GetDict(module))) {
				char *p;
				if ((val = PyDict_GetItemString(dict, "errnum"))) {
					p = pbs_python_object_str(val);
					if (*p != '\0')
						err = atoi(p);
				}
				if ((val = PyDict_GetItemString(dict, "errmsg"))) {
					p = pbs_python_object_str(val);
					if (*p != '\0')
						errmsg = strdup(p);
				}
			}
		}
	}

	switch(err)
	{
		case 0: /* Success */
			rc = 0;
			break;
		case 1: /* Syntax error in formula */
			rc = PBSE_BAD_FORMULA;
			break;
		case 2: /* unknown resource name */
			rc = PBSE_BAD_FORMULA_KW;
			break;
		case 3: /* resource of non-numeric type */
			rc = PBSE_BAD_FORMULA_TYPE;
			break;
		case 4: /* import error */
			rc = PBSE_SYSTEM;
			break;
		default: /* unrecognized error */
			rc = PBSE_INTERNAL;
			break;
	}

	if (err == 0) {
		if (pobject == &server) {
			/* Write formula to all scheds' sched_priv */
			for (psched = (pbs_sched *) GET_NEXT(svr_allscheds);
					psched != NULL;
					psched = (pbs_sched *) GET_NEXT(psched->sc_link)) {
				rc = write_job_sort_formula(formula, psched->sch_attr[SCHED_ATR_sched_priv].at_val.at_str);
				if (rc != PBSE_NONE)
					goto validate_job_formula_exit;
			}
		} else {	/* Write formula to a specific sched's sched_priv */
			psched = (pbs_sched *) pobject;
			rc = write_job_sort_formula(formula, psched->sch_attr[SCHED_ATR_sched_priv].at_val.at_str);
			if (rc != PBSE_NONE)
				goto validate_job_formula_exit;
		}

	} else {
		snprintf(buf, sizeof(buf), "Validation Error: %s", errmsg?errmsg:"Internal error");
		log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_SERVER, LOG_DEBUG, __func__, buf);
	}

validate_job_formula_exit:
	if (ts_main) {
		if (ts_sub)
			Py_EndInterpreter(ts_sub);
		PyThreadState_Swap(ts_main);
	}
	free(script);
	free(globals1);
	free(globals2);
	free(errmsg);
	return rc;
#endif


}

/**
 * @brief
 * 		sched_alloc - allocate space for a pbs_sched structure and
 * 		initialize attributes to "unset" and pbs_sched object is added
 * 		to svr_allscheds list
 *
 * @param[in]	sched_name	- scheduler  name
 *
 * @return	pbs_sched *
 * @retval	null	- space not available.
 */
pbs_sched *
sched_alloc(char *sched_name)
{
	int i;
	pbs_sched *psched;

	psched = calloc(1, sizeof(pbs_sched));

	if (psched == NULL) {
		log_err(errno, __func__, "Unable to allocate memory (malloc error)");
		return NULL;
	}

	CLEAR_LINK(psched->sc_link);
	strncpy(psched->sc_name, sched_name, PBS_MAXSCHEDNAME);
	psched->sc_name[PBS_MAXSCHEDNAME] = '\0';
	psched->svr_do_schedule = SCH_SCHEDULE_NULL;
	psched->svr_do_sched_high = SCH_SCHEDULE_NULL;
	psched->scheduler_sock = -1;
	psched->scheduler_sock2 = -1;
	append_link(&svr_allscheds, &psched->sc_link, psched);

	/* set the working attributes to "unspecified" */

	for (i = 0; i < (int) SCHED_ATR_LAST; i++) {
		clear_attr(&psched->sch_attr[i], &sched_attr_def[i]);
	}

	return (psched);
}

/**
 * @brief find a scheduler
 *
 * @param[in]	sched_name - scheduler name
 *
 * @return	pbs_sched *
 */

pbs_sched *
find_sched(char *sched_name)
{
	pbs_sched *psched = NULL;
	if (!sched_name)
		return NULL;
	psched = (pbs_sched *) GET_NEXT(svr_allscheds);
	while (psched != NULL) {
		if (strcmp(sched_name, psched->sc_name) == 0)
			break;
		psched = (pbs_sched *) GET_NEXT(psched->sc_link);
	}
	return (psched);
}

/**
 * @brief free sched structure
 *
 * @param[in]	psched	- The pointer to the sched to free
 *
 */
void
sched_free(pbs_sched *psched)
{
	int i;
	attribute *pattr;
	attribute_def *pdef;

	/* remove any malloc working attribute space */

	for (i = 0; i < (int) SCHED_ATR_LAST; i++) {
		pdef = &sched_attr_def[i];
		pattr = &psched->sch_attr[i];

		pdef->at_free(pattr);
	}

	/* now free the main structure */
	delete_link(&psched->sc_link);
	(void) free(psched);
}

/**
 * @brief - purge scheduler from system
 *
 * @param[in]	psched	- The pointer to the delete to delete
 *
 * @return	error code
 * @retval	0	- scheduler purged
 * @retval	PBSE_OBJBUSY	- scheduler deletion not allowed
 */
int
sched_delete(pbs_sched *psched)
{
	pbs_db_obj_info_t obj;
	pbs_db_sched_info_t dbsched;
	pbs_db_conn_t *conn = (pbs_db_conn_t *) svr_db_conn;

	if (psched == NULL)
		return (0);

	/* TODO check for scheduler activity and return PBSE_OBJBUSY */
	/* delete scheduler from database */
	strcpy(dbsched.sched_name, psched->sc_name);
	obj.pbs_db_obj_type = PBS_DB_SCHED;
	obj.pbs_db_un.pbs_db_sched = &dbsched;
	if (pbs_db_delete_obj(conn, &obj) != 0) {
		snprintf(log_buffer, LOG_BUF_SIZE,
				"delete of scheduler %s from datastore failed",
				psched->sc_name);
		log_err(errno, __func__, log_buffer);
	}
	sched_free(psched);

	return (0);
}

/**
 * @brief
 * 		action routine for the sched's "sched_port" attribute
 *
 * @param[in]	pattr	-	attribute being set
 * @param[in]	pobj	-	Object on which attribute is being set
 * @param[in]	actmode	-	the mode of setting, recovery or just alter
 *
 * @return	error code
 * @retval	PBSE_NONE	-	Success
 * @retval	!PBSE_NONE	-	Failure
 *
 */
int
action_sched_port(attribute *pattr, void *pobj, int actmode)
{
	pbs_sched *psched;
	psched = (pbs_sched *) pobj;

	if (actmode == ATR_ACTION_NEW || actmode == ATR_ACTION_ALTER || actmode == ATR_ACTION_RECOV) {
		if ( dflt_scheduler && psched != dflt_scheduler) {
			psched->pbs_scheduler_port = pattr->at_val.at_long;
		}
	}
	return PBSE_NONE;
}

/**
 * @brief
 * 		action routine for the sched's "sched_host" attribute
 *
 * @param[in]	pattr	-	attribute being set
 * @param[in]	pobj	-	Object on which attribute is being set
 * @param[in]	actmode	-	the mode of setting, recovery or just alter
 *
 * @return	error code
 * @retval	PBSE_NONE	-	Success
 * @retval	!PBSE_NONE	-	Failure
 *
 */
int
action_sched_host(attribute *pattr, void *pobj, int actmode)
{
	pbs_sched *psched;
	psched = (pbs_sched *) pobj;

	if (actmode == ATR_ACTION_NEW || actmode == ATR_ACTION_ALTER || actmode == ATR_ACTION_RECOV) {
		if ( dflt_scheduler && psched != dflt_scheduler) {
			psched->pbs_scheduler_addr = get_hostaddr(pattr->at_val.at_str);
			if (psched->pbs_scheduler_addr == (pbs_net_t)0)
				return PBSE_BADATVAL;
		}
	}
	return PBSE_NONE;
}

/**
 * @brief
 * 		action routine for the sched's "sched_priv" attribute
 *
 * @param[in]	pattr	-	attribute being set
 * @param[in]	pobj	-	Object on which attribute is being set
 * @param[in]	actmode	-	the mode of setting, recovery or just alter
 *
 * @return	error code
 * @retval	PBSE_NONE	-	Success
 * @retval	!PBSE_NONE	-	Failure
 *
 */
int
action_sched_priv(attribute *pattr, void *pobj, int actmode)
{
	pbs_sched* psched;

	psched = (pbs_sched *) pobj;

	if (pobj == dflt_scheduler)
		return PBSE_SCHED_OP_NOT_PERMITTED;

	if (actmode == ATR_ACTION_NEW || actmode == ATR_ACTION_ALTER || actmode == ATR_ACTION_RECOV) {
		psched = (pbs_sched *) GET_NEXT(svr_allscheds);
		while (psched != NULL) {
			if (psched->sch_attr[SCHED_ATR_sched_priv].at_flags & ATR_VFLAG_SET) {
				if (!strcmp(psched->sch_attr[SCHED_ATR_sched_priv].at_val.at_str, pattr->at_val.at_str)) {
					if (psched != pobj) {
						return PBSE_SCHED_PRIV_EXIST;
					} else
						break;
				}
			}
			psched = (pbs_sched*) GET_NEXT(psched->sc_link);
		}
	}
	if (actmode == ATR_ACTION_NEW || actmode == ATR_ACTION_ALTER)
		(void)contact_sched(SCH_ATTRS_CONFIGURE, NULL, psched->pbs_scheduler_addr, psched->pbs_scheduler_port);
	return PBSE_NONE;
}

/**
 * @brief
 * 		action routine for the sched's "sched_log" attribute
 *
 * @param[in]	pattr	-	attribute being set
 * @param[in]	pobj	-	Object on which attribute is being set
 * @param[in]	actmode	-	the mode of setting, recovery or just alter
 *
 * @return	error code
 * @retval	PBSE_NONE	-	Success
 * @retval	!PBSE_NONE	-	Failure
 *
 */
int
action_sched_log(attribute *pattr, void *pobj, int actmode)
{
	pbs_sched* psched;
	psched = (pbs_sched *) pobj;

	if (pobj == dflt_scheduler)
		return PBSE_SCHED_OP_NOT_PERMITTED;

	if (actmode == ATR_ACTION_NEW || actmode == ATR_ACTION_ALTER || actmode == ATR_ACTION_RECOV) {
		psched = (pbs_sched*) GET_NEXT(svr_allscheds);
		while (psched != NULL) {
			if (psched->sch_attr[SCHED_ATR_sched_log].at_flags & ATR_VFLAG_SET) {
				if (!strcmp(psched->sch_attr[SCHED_ATR_sched_log].at_val.at_str, pattr->at_val.at_str)) {
					if (psched != pobj) {
						return PBSE_SCHED_LOG_EXIST;
					} else
						break;
				}
			}
			psched = (pbs_sched*) GET_NEXT(psched->sc_link);
		}
	}
	if (actmode != ATR_ACTION_RECOV)
		(void)contact_sched(SCH_ATTRS_CONFIGURE, NULL, psched->pbs_scheduler_addr, psched->pbs_scheduler_port);
	return PBSE_NONE;
}

/**
 * @brief action function for 'log_events' sched attribute
 * 
 * @param[in]	pattr		attribute being set
 * @param[in]	pobj		Object on which the attribute is being set
 * @param[in]	actmode		the mode of setting
 * 
 * @return error code
 */
int
action_sched_log_events(attribute *pattr, void *pobj, int actmode)
{
	pbs_sched *psched;
	psched = (pbs_sched *) pobj;

	if (actmode != ATR_ACTION_RECOV)
		set_scheduler_flag(SCH_ATTRS_CONFIGURE, psched);

		    return PBSE_NONE;
}

/**
 * @brief
 * 		action routine for the sched's "sched_iteration" attribute
 *
 * @param[in]	pattr	-	attribute being set
 * @param[in]	pobj	-	Object on which attribute is being set
 * @param[in]	actmode	-	the mode of setting, recovery or just alter
 *
 * @return	error code
 * @retval	PBSE_NONE	-	Success
 * @retval	!PBSE_NONE	-	Failure
 *
 */
int
action_sched_iteration(attribute *pattr, void *pobj, int actmode)
{
	if (pobj == dflt_scheduler) {
			server.sv_attr[SRV_ATR_scheduler_iteration].at_val.at_long = pattr->at_val.at_long;
			server.sv_attr[SRV_ATR_scheduler_iteration].at_flags |= ATR_VFLAG_SET | ATR_VFLAG_MODIFY | ATR_VFLAG_MODCACHE;
			svr_save_db(&server, SVR_SAVE_FULL);
	}
	return PBSE_NONE;
}

/**
 * @brief
 * 		action routine for the sched's "sched_user" attribute
 *
 * @param[in]	pattr	-	attribute being set
 * @param[in]	pobj	-	Object on which attribute is being set
 * @param[in]	actmode	-	the mode of setting, recovery or just alter
 *
 * @return	error code
 * @retval	PBSE_NONE	-	Success
 * @retval	!PBSE_NONE	-	Failure
 *
 */
int
action_sched_user(attribute *pattr, void *pobj, int actmode)
{
	if (actmode == ATR_ACTION_ALTER) {
		/*TODO*/
	}
	return PBSE_NONE;
}

/**
 * @brief
 * 		action routine for the sched's "preempt_order" attribute
 *
 * @param[in]	pattr	-	attribute being set
 * @param[in]	pobj	-	Object on which attribute is being set
 * @param[in]	actmode	-	the mode of setting, recovery or just alter
 *
 * @return	error code
 * @retval	PBSE_NONE	-	Success
 * @retval	!PBSE_NONE	-	Failure
 *
 */
int
action_sched_preempt_order(attribute *pattr, void *pobj, int actmode)
{
	char *tok = NULL;
	char *endp = NULL;
	pbs_sched *psched = pobj;

	if ((actmode == ATR_ACTION_ALTER) || (actmode == ATR_ACTION_RECOV)) {
		char copy[256] = {0};

		if (!(pattr->at_val.at_str))
			return PBSE_BADATVAL;
		strcpy(copy, pattr->at_val.at_str);
		tok = strtok(copy, "\t ");

		if (tok != NULL && !isdigit(tok[0])) {
			int i = 0;
			int num = 0;
			char s_done = 0;
			char c_done = 0;
			char r_done = 0;
			char d_done = 0;
			char next_is_num = 0;

			psched->preempt_order[0].order[0] = PREEMPT_METHOD_LOW;
			psched->preempt_order[0].order[1] = PREEMPT_METHOD_LOW;
			psched->preempt_order[0].order[2] = PREEMPT_METHOD_LOW;
			psched->preempt_order[0].order[3] = PREEMPT_METHOD_LOW;

			psched->preempt_order[0].high_range = 100;
			i = 0;
			do {
				int j = 0;
				j = isdigit(tok[0]);
				if (j) {
					if (next_is_num) {
						num = strtol(tok, &endp, 10);
						if (*endp == '\0') {
							psched->preempt_order[i].low_range = num + 1;
							i++;
							psched->preempt_order[i].high_range = num;
							next_is_num = 0;
						} else
							return PBSE_BADATVAL;
					} else
						return PBSE_BADATVAL;
				} else if (!next_is_num) {
					for (j = 0; tok[j] != '\0' ; j++) {
						switch (tok[j]) {
							case 'S':
								if (!s_done) {
									psched->preempt_order[i].order[j] = PREEMPT_METHOD_SUSPEND;
									s_done = 1;
								} else
									return PBSE_BADATVAL;
								break;
							case 'C':
								if (!c_done) {
									psched->preempt_order[i].order[j] = PREEMPT_METHOD_CHECKPOINT;
									c_done = 1;
								} else
									return PBSE_BADATVAL;
								break;
							case 'R':
								if (!r_done) {
									psched->preempt_order[i].order[j] = PREEMPT_METHOD_REQUEUE;
									r_done = 1;
								} else
									return PBSE_BADATVAL;
								break;
							case 'D':
								if (!d_done) {
									psched->preempt_order[i].order[j] = PREEMPT_METHOD_DELETE;
									d_done = 1;
								} else 
									return PBSE_BADATVAL;
								break;

						default:
							return PBSE_BADATVAL;
						}
						next_is_num = 1;
					}
					s_done = 0;
					c_done = 0;
					r_done = 0;
					d_done = 0;
				}
				else
					return PBSE_BADATVAL;
				tok = strtok(NULL, "\t ");
			} while (tok != NULL && i < PREEMPT_ORDER_MAX);

			if (tok != NULL)
				return PBSE_BADATVAL;

			psched->preempt_order[i].low_range = 0;
		} else
			return PBSE_BADATVAL;
	}
	return PBSE_NONE;
}

/**
 * @brief
 * 		poke_scheduler - action routine for the server's "scheduling" attribute.
 *		Call the scheduler whenever the attribute is set (or reset) to true.
 *
 * @param[in]	pattr	-	pointer to attribute structure
 * @param[in]	pobj	-	not used
 * @param[in]	actmode	-	action mode
 *
 * @return	int
 * @retval	zero	: success
 */

int
poke_scheduler(attribute *pattr, void *pobj, int actmode)
{
	if (pobj == &server || pobj == dflt_scheduler) {
		if (pobj == &server) {
			/* set this attribute on main scheduler */
			if (dflt_scheduler) {
				sched_attr_def[(int) SCHED_ATR_scheduling].at_set(&dflt_scheduler->sch_attr[(int) SCHED_ATR_scheduling], pattr, SET);
				(void)sched_save_db(dflt_scheduler, SVR_SAVE_FULL);
			}
		} else {
			svr_attr_def[(int) SRV_ATR_scheduling].at_set(&server.sv_attr[SRV_ATR_scheduling], pattr, SET);
			svr_save_db(&server, SVR_SAVE_QUICK);
		}
		if (actmode == ATR_ACTION_ALTER) {
			if (pattr->at_val.at_long)
				set_scheduler_flag(SCH_SCHEDULE_CMD, dflt_scheduler);
		}
	} else {
		if (actmode == ATR_ACTION_ALTER) {
			if (pattr->at_val.at_long)
				set_scheduler_flag(SCH_SCHEDULE_CMD, (pbs_sched *)pobj);
		}
	}
	return PBSE_NONE;
}

/**
 * @brief
 * 		Sets default scheduler attributes
 *
 * @param[in] psched		- Scheduler
 * @parma[in] unset_flag	- flag to indicate if this function is called after unset of any sched attributes.
 * @parma[in] from_scheduler	- flag to indicate if this function is called on a request from scheduler.
 *
 *
  */
void
set_sched_default(pbs_sched *psched, int unset_flag, int from_scheduler)
{
	char *temp;
	char dir_path[MAXPATHLEN +1] = {0};
	int flag = 0;

	if (!psched)
		return;

	if ((psched->sch_attr[(int) SCHED_ATR_sched_cycle_len].at_flags & ATR_VFLAG_SET) == 0) {
		set_attr_svr(&(psched->sch_attr[(int) SCHED_ATR_sched_cycle_len]), &sched_attr_def[(int) SCHED_ATR_sched_cycle_len],
			TOSTR(PBS_SCHED_CYCLE_LEN_DEFAULT));
	}
	if (!unset_flag && (psched->sch_attr[(int) SCHED_ATR_schediteration].at_flags & ATR_VFLAG_SET) == 0) {
		set_attr_svr(&(psched->sch_attr[(int) SCHED_ATR_schediteration]), &sched_attr_def[(int) SCHED_ATR_schediteration],
			TOSTR(PBS_SCHEDULE_CYCLE));
	}
	if ((psched->sch_attr[(int) SCHED_ATR_scheduling].at_flags & ATR_VFLAG_SET) == 0) {
		if (psched != dflt_scheduler)
			temp = "0";
		else
			temp = "1";
		set_attr_svr(&(psched->sch_attr[(int) SCHED_ATR_scheduling]), &sched_attr_def[(int) SCHED_ATR_scheduling], temp);
	}
	if ((psched->sch_attr[(int) SCHED_ATR_sched_state].at_flags & ATR_VFLAG_SET) == 0) {
			if (psched != dflt_scheduler)
				temp = SC_DOWN;
			else
				temp = SC_IDLE;
			set_attr_svr(&(psched->sch_attr[(int) SCHED_ATR_sched_state]), &sched_attr_def[(int) SCHED_ATR_sched_state], temp);
	}

	if ((psched->sch_attr[(int) SCHED_ATR_sched_priv].at_flags & ATR_VFLAG_SET) == 0) {
			if (psched != dflt_scheduler)
				(void) snprintf(dir_path, MAXPATHLEN, "%s/sched_priv_%s", pbs_conf.pbs_home_path, psched->sc_name);
			else
				(void) snprintf(dir_path, MAXPATHLEN, "%s/sched_priv", pbs_conf.pbs_home_path);
			set_attr_svr(&(psched->sch_attr[(int) SCHED_ATR_sched_priv]), &sched_attr_def[(int) SCHED_ATR_sched_priv],
				dir_path);
	}
	if ((psched->sch_attr[(int) SCHED_ATR_sched_log].at_flags & ATR_VFLAG_SET) == 0) {
			if (psched != dflt_scheduler)
				(void) snprintf(dir_path, MAXPATHLEN, "%s/sched_logs_%s", pbs_conf.pbs_home_path, psched->sc_name);
			else
				(void) snprintf(dir_path, MAXPATHLEN, "%s/sched_logs", pbs_conf.pbs_home_path);
			set_attr_svr(&(psched->sch_attr[(int) SCHED_ATR_sched_log]), &sched_attr_def[(int) SCHED_ATR_sched_log],
				dir_path);
	}
	if ((psched->sch_attr[(int)SCHED_ATR_log_events].at_flags & ATR_VFLAG_SET) == 0) {
		psched->sch_attr[SCHED_ATR_log_events].at_val.at_long = SCHED_LOG_DFLT;
		psched->sch_attr[SCHED_ATR_log_events].at_flags |= ATR_VFLAG_SET | ATR_VFLAG_MODCACHE | ATR_VFLAG_DEFLT;
		flag = 1;
	}

	if (!(psched->sch_attr[SCHED_ATR_preempt_queue_prio].at_flags & ATR_VFLAG_SET)) {
		psched->sch_attr[SCHED_ATR_preempt_queue_prio].at_val.at_long = PBS_PREEMPT_QUEUE_PRIO_DEFAULT;
		psched->sch_attr[SCHED_ATR_preempt_queue_prio].at_flags |= ATR_VFLAG_SET | ATR_VFLAG_MODCACHE | ATR_VFLAG_DEFLT;
		flag = 1;
	}
	if (!(psched->sch_attr[SCHED_ATR_preempt_prio].at_flags & ATR_VFLAG_SET)) {
		psched->sch_attr[SCHED_ATR_preempt_prio].at_val.at_str = strdup(PBS_PREEMPT_PRIO_DEFAULT);
		psched->sch_attr[SCHED_ATR_preempt_prio].at_flags |= ATR_VFLAG_SET | ATR_VFLAG_MODCACHE | ATR_VFLAG_DEFLT;
		flag = 1;
	}
	if (!(psched->sch_attr[SCHED_ATR_preempt_order].at_flags & ATR_VFLAG_SET)) {
		psched->sch_attr[SCHED_ATR_preempt_order].at_val.at_str = strdup(PBS_PREEMPT_ORDER_DEFAULT);
		action_sched_preempt_order(&psched->sch_attr[SCHED_ATR_preempt_order], psched, ATR_ACTION_ALTER);
		psched->sch_attr[SCHED_ATR_preempt_order].at_flags |= ATR_VFLAG_SET | ATR_VFLAG_MODCACHE | ATR_VFLAG_DEFLT;
		flag = 1;
	}
	if (!unset_flag && !from_scheduler && !(psched->sch_attr[SCHED_ATR_preempt_sort].at_flags & ATR_VFLAG_SET)) {
		psched->sch_attr[SCHED_ATR_preempt_sort].at_val.at_str = strdup(PBS_PREEMPT_SORT_DEFAULT);
		psched->sch_attr[SCHED_ATR_preempt_sort].at_flags |= ATR_VFLAG_SET | ATR_VFLAG_MODCACHE | ATR_VFLAG_DEFLT;
		flag = 1;
	}
	if (flag)
		set_scheduler_flag(SCH_ATTRS_CONFIGURE, psched);
}


/**
 * @brief
 * 		action routine for the scheduler's partition attribute
 *
 * @param[in]	pattr	-	pointer to attribute structure
 * @param[in]	pobj	-	not used
 * @param[in]	actmode	-	action mode
 *
 *
 * @return	error code
 * @retval	PBSE_NONE	-	Success
 * @retval	!PBSE_NONE	-	Failure
 *
 */

int
action_sched_partition(attribute *pattr, void *pobj, int actmode)
{
	pbs_sched* psched;
	pbs_sched* pin_sched;
	attribute *part_attr;
	int i;
	int k;
	if (pobj == dflt_scheduler)
		return PBSE_SCHED_OP_NOT_PERMITTED;
	pin_sched = (pbs_sched *) pobj;

	for (i = 0; i < pattr->at_val.at_arst->as_usedptr; ++i) {
		if (pattr->at_val.at_arst->as_string[i] == NULL)
			continue;
		for (psched = (pbs_sched*) GET_NEXT(svr_allscheds); psched; psched = (pbs_sched*) GET_NEXT(psched->sc_link)) {
			if (psched == pobj) {
				continue;
			}
			part_attr = &(psched->sch_attr[SCHED_ATR_partition]);
			if (part_attr->at_flags & ATR_VFLAG_SET) {
				for (k = 0; k < part_attr->at_val.at_arst->as_usedptr; k++) {
					if ((part_attr->at_val.at_arst->as_string[k] != NULL)
							&& (!strcmp(pattr->at_val.at_arst->as_string[i],
									part_attr->at_val.at_arst->as_string[k])))
						return PBSE_SCHED_PARTITION_ALREADY_EXISTS;
				}
			}
		}
	}
	if (actmode != ATR_ACTION_RECOV)
		(void)contact_sched(SCH_ATTRS_CONFIGURE, NULL, pin_sched->pbs_scheduler_addr, pin_sched->pbs_scheduler_port);
	return PBSE_NONE;
}

