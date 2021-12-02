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
#include <pbs_python_private.h> /* include the internal python file */
#include <log.h>
#include <pbs_error.h>
#include "hook.h"

extern char *pbs_python_daemon_name;
/**
 * @file	common_python_utils.c
 * @brief
 * 	Common Python Utilities shared by extension and embedded C routines.
 */

/**
 *
 * @brief
 *	write python object info to log in the form of:
 *	<object info> [<pre message>]
 *
 * @param[in]	obj	- the Python object to write info about.
 * @param[in]	pre	- some header string to put in the log
 * @param[in]	severity - severity level of the log message
 *
 * @return	none
 *
 * @note
 *  side effects:
 *   No python exceptions are generated, if they do, it is cleared.
 */

void
pbs_python_write_object_to_log(PyObject *obj, char *pre, int severity)
{
	PyObject *py_tmp_str = NULL;
	const char *obj_str = NULL;

	if (!(py_tmp_str = PyObject_Str(obj))) {
		goto ERROR_EXIT;
	}
	if (!(obj_str = PyUnicode_AsUTF8(py_tmp_str))) {
		goto ERROR_EXIT;
	}
	if (pre) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1, "%s %s", pre, obj_str);
	} else {
		snprintf(log_buffer, LOG_BUF_SIZE - 1, "%s", obj_str);
	}
	log_buffer[LOG_BUF_SIZE - 1] = '\0';

	if (IS_PBS_PYTHON_CMD(pbs_python_daemon_name))
		log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SERVER,
			  severity, pbs_python_daemon_name, log_buffer);
	else
		log_event(PBSEVENT_DEBUG2, PBS_EVENTCLASS_SERVER,
			  severity, pbs_python_daemon_name, log_buffer);

	Py_CLEAR(py_tmp_str);
	return;

ERROR_EXIT:
	Py_CLEAR(py_tmp_str);
	pbs_python_write_error_to_log("failed to convert object to str");
}

/**
 * @brief
 * 	insert directory to sys path list
 * 	if pos == -1 , then append to the end of the list.
 *
 * @param[in] dirname - directory path
 * @param[in] pos - position of python list
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	error
 *
 */
int
pbs_python_modify_syspath(const char *dirname, int pos)
{
	PyObject *path = NULL; /* 'sys.path'  */
	PyObject *pystr_dirname = NULL;

	if (!dirname) {
		log_err(PBSE_INTERNAL, __func__, "passed NULL pointer to dirname argument!!");
		return -1;
	}

	PyErr_Clear(); /* clear any exceptions */

	/* if sucess we ger a NEW ref */
	if (!(pystr_dirname = PyUnicode_FromString(dirname))) { /* failed */
		snprintf(log_buffer, LOG_BUF_SIZE - 1, "%s:creating pystr_dirname <%s>",
			 __func__, dirname);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		pbs_python_write_error_to_log(log_buffer);
		goto ERROR_EXIT;
	}

	/* if sucess we ger a NEW ref */
	if (!(path = PySys_GetObject("path"))) { /* failed */
		snprintf(log_buffer, LOG_BUF_SIZE - 1, "%s:PySys_GetObject failed",
			 __func__);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		pbs_python_write_error_to_log(log_buffer);
		goto ERROR_EXIT;
	}

	if (PyList_Check(path)) {
		if (pos == -1) {
			if (PyList_Append(path, pystr_dirname) == -1) {
				snprintf(log_buffer, LOG_BUF_SIZE - 1,
#ifdef NAS /* localmod 005 */
					 "%s:could not append to list pos:<%ld>",
					 __func__, (long) pos
#else
					 "%s:could not append to list pos:<%d>",
					 __func__, pos
#endif /* localmod 005 */
				);
				log_buffer[LOG_BUF_SIZE - 1] = '\0';
				pbs_python_write_error_to_log(log_buffer);
				goto ERROR_EXIT;
			}
		} else {
			if (PyList_Insert(path, pos, pystr_dirname) == -1) {
				snprintf(log_buffer, LOG_BUF_SIZE - 1,
#ifdef NAS /* localmod 005 */
					 "%s:could not append to list pos:<%ld>",
					 __func__, (long) pos
#else
					 "%s:could not append to list pos:<%d>",
					 __func__, pos
#endif /* localmod 005 */
				);
				log_buffer[LOG_BUF_SIZE - 1] = '\0';
				pbs_python_write_error_to_log(log_buffer);
				goto ERROR_EXIT;
			}
		}
	} else {
		log_err(PBSE_INTERNAL, __func__, "sys.path is not a list?");
		goto ERROR_EXIT;
	}

	{
		PyObject *obj_repr;
		char *str;
		obj_repr = PyObject_Repr(path);
		str = pbs_python_object_str(obj_repr);
		snprintf(log_buffer, LOG_BUF_SIZE - 1, "--> Python module path is now: %s <--", str);
		log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SERVER,
			  LOG_DEBUG, pbs_python_daemon_name, log_buffer);
		Py_CLEAR(obj_repr);
	}

	Py_CLEAR(pystr_dirname);
	PySys_SetObject("path", path);
	return 0;

