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

/**
 * @file	pbs_python_external.c
 * @brief
 *  This file contains shared routines that can be used by any of the PBS
 *  infrastructure daemons (Server,MOM or Scheduler). This file basically
 *  provides all the implementation for external interface routines found
 *  in pbs_python.h
 *
 */

#include <pbs_config.h>

/* --- BEGIN PYTHON DEPENDENCIES --- */

#ifdef PYTHON

#include <pbs_python_private.h> /* private python file  */
#include <eval.h>		/* For PyEval_EvalCode  */
#include <pythonrun.h>		/* For Py_SetPythonHome */
#include <sys/types.h>
#include <sys/stat.h>
#include <signal.h>
#include <unistd.h>
#include <wchar.h>

extern PyObject *PyInit__pbs_ifl(void);

static struct _inittab pbs_python_inittab_modules[] = {
	{PBS_PYTHON_V1_MODULE_EXTENSION_NAME, pbs_v1_module_inittab},
	{"_pbs_ifl", PyInit__pbs_ifl},
	{NULL, NULL} /* sentinel */
};

static PyObject *
_pbs_python_compile_file(const char *file_name,
			 const char *compiled_code_file_name);
extern int pbs_python_setup_namespace_dict(PyObject *globals);

#endif /* PYTHON */

#include <pbs_python.h>

/* --- END PYTHON DEPENDENCIES --- */

/*
 * GLOBAL
 */
/* TODO make it autoconf? */
char *pbs_python_daemon_name;

/*
 * ===================   BEGIN   EXTERNAL ROUTINES  ===================
 */

/**
 *
 * @brief
 *	Start the Python interpreter.
 *
 * @param[in/out] interp_data - has some prefilled information about
 *				the python interpreter to start, like python
 *				daemon name. This will also get filled in
 *				with new information such as status of
 *				of the python start.
 * @note
 *	If  called by pbs_python command, then any log messages are logged as
 *	DEBUG3; otherwise, DEBUG2.
 */

