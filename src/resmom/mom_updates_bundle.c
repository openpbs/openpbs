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
 * This file containes functions related to generate resc used updates
 * and make bundle of it and sent it to server
 */

#include <pbs_config.h> /* the master config generated by configure */
#include <pbs_python_private.h>
#include <Python.h>
#include <time.h>
#include "resource.h"
#include "job.h"
#include "mom_func.h"
#include "mom_server.h"
#include "hook.h"
#include "tpp.h"

extern pbs_list_head mom_pending_ruu;
extern int resc_access_perm;
extern int server_stream;
extern time_t time_now;

static void bundle_ruu(int *r_cnt, ruu **prused, int *rh_cnt, ruu **prhused, int *o_cnt, ruu **obits);
static ruu *get_job_update(job *pjob);
static PyObject *json_loads(char *value, char *msg, size_t msg_len);
static char *json_dumps(PyObject *py_val, char *msg, size_t msg_len);
static void encode_used(job *pjob, pbs_list_head *phead);

static PyObject *py_json_name = NULL;
static PyObject *py_json_module = NULL;
static PyObject *py_json_dict = NULL;
static PyObject *py_json_func_loads = NULL;
static PyObject *py_json_func_dumps = NULL;

#ifdef PYTHON
/**
 * @brief
 * 	Returns the Python dictionary representation of a string
 *	specyfing a JSON object.
 *
 * @param[in]  value   - string of JSON-object format
 * @param[out] msg     - error message buffer
 * @param[in]  msg_len - size of 'msg' buffer
 *
 * @return PyObject *
 * @retval !NULL - dictionary representation of 'value'
 * @retval NULL  - if not successful, filling out 'msg' with the actual error message.
 */
static PyObject *
json_loads(char *value, char *msg, size_t msg_len)
{
	PyObject *py_value = NULL;
	PyObject *py_result = NULL;

	if (value == NULL)
		return NULL;

	if (msg != NULL) {
		if (msg_len <= 0)
			return NULL;
		msg[0] = '\0';
	}

	if (py_json_name == NULL) {
		py_json_name = PyUnicode_FromString("json");
		if (py_json_name == NULL) {
			if (msg != NULL)
				snprintf(msg, msg_len, "failed to construct json name");
			return NULL;
		}
	}

	if (py_json_module == NULL) {
		py_json_module = PyImport_Import(py_json_name);
		if (py_json_module == NULL) {
			if (msg != NULL)
				snprintf(msg, msg_len, "failed to import json");
			return NULL;
		}
	}

	if (py_json_dict == NULL) {
		py_json_dict = PyModule_GetDict(py_json_module);
		if (py_json_dict == NULL) {
			if (msg != NULL)
				snprintf(msg, msg_len, "failed to get json module dictionary");
			return NULL;
		}
	}

	if (py_json_func_loads == NULL) {
		py_json_func_loads = PyDict_GetItemString(py_json_dict, (char *) "loads");
		if ((py_json_func_loads == NULL) || !PyCallable_Check(py_json_func_loads)) {
			if (msg != NULL)
				snprintf(msg, msg_len, "did not find json.loads() function");
			return NULL;
		}
	}

	py_value = Py_BuildValue("(z)", (char *) value);
	if (py_value == NULL) {
		if (msg != NULL)
			snprintf(msg, msg_len, "failed to build python arg %s", value);
		return NULL;
	}

	PyErr_Clear(); /* clear any exception */
	py_result = PyObject_CallObject(py_json_func_loads, py_value);

	if (PyErr_Occurred()) {
		if (msg != NULL) {
			PyObject *exc_string = NULL;
			PyObject *exc_type = NULL;
			PyObject *exc_value = NULL;
			PyObject *exc_traceback = NULL;

			PyErr_Fetch(&exc_type, &exc_value, &exc_traceback);

			/* get the exception */
			if (exc_type != NULL && (exc_string = PyObject_Str(exc_type)) != NULL && PyUnicode_Check(exc_string))
				snprintf(msg, msg_len, "%s", PyUnicode_AsUTF8(exc_string));
			Py_XDECREF(exc_string);
			Py_XDECREF(exc_type);
			Py_XDECREF(exc_value);
#if !defined(WIN32)
			Py_XDECREF(exc_traceback);
#elif !defined(_DEBUG)
			/* for some reason this crashes on Windows Debug */
			Py_XDECREF(exc_traceback);
#endif
		}
		goto json_loads_fail;
	} else if (!PyDict_Check(py_result)) {
		if (msg != NULL)
			snprintf(msg, msg_len, "value is not a dictionary");
		goto json_loads_fail;
	}

	Py_XDECREF(py_value);
	return (py_result);

json_loads_fail:
	Py_XDECREF(py_value);
	Py_XDECREF(py_result);
	return NULL;
}

