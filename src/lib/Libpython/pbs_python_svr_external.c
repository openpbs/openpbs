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


/**
 * @file	pbs_python_svr_external.c
 * @brief
 * This file should contain interface implementation interacting with the
 * Core PBS Server. So *no* MOM and SCHED dependency should be in this file.
 *
 * @par	library:
 *   libpbspython_svr.a
 */

#include <pbs_config.h>

#ifdef PYTHON
#include <Python.h>
#endif

#include <pbs_python.h>
#include <server_limits.h>
#include "pbs_ifl.h"	/* picks up the extern decl for pbs_config */
#include "resource.h"
#include "pbs_share.h"
#include "pbs_error.h"

extern struct server server;

/* Functions */
#ifdef PYTHON
extern void _pbs_python_set_mode(int mode);

extern int _pbs_python_event_mark_readonly(void);

extern int _pbs_python_event_set(unsigned int hook_event, char *req_user,
	char *req_host, hook_input_param_t *req_params, char *perf_label);

extern void _pbs_python_event_unset(void);

extern int _pbs_python_event_to_request(unsigned int hook_event, hook_output_param_t *req_params, char *perf_label, char *perf_action);

extern int _pbs_python_event_set_attrval(char *name, char *value);

extern char * _pbs_python_event_get_attrval(char *name);

extern void _pbs_python_event_accept(void);

extern void _pbs_python_event_reject(char *msg);

extern char * _pbs_python_event_get_reject_msg(void);

extern int _pbs_python_event_get_accept_flag(void);

extern void _pbs_python_event_param_mod_allow(void);

extern void _pbs_python_event_param_mod_disallow(void);

extern int _pbs_python_event_param_get_mod_flag(void);

extern char *
_pbs_python_event_job_getval_hookset(char *attrib_name, char *opval,
	int opval_len, char *delval, int delval_len);

extern char *
_pbs_python_event_job_getval(char *attrib_name);

extern char *
_pbs_python_event_jobresc_getval_hookset(char *attrib_name, char *resc_name);

extern int
_pbs_python_event_jobresc_clear_hookset(char *attrib_name);

extern char *
_pbs_python_event_jobresc_getval(char *attrib_name, char *resc_name);

extern int _pbs_python_has_vnode_set(void);

extern void _pbs_python_do_vnode_set(void);

extern char *pbs_python_object_str(PyObject *);

#endif /* PYTHON */


/* GLOBAL vars */
extern char *msg_daemonname; /* pbsd_main.c for SERVER */

/*
 * Helper functions involving the PBS Server daemon
 */

/**
 * @brief
 * 	python initiliaze interpreter data
 *
 * @param[in] interp_data - pointer to python interpreter data
 *
 */
void
pbs_python_svr_initialize_interpreter_data(struct python_interpreter_data *interp_data) {
	/* check whether we are already initialized */
	if (interp_data->data_initialized)
		return ;

	interp_data->daemon_name = msg_daemonname;
	interp_data->interp_started = 0;
	interp_data->data_initialized = 1;
	interp_data->pbs_python_types_loaded = 0;
	return ;
}

/**
 * @brief
 *      python destroy interpreter data
 *
 * @param[in] interp_data - pointer to python interpreter data
 *
 */
void
pbs_python_svr_destroy_interpreter_data(struct python_interpreter_data *interp_data)
{
	/* nothing to do or free data */
	interp_data->data_initialized = 0;
	interp_data->interp_started = 0;
	interp_data->pbs_python_types_loaded = 0;
	return ;
}


/*
 * Helper functions related to PBS events
 */

/**
 * @brief
 * 	Sets the "operation" mode of Python: if 'mode' is PY_MODE, then we're
 * 	inside the hook script; if 'mode' is C_MODE, then we're inside some
 * 	internal C helper function.
 * 	Setting 'mode' to C_MODE usually means we don't have any restriction
 * 	as to which attributes we can or cannot set.
 *
 * @param[in] mode - value to indicate which attr val can be set
 *
 */
void
pbs_python_set_mode(int mode)
{

#ifdef PYTHON
	_pbs_python_set_mode(mode);
#endif

}