int
pbs_python_ext_start_interpreter(struct python_interpreter_data *interp_data)
{

#ifdef PYTHON /* -- BEGIN ONLY IF PYTHON IS CONFIGURED -- */
	struct stat sbuf;
	char pbs_python_destlib[MAXPATHLEN + 1] = {'\0'};
	char pbs_python_destlib2[MAXPATHLEN + 1] = {'\0'};
	int evtype;
	int rc;

	/*
	 * initialize the convenience global pbs_python_daemon_name, as it is
	 * used everywhere
	 */

	pbs_python_daemon_name = interp_data->daemon_name;

	/* Need to make logging less verbose if pbs_python command */
	/* used, since it can get called many times in a pbs daemon, */
	/* and it would litter that daemon's logs */
	if (IS_PBS_PYTHON_CMD(pbs_python_daemon_name))
		evtype = PBSEVENT_DEBUG3;
	else
		evtype = PBSEVENT_DEBUG2;

	snprintf(pbs_python_destlib, MAXPATHLEN, "%s/lib64/python/altair",
		 pbs_conf.pbs_exec_path);
	snprintf(pbs_python_destlib2, MAXPATHLEN, "%s/lib64/python/altair/pbs/v1",
		 pbs_conf.pbs_exec_path);
	rc = stat(pbs_python_destlib, &sbuf);
	if (rc != 0) {
		snprintf(pbs_python_destlib, MAXPATHLEN, "%s/lib/python/altair",
			 pbs_conf.pbs_exec_path);
		rc = stat(pbs_python_destlib, &sbuf);
		snprintf(pbs_python_destlib2, MAXPATHLEN, "%s/lib/python/altair/pbs/v1",
			 pbs_conf.pbs_exec_path);
	}
	if (rc != 0) {
		log_err(-1, __func__,
			"--> PBS Python library directory not found <--");
		goto ERROR_EXIT;
	}
	if (!S_ISDIR(sbuf.st_mode)) {
		log_err(-1, __func__,
			"--> PBS Python library path is not a directory <--");
		goto ERROR_EXIT;
	}

	if (interp_data) {
		interp_data->init_interpreter_data(interp_data); /* to be safe */
		if (interp_data->interp_started) {
			log_event(evtype, PBS_EVENTCLASS_SERVER,
				  LOG_INFO, interp_data->daemon_name,
				  "--> Python interpreter already started <--");
			goto SUCCESS_EXIT;
		} /* else { we are not started but ready } */
	} else {  /* we need to allocate memory */
		log_err(-1, __func__,
			"--> Passed NULL for interpreter data <--");
		goto ERROR_EXIT;
	}

	Py_NoSiteFlag = 1;
	Py_FrozenFlag = 1;
	Py_OptimizeFlag = 2;	      /* TODO make this a compile flag variable */
	Py_IgnoreEnvironmentFlag = 1; /* ignore PYTHONPATH and PYTHONHOME */

	set_py_progname();

	/* we make sure our top level module is initialized */
	if ((PyImport_ExtendInittab(pbs_python_inittab_modules) != 0)) {
		log_err(-1, "PyImport_ExtendInittab",
			"--> Failed to initialize Python interpreter <--");
		goto ERROR_EXIT;
	}

	/*
	 * arg '1' means to not skip init of signals
	 * we want signals to propagate to the executing
	 * Python script to be able to interrupt it
	 */
	Py_InitializeEx(1);

	if (Py_IsInitialized()) {
		char *msgbuf;

		interp_data->interp_started = 1; /* mark python as initialized */
		/* print only the first five characters, TODO check for NULL? */
		pbs_asprintf(&msgbuf,
			     "--> Python Interpreter started, compiled with version:'%s' <--",
			     Py_GetVersion());
		log_event(evtype, PBS_EVENTCLASS_SERVER,
			  LOG_INFO, interp_data->daemon_name, msgbuf);
		free(msgbuf);
	} else {
		log_err(-1, "Py_InitializeEx",
			"--> Failed to initialize Python interpreter <--");
		goto ERROR_EXIT;
	}
	/*
	 * Add Altair python module directory to sys path. NOTE:
	 *  PBS_PYTHON_MODULE_DIR is a command line define, also insert
	 * standard required python modules
	 */
	if (pbs_python_modify_syspath(pbs_python_destlib, -1) == -1) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "could not insert %s into sys.path shutting down",
			 pbs_python_destlib);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		log_err(-1, __func__, log_buffer);
		goto ERROR_EXIT;
	}

	if (pbs_python_modify_syspath(pbs_python_destlib2, -1) == -1) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "could not insert %s into sys.path shutting down",
			 pbs_python_destlib2);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		log_err(-1, __func__, log_buffer);
		goto ERROR_EXIT;
	}

	/*
	 * At this point it is safe to load the available server types from
	 * the python modules. since the syspath is setup correctly
	 */
	if ((pbs_python_load_python_types(interp_data) == -1)) {
		log_err(-1, __func__, "could not load python types into the interpreter");
		goto ERROR_EXIT;
	}

	interp_data->pbs_python_types_loaded = 1; /* just in case */

#ifdef LIBPYTHONSVR
	PyObject *m, *d, *f, *handler, *sigint;
	m = PyImport_ImportModule("signal");
	if (!m) {
		log_err(-1, __func__, "failed to import the signal module");
		goto ERROR_EXIT;
	}
	d = PyModule_GetDict(m);
	f = PyDict_GetItemString(d, "signal");
	handler = PyDict_GetItemString(d, "default_int_handler");
	sigint = PyDict_GetItemString(d, "SIGINT");
	if (f && PyCallable_Check(f)) {
		if (!PyObject_CallFunctionObjArgs(f, sigint, handler, NULL)) {
			Py_CLEAR(m);
			log_err(-1, __func__, "could not set up signal.default_int_handler");
			goto ERROR_EXIT;
		}
	} else {
		Py_CLEAR(m);
		log_err(-1, __func__, "could not call signal.signal");
		goto ERROR_EXIT;
	}
	Py_CLEAR(m);
	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_SERVER, LOG_INFO, interp_data->daemon_name, "successfully set up signal.default_int_handler");
#endif

SUCCESS_EXIT:
	return 0;
ERROR_EXIT:
	if (interp_data->interp_started) {
		pbs_python_ext_shutdown_interpreter(interp_data);
	}
	return 1;
#else  /* !PYTHON */
	log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN |
			  PBSEVENT_DEBUG,
		  PBS_EVENTCLASS_SERVER,
		  LOG_INFO, "start_python",
		  "--> Python interpreter not built in <--");
	return 0;