/**
 * @brief
 * 	Returns a JSON-formatted string representing the Python object 'py_val'.
 *
 * @param[in]  py_val  - Python object
 * @param[out] msg     - error message buffer
 * @param[in]  msg_len - size of 'msg' buffer
 *
 * @return char *
 * @retval !NULL - the returned JSON-formatted string
 * @retval NULL  - if not successful, filling out 'msg' with the actual error message.
 *
 * @note
 *	The returned string is malloced space that must be freed later when no longer needed.
 */
static char *
json_dumps(PyObject *py_val, char *msg, size_t msg_len)
{
	PyObject *py_value = NULL;
	PyObject *py_result = NULL;
	const char *tmp_str = NULL;
	char *ret_string = NULL;
	int slen;

	if (py_val == NULL)
		return NULL;

	if (msg != NULL) {
		if (msg_len <= 0)
			return NULL;
		msg[0] = '\0';
	}

	if (py_json_name == NULL) {
		py_json_name = PyUnicode_FromString("json");
		if (py_json_name == NULL) {
			if (msg != NULL)
				snprintf(msg, msg_len, "failed to construct json name");
			return NULL;
		}
	}

	if (py_json_module == NULL) {
		py_json_module = PyImport_Import(py_json_name);
		if (py_json_module == NULL) {
			if (msg != NULL)
				snprintf(msg, msg_len, "failed to import json");
			return NULL;
		}
	}

	if (py_json_dict == NULL) {
		py_json_dict = PyModule_GetDict(py_json_module);
		if (py_json_dict == NULL) {
			if (msg != NULL)
				snprintf(msg, msg_len, "failed to get json module dictionary");
			return NULL;
		}
	}

	if (py_json_func_dumps == NULL) {
		py_json_func_dumps = PyDict_GetItemString(py_json_dict, (char *) "dumps");
		if ((py_json_func_dumps == NULL) || !PyCallable_Check(py_json_func_dumps)) {
			if (msg != NULL)
				snprintf(msg, msg_len, "did not find json.dumps() function");
			return NULL;
		}
	}

	py_value = Py_BuildValue("(O)", py_val);
	if (py_value == NULL) {
		if (msg != NULL)
			snprintf(msg, msg_len, "failed to build python arg %p", (void *) py_val);
		return NULL;
	}
	PyErr_Clear(); /* clear any exception */
	py_result = PyObject_CallObject(py_json_func_dumps, py_value);

	if (PyErr_Occurred()) {
		if (msg != NULL) {
			PyObject *exc_string = NULL;
			PyObject *exc_type = NULL;
			PyObject *exc_value = NULL;
			PyObject *exc_traceback = NULL;

			PyErr_Fetch(&exc_type, &exc_value, &exc_traceback);

			/* get the exception */
			if (exc_type != NULL && (exc_string = PyObject_Str(exc_type)) != NULL && PyUnicode_Check(exc_string))
				snprintf(msg, msg_len, "%s", PyUnicode_AsUTF8(exc_string));
			Py_XDECREF(exc_string);
			Py_XDECREF(exc_type);
			Py_XDECREF(exc_value);
#if !defined(WIN32)
			Py_XDECREF(exc_traceback);
#elif !defined(_DEBUG)
			/* for some reason this crashes on Windows Debug */
			Py_XDECREF(exc_traceback);
#endif
		}
		goto json_dumps_fail;
	} else if (!PyUnicode_Check(py_result)) {
		if (msg != NULL)
			snprintf(msg, msg_len, "value is not a string");
		goto json_dumps_fail;
	}

	tmp_str = PyUnicode_AsUTF8(py_result);
	/* returned tmp_str points to an internal buffer of 'py_result' */
	if (tmp_str == NULL) {
		if (msg != NULL)
			snprintf(msg, msg_len, "PyUnicode_AsUTF8 failed");
		goto json_dumps_fail;
	}
	slen = strlen(tmp_str) + 3; /* for null character + 2 single quotes */
	ret_string = (char *) malloc(slen);
	if (ret_string == NULL) {
		if (msg != NULL)
			snprintf(msg, msg_len, "malloc of ret_string failed");
		goto json_dumps_fail;
	}
	snprintf(ret_string, slen, "'%s'", tmp_str);
	Py_XDECREF(py_value);
	Py_XDECREF(py_result);
	return (ret_string);

json_dumps_fail:
	Py_XDECREF(py_value);
	Py_XDECREF(py_result);
	return NULL;
}
#endif