ERROR_EXIT:
	Py_CLEAR(pystr_dirname);
	return -1;
}

/**
 * @brief
 * 	pbs_python_write_error_to_log
 *    	write python exception occurred to PBS log file.
 *    	Heavily borrowed from "Programming Python" by Mark Lutz
 *
 * @param[in] emsg - error msg to be logged
 *
 */

void
pbs_python_write_error_to_log(const char *emsg)
{
	PyObject *exc_type = NULL;	/* NEW refrence, please DECREF */
	PyObject *exc_value = NULL;	/* NEW refrence, please DECREF */
	PyObject *exc_traceback = NULL; /* NEW refrence, please DECREF */
	PyObject *exc_string = NULL;	/* the exception message to be written to pbs log */

	/* get the exception */
	if (!PyErr_Occurred()) {
		log_err(PBSE_INTERNAL, __func__, "error handler called but no exception raised!");
		return;
	}

	PyErr_Fetch(&exc_type, &exc_value, &exc_traceback);
	PyErr_Clear(); /* just in case, not clear from API doc */

	exc_string = NULL;
	if ((exc_type != NULL) && /* get the string representation of the object */
	    ((exc_string = PyObject_Str(exc_type)) != NULL) &&
	    (PyUnicode_Check(exc_string))) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1, "%s", PyUnicode_AsUTF8(exc_string));
	} else {
		snprintf(log_buffer, LOG_BUF_SIZE - 1, "%s", "<could not figure out the exception type>");
	}
	log_buffer[LOG_BUF_SIZE - 1] = '\0';
	Py_XDECREF(exc_string);
	if (log_buffer[0] != '\0')
		log_err(PBSE_INTERNAL, emsg, log_buffer);

	/* Log error exception value */
	exc_string = NULL;
	if ((exc_value != NULL) && /* get the string representation of the object */
	    ((exc_string = PyObject_Str(exc_value)) != NULL) &&
	    (PyUnicode_Check(exc_string))) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1, "%s", PyUnicode_AsUTF8(exc_string));
	} else {
		snprintf(log_buffer, LOG_BUF_SIZE - 1, "%s", "<could not figure out the exception value>");
	}
	log_buffer[LOG_BUF_SIZE - 1] = '\0';
	Py_XDECREF(exc_string);
	if (log_buffer[0] != '\0')
		log_err(PBSE_INTERNAL, emsg, log_buffer);

	Py_XDECREF(exc_type);
	Py_XDECREF(exc_value);

#if !defined(WIN32)
	Py_XDECREF(exc_traceback);
#elif !defined(_DEBUG)
	/* for some reason this crashes on Windows Debug version */
	Py_XDECREF(exc_traceback);
#endif

	return;
}

/**
 * @brief
 * 	pbs_python_object_set_attr_string_value
 *    	Current PBS API does not have an easy interface to set a C string value to a
 *    	a object attribute. Hence, a lot of boilerplate code is needed to just set a string
 *   	value, hence this routine.
 *
 * @param[in] obj - object attribute to which string value to be set
 * @param[in] key - name of the attribute to set
 * @param[in] value - string value to be set
 *
 * @par	NOTES:
 *  	- exceptions are cleared!!
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	failure
 *
 */