/**
 * @brief
 * 	Makes the Python PBS event object read-only, meaning none of its
 * 	could be modified in a hook script.
 *
 * @return	int
 * @retval	0 	for success
 * @retval	-1 	otherwise
 */
int
pbs_python_event_mark_readonly(void)
{

#ifdef PYTHON
	return (_pbs_python_event_mark_readonly());
#else
	return (0);
#endif
}


/**
 *
 * @brief
 *	This creates a PBS Python event object representing 'hook_event' with
 * request parameter 'req_params' and requested by:
 * 'req_user'@'req_host'.
 *
 * @param[in]	hook_event - the event represented
 * @param[in]	req_user - who requested the hook event
 * @param[in]	req_host - where the request came from
 * @param[in]	req_params - array of input parameters
 * @param[in]	perf_label - passed on to hook_perf_stat* call.
 *
 * @return int
 * @retval 0	- success
 * @retval -1	- error
 *
 */
int
pbs_python_event_set(unsigned int hook_event, char *req_user,
	char *req_host, hook_input_param_t *req_params,
	char *perf_label)
{
#ifdef PYTHON
	int rc;
	rc = _pbs_python_event_set(hook_event, req_user, req_host, req_params, perf_label);

	if (rc == -2) { /* _pbs_python_event_set got interrupted, retry */
		log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_SERVER, LOG_DEBUG,
			"_pbs_python_event_set", "retrying call");
		rc = _pbs_python_event_set(hook_event, req_user, req_host,
			req_params, perf_label);
	}
	return (rc);
#else
	return (0);
#endif

}

/**
 * @brief
 * 	This discards the Python event object if set, hopefully freeing up any
 * 	memory allocated to it.
 */
void
pbs_python_event_unset(void)
{
#ifdef PYTHON
	_pbs_python_event_unset();
#endif

}

/**
 *
 * @brief
 * 	Recreates 'req_params' (request structures,
 *	ex. rq_queuejob, rq_manage, rq_move) consulting the parameter values
 *	obtained from current
 * 	PBS Python event object representing 'hook_event'.
 *
 * @param[in]	hook_event - the event represented
 * @param[in]	req_params - array of input parameters
 * @param[in]	perf_label - passed on to hook_perf_stat* call.
 * @param[in]	perf_action - passed on to hook_perf_stat* call.
 *
 * @return int
 * @retval 0	- success
 * @retval -1	- error
 *
 * @note
 *		This function calls a single hook_perf_stat_start()
 *		that has some malloc-ed data that are freed in the
 *		hook_perf_stat_end() call, which is done at the end of
 *		this function.
 *		Ensure that after the hook_perf_stat_start(), all
 *		program execution path lead to hook_perf_stat_stop()
 *		call.
 */
int
pbs_python_event_to_request(unsigned int hook_event, hook_output_param_t *req_params, char *perf_label, char *perf_action)
{

#ifdef PYTHON
	return (_pbs_python_event_to_request(hook_event, req_params, perf_label, perf_action));
#else
	return (0);
#endif
}

char *
pbs_python_event_job_getval_hookset(char *attrib_name, char *opval,
	int opval_len, char *delval, int delval_len) {
#ifdef PYTHON
	return (_pbs_python_event_job_getval_hookset(attrib_name, opval,
		opval_len, delval, delval_len));
#else
	return (0);
#endif
}

/**
 *
 * @brief
 *	Wrapper function to _pbs_python_event_job_getval().
 *
 * @param[in]	attrib_name - parameter passed to the function
 *				'_pbs_python_event_job_getval()'.
 */
char *
pbs_python_event_job_getval(char *attrib_name)
{
#ifdef PYTHON
	return (_pbs_python_event_job_getval(attrib_name));
#else
	return NULL;
#endif
}

/**
 *
 * @brief
 *	Wrapper function to _pbs_python_event_jobresc_getval_hookset().
 *
 * @param[in]	attrib_name - parameter passed to the function
 *				'_pbs_python_event_jobresc_getval_hookset()'.
 * @param[in]	resc_name - parameter passed to the function
 *				'_pbs_python_event_jobresc_getval_hookset()'.
 */