/**
 * @brief
 * 	 encode_used - encode resources used by a job to be returned to the server
 *
 * @param[in] pjob - pointer to job structure
 * @param[in] phead - pointer to pbs_list_head structure
 *
 * @return Void
 *
 */
static void
encode_used(job *pjob, pbs_list_head *phead)
{
	attribute_def *ad;
	attribute_def *ad3;
	resource *rs;
	resource_def *rd;
	int include_resc_used_update = 0;

	ad = &job_attr_def[JOB_ATR_resc_used];
	if (!is_jattr_set(pjob, JOB_ATR_resc_used))
		return;

	ad3 = &job_attr_def[JOB_ATR_resc_used_update];
	if (pjob->ji_updated || (is_jattr_set(pjob, JOB_ATR_relnodes_on_stageout) && (get_jattr_long(pjob, JOB_ATR_relnodes_on_stageout) != 0)))
		include_resc_used_update = 1;

	rs = (resource *) GET_NEXT(get_jattr_list(pjob, JOB_ATR_resc_used));
	for (; rs != NULL; rs = (resource *) GET_NEXT(rs->rs_link)) {

		int i;
		attribute val;	/* holds the final accumulated resources_used values from Moms including those released from the job */
		attribute val3; /* holds the final accumulated resources_used values from Moms, which does not include the released moms from job */
		PyObject *py_jvalue;
		char *sval;
		char *dumps;
		char emsg[HOOK_BUF_SIZE];
		attribute tmpatr = {0};
		attribute tmpatr3 = {0};

		rd = rs->rs_defin;
		if ((rd->rs_flags & resc_access_perm) == 0)
			continue;

		val = val3 = rs->rs_value; /* copy resource attribute */

		/* NOTE: presence of pjob->ji_resources means a multinode job (i.e. pjob->ji_numnodes > 1) */
		if (pjob->ji_resources != NULL) {
			/* count up sisterhood too */
			unsigned long lnum = 0;
			unsigned long lnum3 = 0;
			noderes *nr;

			if (strcmp(rd->rs_name, "cput") == 0) {
				for (i = 0; i < pjob->ji_numrescs; i++) {
					nr = &pjob->ji_resources[i];
					lnum += nr->nr_cput;
					if (nr->nr_status != PBS_NODERES_DELETE)
						lnum3 += nr->nr_cput;
				}
				val.at_val.at_long += lnum;
				val3.at_val.at_long += lnum3;
			} else if (strcmp(rd->rs_name, "mem") == 0) {
				for (i = 0; i < pjob->ji_numrescs; i++) {
					nr = &pjob->ji_resources[i];
					lnum += nr->nr_mem;
					if (nr->nr_status != PBS_NODERES_DELETE)
						lnum3 += nr->nr_mem;
				}
				val.at_val.at_long += lnum;
				val3.at_val.at_long += lnum3;
			} else if (strcmp(rd->rs_name, "cpupercent") == 0) {
				for (i = 0; i < pjob->ji_numrescs; i++) {
					nr = &pjob->ji_resources[i];
					lnum += nr->nr_cpupercent;
					if (nr->nr_status != PBS_NODERES_DELETE)
						lnum3 += nr->nr_cpupercent;
				}
				val.at_val.at_long += lnum;
				val3.at_val.at_long += lnum3;
			}
#ifdef PYTHON
			else if (strcmp(rd->rs_name, RESOURCE_UNKNOWN) != 0 &&
				 (val.at_type == ATR_TYPE_LONG ||
				  val.at_type == ATR_TYPE_FLOAT ||
				  val.at_type == ATR_TYPE_SIZE ||
				  val.at_type == ATR_TYPE_STR)) {

				PyObject *py_accum = NULL;  /* holds accum resources_used values from all moms (including the released sister moms from job) */
				PyObject *py_accum3 = NULL; /* holds accum resources_used values from all moms (NOT including the released sister moms from job) */

				/* The following 2 temp variables will be set to 1
				 * if there's an error accumulating resources_used
				 * values from all sister moms including those that
				 * have been released from the job (fail) or from
				 * all sister moms NOT including the released nodes
				 * from job (fail2).
				 */
				int fail = 0;
				int fail2 = 0;

				py_jvalue = NULL;
				tmpatr.at_type = tmpatr3.at_type = val.at_type;

				if (val.at_type != ATR_TYPE_STR) {
					rd->rs_set(&tmpatr, &val, SET);
					rd->rs_set(&tmpatr3, &val, SET);
				} else {
					py_accum = PyDict_New();
					if (py_accum == NULL) {
						log_err(-1, __func__, "error creating accumulation dictionary");
						continue;
					}
					py_accum3 = PyDict_New();
					if (py_accum3 == NULL) {
						log_err(-1, __func__, "error creating accumulation dictionary 3");
						Py_CLEAR(py_accum);
						continue;
					}
				}

				/* accumulating resources_used values from sister
				 * moms into tmpatr (from all sisters including released
				 * moms) and tmpatr3 (from sisters that have not been
				 * released from the job).
				 */
				for (i = 0; i < pjob->ji_numrescs; i++) {
					char mom_hname[PBS_MAXHOSTNAME + 1];
					char *p = NULL;
					attribute *at2;
					resource *rs2;

					if (pjob->ji_resources[i].nodehost == NULL)
						continue;

					at2 = &pjob->ji_resources[i].nr_used;
					if ((at2->at_flags & ATR_VFLAG_SET) == 0)
						continue;

					pbs_strncpy(mom_hname, pjob->ji_resources[i].nodehost, sizeof(mom_hname));
					mom_hname[PBS_MAXHOSTNAME] = '\0';
					p = strchr(mom_hname, '.');
					if (p != NULL)
						*p = '\0';

					fail = fail2 = 0;
					rs2 = (resource *) GET_NEXT(at2->at_val.at_list);
					for (; rs2 != NULL; rs2 = (resource *) GET_NEXT(rs2->rs_link)) {

						attribute val2; /* temp variable for accumulating resources_used from sis Moms */
						resource_def *rd2;

						rd2 = rs2->rs_defin;
						val2 = rs2->rs_value; /* copy resource attribute */
						if ((val2.at_flags & ATR_VFLAG_SET) == 0 || strcmp(rd2->rs_name, rd->rs_name) != 0)
							continue;

						if (val2.at_type == ATR_TYPE_STR) {
							sval = val2.at_val.at_str;
							py_jvalue = json_loads(sval, emsg, HOOK_BUF_SIZE - 1);
							if (py_jvalue == NULL) {
								log_errf(-1, __func__,
									 "Job %s resources_used.%s cannot be accumulated: value '%s' from mom %s not JSON-format: %s",
									 pjob->ji_qs.ji_jobid, rd2->rs_name, sval, mom_hname, emsg);
								fail = 1;
							} else if (PyDict_Merge(py_accum, py_jvalue, 1) != 0) {
								log_errf(-1, __func__,
									 "Job %s resources_used.%s cannot be accumulated: value '%s' from mom %s: error merging values",
									 pjob->ji_qs.ji_jobid, rd2->rs_name, sval, mom_hname);
								Py_CLEAR(py_jvalue);
								fail = 1;
							} else {
								if (pjob->ji_resources[i].nr_status != PBS_NODERES_DELETE) {
									if (PyDict_Merge(py_accum3, py_jvalue, 1) != 0) {
										log_errf(-1, __func__,
											 "Job %s resources_used.%s cannot be accumulated: value '%s' from mom %s: error merging values",
											 pjob->ji_qs.ji_jobid, rd2->rs_name, sval, mom_hname);
										fail2 = 1;
									}
									Py_CLEAR(py_jvalue);
								} else {
									Py_CLEAR(py_jvalue);
								}
							}

						} else {
							rd->rs_set(&tmpatr, &val2, INCR);
							if (pjob->ji_resources[i].nr_status != PBS_NODERES_DELETE)
								rd->rs_set(&tmpatr3, &val2, INCR);
						}
						break;
					}
				}

				/* accumulating the resources_used values from MS mom */

				if (val.at_type == ATR_TYPE_STR) {

					if (fail) {
						Py_CLEAR(py_accum);
						Py_CLEAR(py_accum3);
						/* unset resc */
						(void) add_to_svrattrl_list(phead, ad->at_name, rd->rs_name, "", SET, NULL);
						/* go to next resource to encode_used */
						continue;
					}

					if (fail2) {
						Py_CLEAR(py_accum);
						Py_CLEAR(py_accum3);
						/* unset resc */
						(void) add_to_svrattrl_list(phead, ad3->at_name, rd->rs_name, "", SET, NULL);
						/* go to next resource to encode_used */
						continue;
					}

					sval = val.at_val.at_str;
					if (PyDict_Size(py_accum) == 0) {
						/* no other values seen
						 * except from MS...use as is
						 * don't JSONify
						 */
						rd->rs_decode(&tmpatr, ATTR_used, rd->rs_name, sval);
						Py_CLEAR(py_accum);
						Py_CLEAR(py_accum3);
					} else if ((py_jvalue = json_loads(sval, emsg, HOOK_BUF_SIZE - 1)) == NULL) {
						log_errf(-1, __func__,
							 "Job %s resources_used.%s cannot be accumulated: value '%s' from mom %s not JSON-format: %s",
							 pjob->ji_qs.ji_jobid, rd->rs_name, sval, mom_short_name, emsg);
						Py_CLEAR(py_accum);
						Py_CLEAR(py_accum3);
						/* unset resc */
						(void) add_to_svrattrl_list(phead, ad->at_name, rd->rs_name, "", SET, NULL);
						/* go to next resource to encode */
						continue;
					} else if (PyDict_Merge(py_accum, py_jvalue, 1) != 0) {
						log_errf(-1, __func__,
							 "Job %s resources_used.%s cannot be accumulated: value '%s' from mom %s: error merging values",
							 pjob->ji_qs.ji_jobid, rd->rs_name, sval, mom_short_name);
						Py_CLEAR(py_jvalue);
						Py_CLEAR(py_accum);
						Py_CLEAR(py_accum3);
						/* unset resc */
						(void) add_to_svrattrl_list(phead, ad->at_name, rd->rs_name, "", SET, NULL);
						/* go to next resource to encode */
						continue;
					} else {
						dumps = json_dumps(py_accum, emsg, HOOK_BUF_SIZE - 1);
						if (dumps == NULL) {
							log_errf(-1, __func__,
								 "Job %s resources_used.%s cannot be accumulated: %s",
								 pjob->ji_qs.ji_jobid, rd->rs_name, emsg);
							Py_CLEAR(py_jvalue);
							Py_CLEAR(py_accum);
							Py_CLEAR(py_accum3);
							/* unset resc */
							(void) add_to_svrattrl_list(phead, ad->at_name, rd->rs_name, "", SET, NULL);
							continue;
						}

						rd->rs_decode(&tmpatr, ATTR_used, rd->rs_name, dumps);
						Py_CLEAR(py_accum);
						free(dumps);

						if (PyDict_Merge(py_accum3, py_jvalue, 1) != 0) {
							log_errf(-1, __func__,
								 "Job %s resources_used_update.%s cannot be accumulated: value '%s' from mom %s: error merging values",
								 pjob->ji_qs.ji_jobid, rd->rs_name, sval, mom_short_name);
							Py_CLEAR(py_jvalue);
							Py_CLEAR(py_accum3);
							/* unset resc */
							(void) add_to_svrattrl_list(phead, ad3->at_name, rd->rs_name, "", SET, NULL);
							/* go to next resource to encode */
							continue;
						} else if ((dumps = json_dumps(py_accum3, emsg, HOOK_BUF_SIZE - 1)) == NULL) {
							log_errf(-1, __func__,
								 "Job %s resources_used_update.%s cannot be accumulated: %s",
								 pjob->ji_qs.ji_jobid, rd->rs_name, emsg);
							Py_CLEAR(py_jvalue);
							Py_CLEAR(py_accum3);
							/* unset resc */
							(void) add_to_svrattrl_list(phead, ad3->at_name, rd->rs_name, "", SET, NULL);
							continue;
						} else {
							rd->rs_decode(&tmpatr3, ATTR_used_update, rd->rs_name, dumps);
							Py_CLEAR(py_jvalue);
							Py_CLEAR(py_accum3);
							free(dumps);
						}
					}
				}
				val = tmpatr;
				val3 = tmpatr3;
			}
#endif
			/* no resource to accumulate and yet a multinode job */
		}

		if (val.at_type != ATR_TYPE_STR || pjob->ji_numnodes == 1 || pjob->ji_resources != NULL) {
			/* for string values, set value if single node job
			 * (i.e. pjob->ji_numnodes == 1), or
			 * if the value is accumulated from the various
			 * values obtained from sister nodes
			 * (i.e. pjob->ji_resources != NULL).
			 */
			if (val.at_type == ATR_TYPE_STR && pjob->ji_numnodes == 1) {
				/* check if string value is a valid json string,
				 * if it is then set the resource string within
				 * single quotes.
				 */

				sval = val.at_val.at_str;
				if ((py_jvalue = json_loads(sval, emsg, HOOK_BUF_SIZE - 1)) != NULL) {
					dumps = json_dumps(py_jvalue, emsg, HOOK_BUF_SIZE - 1);
					if (dumps == NULL)
						Py_CLEAR(py_jvalue);
					else {
						rd->rs_decode(&tmpatr, ATTR_used, rd->rs_name, dumps);
						val = tmpatr;
						Py_CLEAR(py_jvalue);
						free(dumps);
						dumps = NULL;
					}
				}
			}

			if (rd->rs_encode(&val, phead, ad->at_name, rd->rs_name, ATR_ENCODE_CLIENT, NULL) < 0)
				goto encode_used_exit;

			if (include_resc_used_update) {
				if (rd->rs_encode(&val3, phead, ad3->at_name, rd->rs_name, ATR_ENCODE_CLIENT, NULL) < 0)
					goto encode_used_exit;
			}
		}

	encode_used_exit:
		if ((tmpatr.at_flags & ATR_VFLAG_SET) != 0 && tmpatr.at_type == ATR_TYPE_STR)
			rd->rs_free(&tmpatr);
		if ((tmpatr3.at_flags & ATR_VFLAG_SET) != 0 && tmpatr3.at_type == ATR_TYPE_STR)
			rd->rs_free(&tmpatr3);
	}
}