int
pbs_python_object_set_attr_string_value(PyObject *obj,
					const char *key,
					const char *value)
{
	PyObject *tmp_py_str = NULL;

	int rv = -1; /* default failure */

	if (!key) {
		log_err(PBSE_INTERNAL, __func__, "Null key passed!");
		return rv;
	}

	if (!value) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "Null value passed while setting attribute '%s'", key);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		log_err(PBSE_INTERNAL, __func__, log_buffer);
		return rv;
	}

	tmp_py_str = PyUnicode_FromString(value); /* NEW reference */

	if (!tmp_py_str) { /* Uh-of failed */
		pbs_python_write_error_to_log(__func__);
		return rv;
	}
	rv = PyObject_SetAttrString(obj, key, tmp_py_str);

	if (rv == -1) {
		pbs_python_write_error_to_log(__func__);
	}
	Py_CLEAR(tmp_py_str);
	return rv;
}

/**
 * @brief
 *      pbs_python_object_set_attr_string_value
 *      Current PBS API does not have an easy interface to set a C integral value to a
 *      a object attribute. Hence, a lot of boilerplate code is needed to just set a integral
 *      value, hence this routine.
 *
 * @param[in] obj - object attribute to which string value to be set
 * @param[in] key - name of the attribute to set
 * @param[in] value - integer value to be set
 *
 * @par NOTES:
 *      - exceptions are cleared!!
 *
 * @return      int
 * @retval      0       success
 * @retval      -1      failure
 *
 */

int
pbs_python_object_set_attr_integral_value(PyObject *obj,
					  const char *key,
					  int value)
{
	PyObject *tmp_py_int = PyLong_FromSsize_t(value); /* NEW reference */

	int rv = -1;	   /* default failure */
	if (!tmp_py_int) { /* Uh-of failed */
		pbs_python_write_error_to_log(__func__);
		return rv;
	}
	rv = PyObject_SetAttrString(obj, key, tmp_py_int);

	if (rv == -1)
		pbs_python_write_error_to_log(__func__);
	Py_CLEAR(tmp_py_int);

	return rv;
}

/**
 * @brief
 *      pbs_python_object_set_attr_string_value
 *      Current PBS API does not have an easy interface to get a C integral value of
 *      a object attribute. Hence, a lot of boilerplate code is needed to just get a integral
 *      value, hence this routine.
 *
 * @param[in] obj - object attribute from which integral value is taken
 * @param[in] key - name of the attribute to get
 *
 * @return      int
 * @retval      0       success
 * @retval      -1      failure
 *
 */
int
pbs_python_object_get_attr_integral_value(PyObject *obj, const char *key)
{
	int rv = -1; /* default failure */
	PyObject *py_int = NULL;
	int retval;

	if (!key) { /* Uh-of failed */
		return rv;
	}
	if (!PyObject_HasAttrString(obj, key)) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "obj %s has no key %s", pbs_python_object_str(obj), key);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		return rv;
	}

	py_int = PyObject_GetAttrString(obj, key); /* NEW ref */

	if (!py_int) {
		pbs_python_write_error_to_log(__func__);
		return rv;
	}

	if (!PyArg_Parse(py_int, "i", &retval)) {
		pbs_python_write_error_to_log(__func__);
		Py_CLEAR(py_int);
		return rv;
	}

	Py_CLEAR(py_int);
	return (retval);
}

/**
 * @brief
 * 	Returns a string representation of 'obj' in a fixed memory area that must
 * 	not be freed. This never returns NULL.
 *
 * @par Note:
 *	next call of this function would overwrite this fixed memory area
 * 	so probably best to use the result immediately, or strdup() it.
 *
 * @param[in]	obj - object
 *
 * @return	string
 * @retval	string repsn of obj
 */
char *
pbs_python_object_str(PyObject *obj)
{
	const char *str = NULL;
	PyObject *py_str;
	static char *ret_str = NULL;
	char *tmp_str = NULL;
	size_t alloc_sz = 0;

	py_str = PyObject_Str(obj); /* NEW ref */

	if (!py_str)
		return ("");

	str = PyUnicode_AsUTF8(py_str);

	if (str)
		alloc_sz = strlen(str) + 1;
	else
		alloc_sz = 1; /* for null byte */

	tmp_str = (char *) realloc((char *) ret_str, alloc_sz);
	if (!tmp_str) { /* error on realloc */
		log_err(errno, __func__, "error on realloc");
		Py_CLEAR(py_str);
		return ("");
	}
	ret_str = tmp_str;
	*ret_str = '\0';
	if (str != NULL) {
		strncpy(ret_str, str, alloc_sz);
		ret_str[alloc_sz - 1] = '\0';
	}
	Py_CLEAR(py_str);
	return (ret_str);
}