#endif /* PYTHON */
}

/**
 *
 * @brief
 *	Shuts down the Python interpreter.
 *
 * @param[in/out] interp_data - has some prefilled information about
 *				the python interpreter to shutdown,
 *				This will also get filled in
 *				with new information such as status of
 *				of the python shutdown.
 * @note
 *	If  called by pbs_python command, then any log messages are logged as
 *	DEBUG3; otherwise, DEBUG2.
 */

void
pbs_python_ext_shutdown_interpreter(struct python_interpreter_data *interp_data)
{
#ifdef PYTHON /* -- BEGIN ONLY IF PYTHON IS CONFIGURED -- */
	int evtype;

	if (IS_PBS_PYTHON_CMD(pbs_python_daemon_name))
		evtype = PBSEVENT_DEBUG3;
	else
		evtype = PBSEVENT_DEBUG2;

	if (interp_data) {
		if (interp_data->interp_started) {
			log_event(evtype, PBS_EVENTCLASS_SERVER,
				  LOG_INFO, interp_data->daemon_name,
				  "--> Stopping Python interpreter <--");

			/* before finalize clear global python objects */
			pbs_python_event_unset(); /* clear Python event object */
			pbs_python_unload_python_types(interp_data);
			Py_Finalize();
		}
		interp_data->destroy_interpreter_data(interp_data);
		/* reset so that we do not have a problem */
		pbs_python_daemon_name = NULL;
	}

#endif /* PYTHON */
}

/**
 * @brief
 * 	pbs_python_ext_quick_start_interpreter - the basic startup without loading
 *	of PBS attributes and resources into Python.
 */

void
pbs_python_ext_quick_start_interpreter(void)
{

#ifdef PYTHON /* -- BEGIN ONLY IF PYTHON IS CONFIGURED -- */
	char pbs_python_destlib[MAXPATHLEN + 1] = {'\0'};
	char pbs_python_destlib2[MAXPATHLEN + 1] = {'\0'};

	snprintf(pbs_python_destlib, MAXPATHLEN, "%s/lib/python/altair",
		 pbs_conf.pbs_exec_path);
	snprintf(pbs_python_destlib2, MAXPATHLEN, "%s/lib/python/altair/pbs/v1",
		 pbs_conf.pbs_exec_path);

	Py_NoSiteFlag = 1;
	Py_FrozenFlag = 1;
	Py_OptimizeFlag = 2;	      /* TODO make this a compile flag variable */
	Py_IgnoreEnvironmentFlag = 1; /* ignore PYTHONPATH and PYTHONHOME */
	set_py_progname();

	/* we make sure our top level module is initialized */
	if ((PyImport_ExtendInittab(pbs_python_inittab_modules) != 0)) {
		log_err(-1, "PyImport_ExtendInittab",
			"--> Failed to initialize Python interpreter <--");
		return;
	}

	Py_InitializeEx(0); /* SKIP initialization of signals */

	if (Py_IsInitialized()) {
		char *msgbuf;

		pbs_asprintf(&msgbuf,
			     "--> Python Interpreter quick started, compiled with version:'%s' <--",
			     Py_GetVersion());
		log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN |
				  PBSEVENT_DEBUG,
			  PBS_EVENTCLASS_SERVER,
			  LOG_INFO, __func__, msgbuf);
		free(msgbuf);
	} else {
		log_err(-1, "Py_InitializeEx",
			"--> Failed to quick initialize Python interpreter <--");
		goto ERROR_EXIT;
	}
	/*
	 * Add Altair python module directory to sys path. NOTE:
	 *  PBS_PYTHON_MODULE_DIR is a command line define, also insert
	 * standard required python modules
	 */
	if (pbs_python_modify_syspath(pbs_python_destlib, -1) == -1) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "could not insert %s into sys.path shutting down",
			 pbs_python_destlib);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		log_err(-1, __func__, log_buffer);
		goto ERROR_EXIT;
	}

	if (pbs_python_modify_syspath(pbs_python_destlib2, -1) == -1) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "could not insert %s into sys.path shutting down",
			 pbs_python_destlib2);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		log_err(-1, __func__, log_buffer);
		goto ERROR_EXIT;
	}

	snprintf(log_buffer, LOG_BUF_SIZE - 1,
		 "--> Inserted Altair PBS Python modules dir '%s' '%s'<--", pbs_python_destlib, pbs_python_destlib2);
	log_buffer[LOG_BUF_SIZE - 1] = '\0';
	log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN |
			  PBSEVENT_DEBUG,
		  PBS_EVENTCLASS_SERVER,
		  LOG_INFO, __func__, log_buffer);

	return;

