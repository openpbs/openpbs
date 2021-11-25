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
 * @file	pbs_python_import_types.c
 * @brief
 * This file contains all the neccessary type initialization for the "extension"
 * module.
 * Also all Python types implemented in "C" are added as "module object"
 * "svr_types" and inserted into the extension module dictionary.
 *
 */

#include <pbs_config.h>
#include <pbs_python_private.h>

/* GLOBALS */

extern PyTypeObject PPSVR_Size_Type; /* pbs_python_svr_size_type.c */

/**
 * @brief
 * 	Prepare all the types, see the PBS Extensions Documentations on why we
 * 	need to do this. Essentially, this ensures all the "slots" for the
 * 	PyTypeObject are properly initialized.
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */

int
ppsvr_prepare_all_types(void)
{
	int rv = 0; /* success */

	if ((rv = PyType_Ready(&PPSVR_Size_Type)) < 0)
		return rv;

	return rv;
}

/*
 * -----                 svr_types MODULE METHODS               ----- *
 */

static PyMethodDef svr_types_module_methods[] = {
	{NULL, NULL} /* sentinel */
};

static char svr_types_module_doc[] =
	"PBS Server types Module providing handy access to all the types\n\
\tavailable in the PBS Python Server modules.\n\
";

static struct PyModuleDef svr_types_module = {
	PyModuleDef_HEAD_INIT,
	PBS_PYTHON_V1_MODULE_EXTENSION_NAME ".svr_types",
	svr_types_module_doc,
	-1,
	svr_types_module_methods,
	NULL,
	NULL,
	NULL,
	NULL};

/**
 * @brief
 * 	ppsvr_create_types_module-creates and returns svr)types module object
 *
 * @returns	PyObject*
 * @retval	The svr_types module object (BORROWED reference)
 */

PyObject *
ppsvr_create_types_module(void)
{
	PyObject *m = NULL;	/* create types module */
	PyObject *mdict = NULL; /* module dict  */

	m = PyModule_Create(&svr_types_module);

	if (m == NULL)
		return m;
	/* let's get the modules dict, we use this instead of PyModule_AddObject
	 * because of Py_INCREF all types and then to Py_DECREF in case of error
	 * is not going to be managable
	 */
	mdict = PyModule_GetDict(m); /* never fails */

	/* Add _size type to svr_types */
	if ((PyDict_SetItemString(mdict, "_size",
				  (PyObject *) &PPSVR_Size_Type)) == -1)
		return NULL;

	return m;
}