/**
 * @brief
 * 	generate new resc used update based on given job information
 *
 * @param[in] pjob - pointer to job
 *
 * @return ruu *
 *
 * @return NULL  - failure
 * @return !NULL - success
 *
 * @warning
 * 	retuned pointer should be free'd using FREE_RUU() when not needed
 */
static ruu *
get_job_update(job *pjob)
{
	/*
	 * the following is a list of attributes to be returned to the server
	 * for a newly executing job. They are returned only if they have
	 * been modified by Mom.  Note that JOB_ATR_session_id and JOB_ATR_resc_used
	 * are always returned;
	 */
	static enum job_atr mom_rtn_list[] = {
		JOB_ATR_errpath,
		JOB_ATR_outpath,
		JOB_ATR_altid,
		JOB_ATR_acct_id,
		JOB_ATR_jobdir,
		JOB_ATR_exectime,
		JOB_ATR_hold,
		JOB_ATR_variables,
		JOB_ATR_runcount,
		JOB_ATR_exec_vnode,
		JOB_ATR_SchedSelect,
		JOB_ATR_LAST};
	ruu *prused;
	int i;
	int nth;
	attribute *at;
	attribute_def *ad;

	prused = (ruu *) calloc(1, sizeof(ruu));
	if (prused == NULL) {
		log_joberr(errno, __func__, "Out of memory while encoding stat update", pjob->ji_qs.ji_jobid);
		return NULL;
	}
	CLEAR_LINK(prused->ru_pending);
	CLEAR_HEAD(prused->ru_attr);
	prused->ru_created_at = time(0);
	prused->ru_pjobid = strdup(pjob->ji_qs.ji_jobid);
	if (prused->ru_pjobid == NULL) {
		FREE_RUU(prused);
		log_joberr(errno, __func__, "Out of memory while encoding jobid in stat update", pjob->ji_qs.ji_jobid);
		return NULL;
	}

	resc_access_perm = ATR_DFLAG_MGRD;

	if (is_jattr_set(pjob, JOB_ATR_run_version))
		prused->ru_hop = get_jattr_long(pjob, JOB_ATR_run_version);
	else
		prused->ru_hop = get_jattr_long(pjob, JOB_ATR_runcount);
#ifdef WIN32
	if (is_jattr_set(pjob, JOB_ATR_Comment)) {
		prused->ru_comment = strdup(get_jattr_str(pjob, JOB_ATR_Comment));
		if (prused->ru_comment == NULL)
			log_joberr(errno, __func__, "Out of memory while encoding comment in stat update", pjob->ji_qs.ji_jobid);
	}
#endif
	if ((at = get_jattr(pjob, JOB_ATR_session_id))->at_flags & ATR_VFLAG_MODIFY) {
		log_eventf(PBSEVENT_DEBUG3, PBS_EVENTCLASS_JOB, LOG_DEBUG, pjob->ji_qs.ji_jobid, "SID is: %ld", get_jattr_long(pjob, JOB_ATR_session_id));
		job_attr_def[JOB_ATR_session_id].at_encode(at, &prused->ru_attr,
							   job_attr_def[JOB_ATR_session_id].at_name,
							   NULL, ATR_ENCODE_CLIENT, NULL);
	}

	if (mock_run) {
		/* Also add substate & state to the attrs sent to servers since we don't have a session id */
		job_attr_def[JOB_ATR_state].at_encode(get_jattr(pjob, JOB_ATR_state), &prused->ru_attr,
						      job_attr_def[JOB_ATR_state].at_name, NULL, ATR_ENCODE_CLIENT, NULL);
		job_attr_def[JOB_ATR_substate].at_encode(get_jattr(pjob, JOB_ATR_substate), &prused->ru_attr,
							 job_attr_def[JOB_ATR_substate].at_name, NULL, ATR_ENCODE_CLIENT, NULL);
	}

	/*
	 * walltime must be set before encoded_used because in case of rerun
	 * job without used walltime, the Resource_List.walltime could be used
	 * as used.walltime for scheduling/calendaring.
	 */
	update_walltime(pjob);

	encode_used(pjob, &prused->ru_attr);

	/* Now add certain others as required for updating at the Server */
	for (i = 0; mom_rtn_list[i] != JOB_ATR_LAST; ++i) {
		nth = mom_rtn_list[i];
		at = get_jattr(pjob, nth);
		ad = &job_attr_def[nth];

		if ((at->at_flags & ATR_VFLAG_MODIFY) ||
		    (at->at_flags & ATR_VFLAG_HOOK) ||
		    (pjob->ji_pending_ruu != NULL && find_svrattrl_list_entry(&(((ruu *) pjob->ji_pending_ruu)->ru_attr), ad->at_name, NULL) != NULL)) {
			ad->at_encode(at, &prused->ru_attr, ad->at_name, NULL, ATR_ENCODE_CLIENT, NULL);
			if (at->at_flags & ATR_VFLAG_MODIFY)
				at->at_flags &= ~ATR_VFLAG_MODIFY;
		}
	}

	return prused;
}