ERROR_EXIT:
	pbs_python_ext_quick_shutdown_interpreter();
	return;
#else  /* !PYTHON */
	log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN |
			  PBSEVENT_DEBUG,
		  PBS_EVENTCLASS_SERVER,
		  LOG_INFO, "start_python",
		  "--> Python interpreter not built in <--");
	return;
#endif /* PYTHON */
}

/**
 * @brief
 * 	pbs_python_ext_quick_shutdown_interpreter
 */

void
pbs_python_ext_quick_shutdown_interpreter(void)
{
#ifdef PYTHON /* -- BEGIN ONLY IF PYTHON IS CONFIGURED -- */
	log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN |
			  PBSEVENT_DEBUG,
		  PBS_EVENTCLASS_SERVER,
		  LOG_INFO, "pbs_python_ext_quick_shutdown_interpreter",
		  "--> Stopping Python interpreter <--");
	Py_Finalize();
#endif /* PYTHON */
}

void
pbs_python_ext_free_python_script(
	struct python_script *py_script)
{
	if (py_script) {
		if (py_script->path)
			free(py_script->path);

#ifdef PYTHON /* --- BEGIN PYTHON BLOCK --- */
		if (py_script->py_code_obj)
			Py_CLEAR(py_script->py_code_obj);
		if (py_script->global_dict) {
			PyDict_Clear((PyObject *) py_script->global_dict); /* clear k,v */
			Py_CLEAR(py_script->global_dict);
		}
#endif /* --- END   PYTHON BLOCK --- */
	}
	return;
}
#define COPY_STRING(dst, src)                                              \
	do {                                                               \
		if (!((dst) = strdup(src))) {                              \
			log_err(errno, __func__, "could not copy string"); \
			goto ERROR_EXIT;                                   \
		}                                                          \
	} while (0)

int
pbs_python_ext_alloc_python_script(
	const char *script_path,
	struct python_script **py_script /* returned value */
)
{

#ifdef PYTHON /* --- BEGIN PYTHON BLOCK --- */

	struct python_script *tmp_py_script = NULL;
	size_t nbytes = sizeof(struct python_script);
	struct stat sbuf;

	*py_script = NULL; /* init, to be safe */

	if (!(tmp_py_script = (struct python_script *) malloc(nbytes))) {
		log_err(errno, __func__, "failed to malloc struct python_script");
		goto ERROR_EXIT;
	}
	(void) memset(tmp_py_script, 0, nbytes);
	/* check for recompile true by default */
	tmp_py_script->check_for_recompile = 1;

	COPY_STRING(tmp_py_script->path, script_path);
	/* store the stat */
	if ((stat(script_path, &sbuf) == -1)) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "failed to stat <%s>", script_path);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		log_err(errno, __func__, log_buffer);
		goto ERROR_EXIT;
	}
	(void) memcpy(&(tmp_py_script->cur_sbuf), &sbuf,
		      sizeof(tmp_py_script->cur_sbuf));
	/* ok, we are set with py_script */
	*py_script = tmp_py_script;
	return 0;

ERROR_EXIT:
	if (tmp_py_script) {
		pbs_python_ext_free_python_script(tmp_py_script);
		free(tmp_py_script);
	}
	return -1;
#else

	log_err(-1, __func__, "--> Python is disabled <--");
	return -1;
#endif /* --- END   PYTHON BLOCK --- */
}

/**
 * @brief
 * 	Function to create a separate namespace. Essentially a sandbox to run
 * 	python scrips independently.
 *
 * @param[in] interp_data - pointer to interpreter data
 *
 */

void *
pbs_python_ext_namespace_init(
	struct python_interpreter_data *interp_data)
{

#ifdef PYTHON /* --- BEGIN PYTHON BLOCK --- */

	PyObject *namespace_dict = NULL;
	PyObject *py_v1_module = NULL;