/**
 * @brief
 * 	pbs_python_object_get_attr_string_value
 *    	Current PBS API does not have an easy interface to set a C string value to a
 *    	a object attribute. Hence, a lot of boilerplate code is needed to just set a string
 *    	value, hence this routine.
 *
 * @par	NOTES:
 *  	- exceptions are cleared!!
 * 	This must return NULL if object does not have a value for attribute 'name'.
 *
 * @param[in] obj - object
 * @param[in] name - name attr
 *
 * @return	string
 * @retval	string val to object	success
 * @retval	NULL			error
 *
 */

char *
pbs_python_object_get_attr_string_value(PyObject *obj, const char *name)
{
	char *attrval_str = NULL;
	PyObject *py_attrval = NULL;

	if (!name) {
		log_err(PBSE_INTERNAL, __func__, "No value for name");
		return NULL;
	}

	if (!PyObject_HasAttrString(obj, name)) {
		return NULL;
	}

	py_attrval = PyObject_GetAttrString(obj, name);

	if (py_attrval) {
		if (py_attrval != Py_None)
			attrval_str = pbs_python_object_str(py_attrval);
		Py_DECREF(py_attrval);
	}
	return (attrval_str);
}

/**
 * @brief
 *	pbs_python_dict_set_item_string_value
 *    	Current PBS API does not have an easy interface to set a C string value to a
 *    	a dictionary. Hence, a lot of boilerplate code is needed to just set a string
 *    	value, hence this routine.
 *
 * @param[in] dict - dictionary to which string value to be set
 * @param[in] key - name of the attribute to set
 * @param[in] value - integer value to be set
 *
 *
 * @return      int
 * @retval      0       success
 * @retval      -1      failure
 *
 */

int
pbs_python_dict_set_item_string_value(PyObject *dict,
				      const char *key,
				      const char *value)
{
	PyObject *tmp_py_str;

	int rv = -1; /* default failure */
	if (!value) {
		snprintf(log_buffer, LOG_BUF_SIZE - 1,
			 "Null value passed while setting key '%s'", key);
		log_buffer[LOG_BUF_SIZE - 1] = '\0';
		log_err(PBSE_INTERNAL, __func__, log_buffer);
		return rv;
	}

	tmp_py_str = PyUnicode_FromString(value); /* NEW reference */
	if (!tmp_py_str) {			  /* Uh-of failed */
		pbs_python_write_error_to_log(__func__);
		return rv;
	}
	rv = PyDict_SetItemString(dict, key, tmp_py_str);
	if (rv == -1)
		pbs_python_write_error_to_log(__func__);
	Py_CLEAR(tmp_py_str);
	return rv;
}

/**
 * @brief
 * 	Given a list Python object, return the string item at 'index'.
 *
 * @param[in]	list - the Python list object
 * @param[in]	index - index of the item in the list to return
 *
 * @return char *
 * @retval <string>  - a string value that is in a fixed memory area that
 * 			must not be freed. This would  be a an emnpty
 * 			string "" if no value is found.
 * @note
 * 	Next call to this function would overwrite the fixed memory area
 * 	returned, so probably best to use the result immediately,
 *	or strdup() it.
 *	This will never return a NULL value.
 */

char *
pbs_python_list_get_item_string_value(PyObject *list, int index)
{
	PyObject *py_item = NULL;
	char *ret_str = NULL;

	if (!PyList_Check(list)) {
		log_err(PBSE_INTERNAL, __func__, "Did not get passed a list object");
		return ("");
	}

	py_item = PyList_GetItem(list, index);
	if (!py_item) {
		pbs_python_write_error_to_log(__func__);
		return ("");
	}
	ret_str = pbs_python_object_str(py_item); /* does not return NULL */

	return ret_str;
}