/**
 * @brief
 * 	generate resc used update for given job and put it in queue
 * 	to send to server
 *
 * @param[in] pjob - pointer to job
 * @param[in] cmd  - cmd to be send along with resc used update to server
 *
 * @return int
 *
 * @retval 1 - failure
 * @retval 0 - success
 *
 */
int
enqueue_update_for_send(job *pjob, int cmd)
{
	ruu *prused = get_job_update(pjob);
	if (prused == NULL)
		return 1; /* get_job_update has done error logging */

	if ((pjob->ji_qs.ji_svrflags & JOB_SVFLG_HERE) == 0) {
		/* If sister node of job, send update right away */
		send_resc_used(cmd, 1, prused);
		FREE_RUU(prused);
		return 0;
	}

	if (pjob->ji_pending_ruu != NULL) {
		ruu *x = (ruu *) (pjob->ji_pending_ruu);
		FREE_RUU(x);
	}
	prused->ru_cmd = cmd;
	prused->ru_pjob = pjob;
	pjob->ji_pending_ruu = prused;
	if (cmd == IS_JOBOBIT)
		prused->ru_status = pjob->ji_qs.ji_un.ji_momt.ji_exitstat;

	/* link in global pending ruu update list */
	append_link(&mom_pending_ruu, &prused->ru_pending, (void *) prused);

	return 0;
}