	namespace_dict = PyDict_New(); /* New Refrence MUST Decref */
	if (!namespace_dict) {
		pbs_python_write_error_to_log(__func__);
		goto ERROR_EXIT;
	}
	/*
	 * setup our namespace, by including all the modules that are needed to
	 * run the python scripts
	 */
	if ((PyDict_SetItemString(namespace_dict, "__builtins__",
				  PyEval_GetBuiltins()) == -1)) {
		pbs_python_write_error_to_log(__func__);
		goto ERROR_EXIT;
	}

	/*
	 * Now, add our extension object/module to the namespace.
	 */
	py_v1_module = pbs_v1_module_init();
	if (py_v1_module == NULL)
		goto ERROR_EXIT;
	if ((PyDict_SetItemString(namespace_dict,
				  PBS_PYTHON_V1_MODULE_EXTENSION_NAME,
				  py_v1_module) == -1)) {
		Py_XDECREF(py_v1_module);
		snprintf(log_buffer, LOG_BUF_SIZE - 1, "%s|adding extension object",
			 __func__);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		pbs_python_write_error_to_log(__func__);
		goto ERROR_EXIT;
	}

	Py_XDECREF(py_v1_module);

	return namespace_dict;

ERROR_EXIT:
	if (namespace_dict) {
		PyDict_Clear(namespace_dict);
		Py_CLEAR(namespace_dict);
	}
	return namespace_dict;

#else  /* !PYTHON */
	return NULL;
#endif /* --- END   PYTHON BLOCK --- */
}

/**
 *
 * @brief
 *	Checks if hook script needs recompilation.
 *
 * @param[in] interp_data - data to the python interpreter that will interpret
 *				the script.
 * @return	int
 * @retval	-2 	script  compilation failed
 * @retval	-1 	other failures
 * @retval	0 	success
 *
 * @note
 *	If  called by pbs_python command, then any log messages are logged as
 *	DEBUG3; otherwise, DEBUG2.
 */
int
pbs_python_check_and_compile_script(struct python_interpreter_data *interp_data,
				    struct python_script *py_script)
{

#ifdef PYTHON		  /* -- BEGIN ONLY IF PYTHON IS CONFIGURED -- */
	struct stat nbuf; /* new stat buf */
	struct stat obuf; /* old buf */
	int recompile = 1;

	if (!interp_data || !py_script) {
		log_err(-1, __func__, "Either interp_data or py_script is NULL");
		return -1;
	}

	/* ok, first time go straight to compile */
	do {
		if (!py_script->py_code_obj)
			break;
		(void) memcpy(&obuf, &(py_script->cur_sbuf), sizeof(obuf));
		if (py_script->check_for_recompile) {
			if ((stat(py_script->path, &nbuf) != 1) &&
			    (nbuf.st_ino == obuf.st_ino) &&
			    (nbuf.st_size == obuf.st_size) &&
			    (nbuf.st_mtime == obuf.st_mtime)) {
				recompile = 0;
			} else {
				recompile = 1;
				(void) memcpy(&(py_script->cur_sbuf), &nbuf,
					      sizeof(py_script->cur_sbuf));
				Py_CLEAR(py_script->py_code_obj); /* we are rebuilding */
			}
		}
	} while (0);

	if (recompile) {
		snprintf(log_buffer, LOG_BUF_SIZE,
			 "Compiling script file: <%s>", py_script->path);

		if (IS_PBS_PYTHON_CMD(pbs_python_daemon_name))
			log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SERVER,
				  LOG_INFO, interp_data->daemon_name, log_buffer);
		else
			log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN |
					  PBSEVENT_DEBUG,
				  PBS_EVENTCLASS_SERVER,
				  LOG_INFO, interp_data->daemon_name, log_buffer);

		if (!(py_script->py_code_obj =
			      _pbs_python_compile_file(py_script->path,
						       "<embedded code object>"))) {
			pbs_python_write_error_to_log("Failed to compile script");
			return -2;
		}
	}

	/* set dict to null during compilation, clearing previous global/local */
	/* dictionary to prevent leaks.                                        */
	if (py_script->global_dict) {
		PyDict_Clear((PyObject *) py_script->global_dict);
		Py_CLEAR(py_script->global_dict);
	}

	return 0;
#else  /* !PYTHON */
	return -1;
#endif /* PYTHON */
}