char *
pbs_python_event_jobresc_getval_hookset(char *attrib_name, char *resc_name)
{
#ifdef PYTHON
	return (_pbs_python_event_jobresc_getval_hookset(attrib_name, resc_name));
#else
	return NULL;
#endif
}

/**
 *
 * @brief
 *	Wrapper function to _pbs_python_event_jobresc_clear_hookset().
 *
 * @param[in]	attrib_name - parameter passed to the function
 *				'_pbs_python_event_jobresc_clear_hookset()'.
 */
int
pbs_python_event_jobresc_clear_hookset(char *attrib_name)
{
#ifdef PYTHON
	return (_pbs_python_event_jobresc_clear_hookset(attrib_name));
#else
	return (0);
#endif
}

/**
 *
 * @brief
 *	Wrapper function to _pbs_python_event_jobresc_getval().
 *
 * @param[in]	attrib_name - parameter passed to the function
 *				'_pbs_python_event_jobresc_getval()'.
 * @param[in]	resc_name - parameter passed to the function
 *				'_pbs_python_event_jobresc_getval()'.
 */
char *
pbs_python_event_jobresc_getval(char *attrib_name, char *resc_name)
{
#ifdef PYTHON
	return (_pbs_python_event_jobresc_getval(attrib_name, resc_name));
#else
	return NULL;
#endif
}

/**
 * @brief
 * 	Sets the value of the attribute 'name' of the current Python Object event
 * 	to a string 'value'. The descriptor for the attribute will take care of
 * 	converting to an actual type.
 *
 * @param[out] name - attr name
 * @param[in] value - value for attribute name
 *
 * @return	int
 * @retval	0 	for success
 * @retval	-1  	for error.
 */
int
pbs_python_event_set_attrval(char *name, char *value)
{

#ifdef PYTHON
	return (_pbs_python_event_set_attrval(name, value));
#else
	return (0);
#endif
}

/**
 * @brief
 * 	Gets the value of the attribute 'name' of the current Python Object event
 * 	as a string. Returns NULL if it doesn't find one.
 */
char *
pbs_python_event_get_attrval(char *name)
{

#ifdef PYTHON
	return (_pbs_python_event_get_attrval(name));
#else
	return NULL;
#endif
}

/**
 * @brief
 *  	Allows the current PBS event request to proceed.
 */
void
pbs_python_event_accept(void)
{

#ifdef PYTHON
	_pbs_python_event_accept();
#endif

}

/**
 * @brief
 *  	Reject the current PBS event request.
 */
void
pbs_python_event_reject(char *msg)
{

#ifdef PYTHON
	_pbs_python_event_reject(msg);
#endif
}

/**
 * @brief
 * 	Returns the message string supplied in the hook script when it rejected
 * 	an event request.
 */
char *
pbs_python_event_get_reject_msg(void)
{

#ifdef PYTHON
	return (_pbs_python_event_get_reject_msg());
#else
	return NULL;
#endif
}


/**
 * @brief
 * 	Returns the value of the event accept flag (1 for TRUE or 0 for FALSE).
 */
int
pbs_python_event_get_accept_flag(void)
{

#ifdef PYTHON
	return (_pbs_python_event_get_accept_flag());
#else
	return (0);	/* for FALSE */
#endif

}

/**
 * @brief
 * 	Sets a global flag that says modifications to the PBS Python
 * 	attributes are allowed.
 */
void
pbs_python_event_param_mod_allow(void)
{

#ifdef PYTHON
	_pbs_python_event_param_mod_allow();
#endif

}

/**
 * @brief
 * 	Sets a global flag that says any more modifications to the PBS Python
 * 	attributes would be disallowed.
 */
void
pbs_python_event_param_mod_disallow(void)
{

#ifdef PYTHON
	_pbs_python_event_param_mod_disallow();
#endif

}

/**
 * @brief
 * 	Returns the value (0 or 1) of the global flag that says whether or not
 * 	modifications to the PBS Python attributes are allowed.
 */
int
pbs_python_event_param_get_mod_flag(void)
{

#ifdef PYTHON
	return (_pbs_python_event_param_get_mod_flag());
#else
	return (0);	/* for FALSE */
#endif

}