/**
 * @brief
 * 	create bundles of pending updates in queue based on their cmds
 * 	if cmd of update is not IS_OBIT then check time of creatation
 * 	of update and based on that decide whether to send that update
 * 	or delay it for rescused_send_delay
 *
 * @param[out] r_cnt    - number of updates in prused bundle
 * @param[out] prused   - bundle of IS_RESCUSED updates
 * @param[out] rh_cnt   - number of updates in prhused bundle
 * @param[out] prhused  - bundle of IS_RESCUSED_FROM_HOOK updates
 * @param[out] obits_cnt - number of updates in obits bundle
 * @param[out] obits    - bundle of IS_OBIT updates
 *
 * @return void
 *
 */
static void
bundle_ruu(int *r_cnt, ruu **prused, int *rh_cnt, ruu **prhused, int *obits_cnt, ruu **obits)
{
	static int rescused_send_delay = 2;
	ruu *cur;
	ruu *next;

	*r_cnt = 0;
	*prused = NULL;
	*rh_cnt = 0;
	*prhused = NULL;
	*obits_cnt = 0;
	*obits = NULL;

	cur = (ruu *) GET_NEXT(mom_pending_ruu);
	while (cur != NULL) {
		next = (ruu *) GET_NEXT(cur->ru_pending);
		if (cur->ru_cmd == IS_JOBOBIT) {
			cur->ru_next = *obits;
			*obits = cur;
			(*obits_cnt)++;
		} else if (time_now >= (cur->ru_created_at + rescused_send_delay)) {
			if (cur->ru_cmd == IS_RESCUSED) {
				cur->ru_next = *prused;
				*prused = cur;
				(*r_cnt)++;
			} else if (cur->ru_cmd == IS_RESCUSED_FROM_HOOK) {
				cur->ru_next = *prhused;
				*prhused = cur;
				(*rh_cnt)++;
			}
		}
		cur = next;
	}
}