/**
 * @brief
 * 	pbs_python_dict_set_item_integral_value
 *    	Current PBS API does not have an easy interface to set a C integral value to a
 *    	a dictionary. Hence, a lot of boilerplate code is needed to just set a integral
 *    	value, hence this routine.
 *
 * @param[in] dict - dictionary to which string value to be set
 * @param[in] key - name of the attribute to set
 * @param[in] value - integer value to be set
 *
 *
 * @return      int
 * @retval      0       success
 * @retval      -1      failure
 *
 */

int
pbs_python_dict_set_item_integral_value(PyObject *dict,
					const char *key,
					const Py_ssize_t value)
{
	int rv = -1; /* default failure */

	PyObject *tmp_py_int = PyLong_FromSsize_t(value); /* NEW reference */
	if (!tmp_py_int) {				  /* Uh-of failed */
		pbs_python_write_error_to_log(__func__);
		return rv;
	}
	rv = PyDict_SetItemString(dict, key, tmp_py_int);
	if (rv == -1)
		pbs_python_write_error_to_log(__func__);
	Py_CLEAR(tmp_py_int);
	return rv;
}

/**
 * @brief
 * 	pbs_python_import_name
 *   	This imports a name from the given module. Note this returns a NEW
 *   	reference. This essentially retrieves an attribute name.
 *
 * @param[in]	module_name - imported module name
 * @param[in] 	fromname    - imported from
 *
 * @return	object
 * @retval	object of type from imported file	success
 * @retval	exiterror code				error
 *
 */

PyObject *
pbs_python_import_name(const char *module_name, const char *fromname)
{
	PyObject *py_mod_obj = NULL;
	PyObject *py_fromname_obj = NULL;

	py_mod_obj = PyImport_ImportModule(module_name); /* fetch module */
	if (py_mod_obj == NULL) {
		goto ERROR_EXIT;
	}
	if (!(py_fromname_obj = PyObject_GetAttrString(py_mod_obj, fromname))) {
		goto ERROR_EXIT;
	}

	if (py_mod_obj)
		Py_CLEAR(py_mod_obj);

	return py_fromname_obj;

ERROR_EXIT:
	pbs_python_write_error_to_log(__func__);
	if (py_mod_obj)
		Py_CLEAR(py_mod_obj);
	return NULL;
}

/*
 * logmsg module method implementation and documentation
 *
 *  TODO
 *     This could really be a log type capturing all the log.h functionality.
 */

const char pbsv1mod_meth_logmsg_doc[] =
	"logmsg(strSeverity,strMessage)\n\
  where:\n\
\n\
   strSeverity: one of module constants\n\
              pbs.LOG_WARNING\n\
              pbs.LOG_ERROR\n\
              pbs.LOG_DEBUG (default)\n\
   strMessage:  error message to write\n\
\n\
  returns:\n\
         None\n\
";

/* note this is undefind later */
#define VALID_SEVERITY_VALUE(val) \
	((val == SEVERITY_LOG_WARNING) || (val == SEVERITY_LOG_ERR) || (val == SEVERITY_LOG_DEBUG))

#define VALID_EVENTTYPE_VALUE(val)                                \
	((val == PBSEVENT_ERROR) || (val == PBSEVENT_SYSTEM) ||   \
	 (val == PBSEVENT_JOB) || (val == PBSEVENT_JOB_USAGE) ||  \
	 (val == PBSEVENT_SECURITY) || (val == PBSEVENT_SCHED) || \
	 (val == PBSEVENT_DEBUG) || (val == PBSEVENT_DEBUG2) ||   \
	 (val == PBSEVENT_RESV) || (val == PBSEVENT_DEBUG3) ||    \
	 (val == PBSEVENT_DEBUG4) || (val == PBSEVENT_FORCE) ||   \
	 (val == PBSEVENT_ADMIN))