/**
 * @brief
 *	runs python script in namespace.
 *
 * @param[in] interp_data - pointer to interpreter data
 * @param[in] py_script - pointer to python script info
 * @param[out] exit_code - exit code
 *
 * @return	int
 * @retval	-3 	script executed but got KeyboardInterrupt
 * @retval	-2 	script  compiled or executed with error
 * @retval	-1 	other failures
 * @retval	0 	success
 */
int
pbs_python_run_code_in_namespace(struct python_interpreter_data *interp_data,
				 struct python_script *py_script,
				 int *exit_code)
{

#ifdef PYTHON /* -- BEGIN ONLY IF PYTHON IS CONFIGURED -- */

	PyObject *pdict;
	struct stat nbuf; /* new stat buf */
	struct stat obuf; /* old buf */
	int recompile = 1;
	PyObject *ptype;
	PyObject *pvalue;
	PyObject *ptraceback;
	PyObject *pobjStr;
	PyObject *retval;
	const char *pStr;
	int rc = 0;
	pid_t orig_pid;

	if (!interp_data || !py_script) {
		log_err(-1, __func__, "Either interp_data or py_script is NULL");
		return -1;
	}

	/* ok, first time go straight to compile */
	do {
		if (!py_script->py_code_obj)
			break;
		(void) memcpy(&obuf, &(py_script->cur_sbuf), sizeof(obuf));
		if (py_script->check_for_recompile) {
			if ((stat(py_script->path, &nbuf) != -1) &&
			    (nbuf.st_ino == obuf.st_ino) &&
			    (nbuf.st_size == obuf.st_size) &&
			    (nbuf.st_mtime == obuf.st_mtime)) {
				recompile = 0;
			} else {
				recompile = 1;
				(void) memcpy(&(py_script->cur_sbuf), &nbuf,
					      sizeof(py_script->cur_sbuf));
				Py_CLEAR(py_script->py_code_obj); /* we are rebuilding */
			}
		}
	} while (0);

	if (recompile) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "Compiling script file: <%s>", py_script->path);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		if (IS_PBS_PYTHON_CMD(pbs_python_daemon_name))
			log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SERVER,
				  LOG_INFO, interp_data->daemon_name, log_buffer);
		else
			log_event(PBSEVENT_SYSTEM | PBSEVENT_ADMIN |
					  PBSEVENT_DEBUG,
				  PBS_EVENTCLASS_SERVER,
				  LOG_INFO, interp_data->daemon_name, log_buffer);

		if (!(py_script->py_code_obj =
			      _pbs_python_compile_file(py_script->path,
						       "<embedded code object>"))) {
			pbs_python_write_error_to_log("Failed to compile script");
			return -2;
		}
	}

	/* make new namespace dictionary, NOTE new reference */

	if (!(pdict = (PyObject *) pbs_python_ext_namespace_init(interp_data))) {
		log_err(-1, __func__, "while calling pbs_python_ext_namespace_init");
		return -1;
	}
	if ((pbs_python_setup_namespace_dict(pdict) == -1)) {
		Py_CLEAR(pdict);
		return -1;
	}

	/* clear previous global/local dictionary */
	if (py_script->global_dict) {
		PyDict_Clear((PyObject *) py_script->global_dict); /* clear k,v */
		Py_CLEAR(py_script->global_dict);
	}

	py_script->global_dict = pdict;

	orig_pid = getpid();

	PyErr_Clear(); /* clear any exceptions before starting code */
	/* precompile strings of code to bytecode objects */
	retval = PyEval_EvalCode((PyObject *) py_script->py_code_obj,
				 pdict, pdict);

	/* check for a fork of the hook, terminate fork immediately */
	if (orig_pid != getpid())
		exit(0);

	/* check for exception */
	if (PyErr_Occurred()) {
		if (PyErr_ExceptionMatches(PyExc_KeyboardInterrupt)) {
			pbs_python_write_error_to_log("Python script received a KeyboardInterrupt");
			Py_XDECREF(retval);
			return -3;
		}

		if (PyErr_ExceptionMatches(PyExc_SystemExit)) {
			PyErr_Fetch(&ptype, &pvalue, &ptraceback);
			PyErr_Clear(); /* just in case, not clear from API doc */

			if (pvalue) {
				pobjStr = PyObject_Str(pvalue); /* new ref */
				pStr = PyUnicode_AsUTF8(pobjStr);
				rc = (int) atol(pStr);
				Py_XDECREF(pobjStr);
			}

			Py_XDECREF(ptype);
			Py_XDECREF(pvalue);

#if !defined(WIN32)
			Py_XDECREF(ptraceback);
#elif !defined(_DEBUG)
			/* for some reason this crashes on Windows Debug version */
			Py_XDECREF(ptraceback);
#endif

		} else {
			pbs_python_write_error_to_log("Error evaluating Python script");
			Py_XDECREF(retval);
			return -2;
		}
	}
	PyErr_Clear();
	Py_XDECREF(retval);

	if (exit_code)
		*exit_code = rc; /* set exit code if var is not null */

	return 0;