/*
 *
 * @brief
 *	Checks if there's at least one pending "set" vnode operation
 *	that needs to be performed by PBS.
 * @par
 *	See called function itself for details.
 *
 * @return int
 * @retval 1	- if a "set" operation was found.
 * @retval 0   - if not found.
 *
 */
int
pbs_python_has_vnode_set(void)
{

#ifdef PYTHON
	return (_pbs_python_has_vnode_set());
#else
	return (0);	/* for FALSE */
#endif

}

/**
 * @brief
 *	Perform all the "set" vnode operations to be performed by PBS.
 * @par
 *	See called function itself for details.
 */
void
pbs_python_do_vnode_set(void)
{

#ifdef PYTHON
	_pbs_python_do_vnode_set();
#endif
}


/**
 * @brief
 * 	validate_job_formula - validate that the sorting forumla is in the
 *	correct form.  We do this by calling python and having
 *	it catch exceptions.
 *
 */
int validate_job_formula(attribute *pattr, void *pobject, int actmode) {
	char *formula;
	char *errmsg = NULL;
	struct resource_def *pres;
	FILE *fp;
	char buf[1024];
	char pathbuf[MAXPATHLEN];
	char *globals1 = NULL;
	int globals_size1 = 1024;
	char *globals2 = NULL;
	int globals_size2 = 1024;
	char *script = NULL;
	int script_size = 2048;
	PyThreadState *ts_main = NULL;
	PyThreadState *ts_sub = NULL;
	int rc = 0;
	int err = 0;

	if (actmode == ATR_ACTION_FREE)
		return (0);

#ifndef PYTHON
	return PBSE_INTERNAL;
#else
	if (!Py_IsInitialized())
		return PBSE_INTERNAL;

	formula = pattr->at_val.at_str;
	if (formula == NULL)
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
		snprintf(pathbuf, sizeof(pathbuf), "%s/%s", pbs_conf.pbs_home_path,
			FORMULA_ATTR_PATH_SCHED);
		if ((fp = fopen(pathbuf, "w")) == NULL) {
			rc = PBSE_SYSTEM;
			goto validate_job_formula_exit;
		}

		fprintf(fp, "### PBS INTERNAL FILE DO NOT MODIFY ###\n");
		fprintf(fp, "%s\n", formula);

		fclose(fp);
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
 * 	pbs_python_set_interrupt - wrapper to PyErr_SetInterrupt()
 *
 */

void
pbs_python_set_interrupt(void)
{

#ifdef PYTHON
	PyErr_SetInterrupt();
#endif
}

/**
 *  @brief
 *  	Initializes all the elements of hook_input_param_t structure.
 *
 *  @param[in/out]	hook_input - the structure to initialize.
 *
 *  @return void
 */

void
hook_input_param_init(hook_input_param_t *hook_input)
{

	hook_input->rq_job = NULL;
	hook_input->rq_manage = NULL;
	hook_input->rq_move = NULL;
	hook_input->rq_prov = NULL;
	hook_input->rq_run = NULL;
	hook_input->progname = NULL;
	hook_input->argv_list = NULL;
	hook_input->env = NULL;
	hook_input->jobs_list = NULL;
	hook_input->vns_list = NULL;
	hook_input->resv_list = NULL;
	hook_input->vns_list_fail = NULL;
}

/**
 *  @brief
 *  	Initializes all the elements of hook_output_param_t structure.
 *
 *  @param[in/out]	hook_output - the structure to initialize.
 *
 *  @return void
 */
void
hook_output_param_init(hook_output_param_t *hook_output)
{
	hook_output->rq_job = NULL;
	hook_output->rq_manage = NULL;
	hook_output->rq_move = NULL;
	hook_output->rq_prov = NULL;
	hook_output->rq_run = NULL;
	hook_output->progname = NULL;
	hook_output->argv_list = NULL;
	hook_output->env = NULL;
	hook_output->jobs_list = NULL;
	hook_output->vns_list = NULL;
	hook_output->resv_list = NULL;
	hook_output->vns_list_fail = NULL;
}