/**
 * @brief
 * 	Send the amount of resources used by jobs to the server
 * 	This function used to encode and send the data for IS_RESCUSED,
 * 	IS_JOBOBIT, IS_RESCUSED_FROM_HOOK.
 *
 * @param[in] cmd   - communication command to use
 * @param[in] count - number of  jobs to update.
 * @param[in] rud   - input structure containing info about the jobs, resources used, etc...
 *
 * @note
 * 	If cmd is IS_RESCUSED_FROM_HOOK and there's an error communicating
 * 	to the server, the server_stream connection is not closed automatically.
 * 	It's possible it could be a transient error, and this function may
 * 	have been called from a child mom. Closing the server_stream would
 * 	cause the server to see mom as down.
 *
 * @return void
 *
 */
void
send_resc_used(int cmd, int count, ruu *rud)
{
	int ret;

	if (count == 0 || rud == NULL || server_stream < 0)
		return;
	log_eventf(PBSEVENT_DEBUG3, PBS_EVENTCLASS_NODE, LOG_DEBUG, "",
		   "send_resc_used update to server on stream %d\n", server_stream);

	ret = is_compose(server_stream, cmd);
	if (ret != DIS_SUCCESS)
		goto err;

	ret = diswui(server_stream, count);
	if (ret != DIS_SUCCESS)
		goto err;

	while (rud) {
		ret = diswst(server_stream, rud->ru_pjobid);
		if (ret != DIS_SUCCESS)
			goto err;

		if (rud->ru_comment) {
			/* non-null comment: send "1" followed by comment */
			ret = diswsi(server_stream, 1);
			if (ret != DIS_SUCCESS)
				goto err;
			ret = diswst(server_stream, rud->ru_comment);
			if (ret != DIS_SUCCESS)
				goto err;
		} else {
			/* null comment: send "0" */
			ret = diswsi(server_stream, 0);
			if (ret != DIS_SUCCESS)
				goto err;
		}
		ret = diswsi(server_stream, rud->ru_status);
		if (ret != DIS_SUCCESS)
			goto err;

		ret = diswsi(server_stream, rud->ru_hop);
		if (ret != DIS_SUCCESS)
			goto err;

		ret = encode_DIS_svrattrl(server_stream, (svrattrl *) GET_NEXT(rud->ru_attr));
		if (ret != DIS_SUCCESS)
			goto err;

		rud = rud->ru_next;
	}

	if (dis_flush(server_stream) != 0)
		goto err;

	return;

err:
	sprintf(log_buffer, "%s for %d", dis_emsg[ret], cmd);
#ifdef WIN32
	if (errno != 10054)
#endif
		log_err(errno, "send_resc_used", log_buffer);

	if (cmd != IS_RESCUSED_FROM_HOOK) {
		tpp_close(server_stream);
		server_stream = -1;
	}
	return;
}