#else  /* !PYTHON */
	return -1;
#endif /* PYTHON */
}

#ifdef PYTHON /*  === BEGIN ALL FUNCTIONS REQUIRING PYTHON HEADERS === */

/**
 * @brief
 *	only compile the python script.
 *
 * @param[in]	file_name - abs file name
 * @param[out]  compiled_code_file_name - compiled file
 *
 * @return	object
 * @retval
 * @retval	error code	error
 *
 */
static PyObject *
_pbs_python_compile_file(const char *file_name,
			 const char *compiled_code_file_name)
{
	FILE *fp = NULL;

	long len = 0;
	size_t file_sz = 0;	  /* script file no. of bytes */
	char *file_buffer = NULL; /* buffer to hold the python script file */
	char *cp = NULL;	  /* useful character pointer */
	PyObject *rv = NULL;

	fp = fopen(file_name, "rb");
	if (!fp) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "could not open file <%s>: %s\n", file_name, strerror(errno));
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		log_err(errno, __func__, log_buffer);
		goto ERROR_EXIT;
	}

	if ((fseek(fp, 0L, SEEK_END) == 0)) { /* ok we reached the end */
		len = ftell(fp);
		if (len == -1) {
			snprintf(log_buffer, LOG_BUF_SIZE - 1,
				 "could not determine the file length: %s\n", strerror(errno));
			log_buffer[LOG_BUF_SIZE - 1] = '\0';
			log_err(errno, __func__, log_buffer);
			goto ERROR_EXIT;
		}
		if ((fseek(fp, 0L, SEEK_SET) == -1)) {
			snprintf(log_buffer, LOG_BUF_SIZE - 1,
				 "could not fseek to beginning: %s\n", strerror(errno));
			log_buffer[LOG_BUF_SIZE - 1] = '\0';
			log_err(errno, __func__, log_buffer);
			goto ERROR_EXIT;
		}
		file_sz = len; /* ok good we have a file size */
	} else {	       /* Uh-oh bad news */
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "could not fseek to end: %s\n", strerror(errno));
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		log_err(errno, __func__, log_buffer);
		goto ERROR_EXIT;
	}
	/* allocate memory for file + \n\0 */
	file_sz += 2;

	if (!(file_buffer = (char *) PyMem_Malloc(sizeof(char) * file_sz))) {
		/* could not allocate memory */
		pbs_python_write_error_to_log(__func__);
		goto ERROR_EXIT;
	}

	/* read the file, clean up the file for DOS \r stuff */
	file_sz = fread(file_buffer, sizeof(char), (file_sz - 2), fp);

	file_buffer[file_sz] = '\n';
	file_buffer[file_sz + 1] = '\0';

	if (*file_buffer == '\r')
		*file_buffer = ' ';
	/* TODO handle \r in string constants? */
	for (cp = file_buffer + 1; *cp != '\0'; cp++) {
		if (*cp == '\r') {
			if (*(cp - 1) == '\\') {
				*(cp - 1) = ' ';
				*cp = '\\';
			} else {
				*cp = ' ';
			}
		}
	}

	fclose(fp);
	/* compile the string to a code object,NEW reference caller must DECREF */
	rv = Py_CompileString(file_buffer, compiled_code_file_name, Py_file_input);
	PyMem_Free(file_buffer);
	return rv;

ERROR_EXIT:
	if (fp)
		fclose(fp);
	if (file_buffer)
		PyMem_Free(file_buffer); /* to be safe */
	return rv;
}

#endif /* PYTHON */
