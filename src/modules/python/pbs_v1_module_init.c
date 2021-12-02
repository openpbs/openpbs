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

#include "pbs_config.h"
#include "pbs_ifl.h"
#include "pbs_internal.h"
#include "pbs_version.h"
#include "pbs_error.h"
#include "attribute.h"
#include "job.h"
#include "reservation.h"
#include "server.h"
#include "pbs_nodes.h"
#include "pbs_sched.h"
#include "pbs_python_private.h"
#include <Python.h>

#define PBS_V1_COMMON_MODULE_DEFINE_STUB_FUNCS 1
#include "pbs_v1_module_common.i"

/* #define MODULE_NAME "_pbs_v1_module" */
#define MODULE_NAME "pbs_python"

PyMODINIT_FUNC
PyInit__pbs_v1(void)
{
	int i;
	PyObject *module = NULL;
	PyObject *py_sys_modules = NULL;

	memset(&server, 0, sizeof(server));

	if (set_msgdaemonname(MODULE_NAME)) {
		return PyErr_Format(PyExc_MemoryError,
				    "set_msgdaemonname() failed to allocate memory");
	}

	if (pbs_loadconf(0) == 0) {
		return PyErr_Format(PyExc_Exception, "Failed to load pbs.conf!");
	}

	set_log_conf(pbs_conf.pbs_leaf_name, pbs_conf.pbs_mom_node_name,
		     pbs_conf.locallog, pbs_conf.syslogfac,
		     pbs_conf.syslogsvr, pbs_conf.pbs_log_highres_timestamp);

	pbs_python_set_use_static_data_value(0);

	/* by default, server_name is what is set in /etc/pbs.conf */
	strncpy(server_name, pbs_conf.pbs_server_name, PBS_MAXSERVERNAME);

	/* determine the actual server name */
	pbs_server_name = pbs_default();
	if ((!pbs_server_name) || (*pbs_server_name == '\0')) {
		return PyErr_Format(PyExc_Exception,
				    "pbs_default() failed acquire the server name");
	}

	/* determine the server host name */
	if (get_fullhostname(pbs_server_name, server_host, PBS_MAXSERVERNAME) != 0) {
		return PyErr_Format(PyExc_Exception,
				    "get_fullhostname() failed to acqiure the server host name");
	}

	if ((job_attr_idx = cr_attrdef_idx(job_attr_def, JOB_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
				    "Failed creating job attribute search index");
	}
	if ((node_attr_idx = cr_attrdef_idx(node_attr_def, ND_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
				    "Failed creating node attribute search index");
	}
	if ((que_attr_idx = cr_attrdef_idx(que_attr_def, QA_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
				    "Failed creating queue attribute search index");
	}
	if ((svr_attr_idx = cr_attrdef_idx(svr_attr_def, SVR_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
				    "Failed creating server attribute search index");
	}
	if ((sched_attr_idx = cr_attrdef_idx(sched_attr_def, SCHED_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
				    "Failed creating sched attribute search index");
	}
	if ((resv_attr_idx = cr_attrdef_idx(resv_attr_def, RESV_ATR_LAST)) == NULL) {
		return PyErr_Format(PyExc_Exception,
				    "Failed creating resv attribute search index");
	}
	if (cr_rescdef_idx(svr_resc_def, svr_resc_size) != 0) {
		return PyErr_Format(PyExc_Exception,
				    "Failed creating resc definition search index");
	}

	/* initialize the pointers in the resource_def array */
	for (i = 0; i < (svr_resc_size - 1); ++i) {
		svr_resc_def[i].rs_next = &svr_resc_def[i + 1];
	}

	/* set python interp data */
	svr_interp_data.init_interpreter_data = NULL;
	svr_interp_data.destroy_interpreter_data = NULL;
	svr_interp_data.interp_started = 1;
	svr_interp_data.pbs_python_types_loaded = 0;
	if (gethostname(svr_interp_data.local_host_name, PBS_MAXHOSTNAME) == -1) {
		return PyErr_Format(PyExc_Exception,
				    "gethostname() failed to acquire the local host name");
	}
	svr_interp_data.daemon_name = strdup(MODULE_NAME);
	svr_interp_data.data_initialized = 1;

	/* construct _pbs_v1 module */
	module = pbs_v1_module_init();
	if (module == NULL) {
		return PyErr_Format(PyExc_Exception,
				    PBS_PYTHON_V1_MODULE_EXTENSION_NAME
				    " module initialization failed");
	}

	/*
	 * get a borrowed reference to sys.modules and add our module to it in order
	 * to prevent an import cycle while loading the PBS python types
	 */
	py_sys_modules = PyImport_GetModuleDict();
	if (PyDict_SetItemString(py_sys_modules,
				 PBS_PYTHON_V1_MODULE_EXTENSION_NAME, module)) {
		return PyErr_Format(PyExc_Exception,
				    "failed to addd the " PBS_PYTHON_V1_MODULE_EXTENSION_NAME
				    " module to sys.modules");
	}

	/* load python types into the _pbs_v1 module */
	if ((pbs_python_load_python_types(&svr_interp_data) == -1)) {
		PyDict_DelItemString(py_sys_modules,
				     PBS_PYTHON_V1_MODULE_EXTENSION_NAME);
		return PyErr_Format(PyExc_Exception,
				    "pbs_python_load_python_types() failed to load Python types");
	}

	return module;
}