/**
 * @brief
 * 	generate pending update bundles and send it to server
 *
 * @retval void
 */
void
send_pending_updates(void)
{
	int r_cnt;
	ruu *prused;
	int rh_cnt;
	ruu *prhused;
	int obits_cnt;
	ruu *obits;
	ruu *next;

	bundle_ruu(&r_cnt, &prused, &rh_cnt, &prhused, &obits_cnt, &obits);
	if (r_cnt > 0) {
		send_resc_used(IS_RESCUSED, r_cnt, prused);
		while (prused != NULL) {
			next = prused->ru_next;
			FREE_RUU(prused);
			prused = next;
		}
	}
	if (rh_cnt > 0) {
		send_resc_used(IS_RESCUSED_FROM_HOOK, rh_cnt, prhused);
		while (prhused != NULL) {
			next = prhused->ru_next;
			FREE_RUU(prhused);
			prhused = next;
		}
	}
	if (obits_cnt > 0) {
		send_resc_used(IS_JOBOBIT, obits_cnt, obits);
		while (obits != NULL) {
			next = obits->ru_next;
			/*
			 * Here, we reply to outstanding request
			 * this should come after obit sent
			 */
			if (obits->ru_pjob && obits->ru_pjob->ji_preq) {
				reply_ack(obits->ru_pjob->ji_preq);
				obits->ru_pjob->ji_preq = NULL;
			}
			FREE_RUU(obits);
			obits = next;
		}
	}
}