/**
 * @brief
 *	This is the wrapper function to the pbs.logmsg() call in the hook world.
 * 	It will basically call log_event() passing in values for eventtype,
 * 	severity, and actual log message.
 *
 * @param[in]	self - parent object
 * @param[in]	args - the list of arguments:
 * 			args[0] = loglevel	(pbs.LOG_DEBUG, pbs.EVENT_DEBUG4, etc...)
 * 			args[1] = log_message
 * 			if loglevel is pbs.LOG_DEBUG, pbs.LOG_ERROR, pbs.LOG_WARNING,
 * 			then the 'severity' argument to log_event() is set to LOG_DEBUG,
 * 			LOG_ERROR, LOG_WARNING, respectively. Otherwise, it would default
 * 			to LOG_DEBUG.
 * 			NOTE: 'severity' determines the severity of the message when
 * 			sent to syslog.
 * @return PyObjectd *
 * @retval Py_None	- for success
 * @retval NULL		- which causes an exception to the executing hook script.
 *
 */
PyObject *
pbsv1mod_meth_logmsg(PyObject *self, PyObject *args, PyObject *kwds)
{

	static char *kwlist[] = {"loglevel", "message", NULL};

	int loglevel;
	int severity = -1;
	int eventtype = -1;
	char *emsg = NULL;
	int emsg_len = 0;

	/* The use of "s#" below is to allow embedded NULLs, to guarantee */
	/* something will get printed and not get an exception */
	if (!PyArg_ParseTupleAndKeywords(args, kwds,
					 "is#:logmsg",
					 kwlist,
					 &loglevel,
					 &emsg,
					 &emsg_len)) {
		return NULL;
	}

	if (!VALID_SEVERITY_VALUE(loglevel) &&
	    !VALID_EVENTTYPE_VALUE(loglevel)) {
		PyErr_Format(PyExc_TypeError, "Invalid severity or eventtype value <%d>",
			     loglevel);
		return NULL;
	}
	/* log the message */
	if (VALID_SEVERITY_VALUE(loglevel)) {
		if (loglevel == SEVERITY_LOG_DEBUG)
			severity = LOG_DEBUG;
		else if (loglevel == SEVERITY_LOG_ERR)
			severity = LOG_ERR;
		else if (loglevel == SEVERITY_LOG_WARNING)
			severity = LOG_WARNING;
	}
	if (VALID_EVENTTYPE_VALUE(loglevel)) {
		eventtype = loglevel;
	}

	/* This usually means what got passed are the old
	 * loglevel values (pbs.LOG_DEBUG, pbs.LOG_ERROR, pbs.LOG_WARNING).
	 * These values were actually the 'severity' values for syslog.
	 * so we use the same default as before for 'eventtype' argument
	 * to log_event().
	 */
	if (eventtype == -1) {
		eventtype = (PBSEVENT_ADMIN | PBSEVENT_SYSTEM);
	}
	/* This means what got passed are the new log level values
	 * (ex .pbs.EVENT_DEBUG4) which really maps to the 'eventtype'
	 * argument to log_event(). So we'll use a default LOG_DEBUG
	 * 'severity' value for syslog.
	 */
	if (severity == -1) {
		severity = LOG_DEBUG;
	}

	log_event(eventtype, PBS_EVENTCLASS_HOOK,
		  severity, pbs_python_daemon_name, emsg);
	Py_RETURN_NONE;
}
#undef VALID_SEVERITY_VALUE

/*
 * logjobmsg module method implementation and documentation
 *
 */

const char pbsv1mod_meth_logjobmsg_doc[] =
	"logjobmsg(strJobId,strMessage)\n\
  where:\n\
\n\
   strJobId:  a PBS  job id\n\
   strMessage:  message to write to PBS log under class of messages\n\
   		related to 'strJobId'.\n\
\n\
  returns:\n\
         None\n\
";

PyObject *
pbsv1mod_meth_logjobmsg(PyObject *self, PyObject *args, PyObject *kwds)
{

	static char *kwlist[] = {"jobid", "message", NULL};

	char *jobid = NULL;
	char *msg = NULL;
	int msg_len = 0;

	/* The use of "s#" below is to allow embedded NULLs, to guarantee */
	/* something will get printed and not get an exception */
	if (!PyArg_ParseTupleAndKeywords(args, kwds,
					 "ss#:logjobmsg",
					 kwlist,
					 &jobid,
					 &msg,
					 &msg_len)) {
		return NULL;
	}

	if ((jobid == NULL) || (jobid[0] == '\0')) {
		PyErr_SetString(PyExc_ValueError, "no jobid given!");
		return NULL;
	}

	/* log the message */
	log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_DEBUG, jobid, msg);

	Py_RETURN_NONE;
}
