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
 * @file	DIS_encode.c
 * 
 * @brief
 * DIS decode routines
 */

#include "batch_request.h"
#include "dis.h"

/**
 * @brief
 *      Decode PBS batch request to authenticate based on external (non-resv-port) mechanisms.
 *      The batch request contains type and the auth data.
 *
 * @param [in] sock socket connection
 * @param [in] preq PBS bath request
 * @return in
 * @retval 0 on success
 * @retval > 0 on failure
 */
int
decode_DIS_Authenticate(int sock, struct batch_request *preq)
{
	int rc;
	int len = 0;

	memset(preq->rq_ind.rq_auth.rq_auth_method, '\0', sizeof(preq->rq_ind.rq_auth.rq_auth_method));
	len = disrsi(sock, &rc);
	if (rc != DIS_SUCCESS)
		return (rc);
	if (len <= 0) {
		return DIS_PROTO;
	}
	rc = disrfst(sock, len, preq->rq_ind.rq_auth.rq_auth_method);
	if (rc != DIS_SUCCESS)
		return (rc);

	memset(preq->rq_ind.rq_auth.rq_encrypt_method, '\0', sizeof(preq->rq_ind.rq_auth.rq_encrypt_method));
	len = disrsi(sock, &rc);
	if (rc != DIS_SUCCESS)
		return (rc);
	if (len > 0) {
		rc = disrfst(sock, len, preq->rq_ind.rq_auth.rq_encrypt_method);
		if (rc != DIS_SUCCESS)
			return (rc);
	}

	preq->rq_ind.rq_auth.rq_port = disrui(sock, &rc);
	if (rc != DIS_SUCCESS)
		return (rc);

	return (rc);
}

/**
 *
 * @brief
 *	Decode the data items needed for a Copy Hook Filecopy request as:
 * 			u int	block sequence number
 *			u int	size of data in block
 *			string	hook file name
 *			cnt str	file data contents
 *
 * @param[in]	sock	- the connection to get data from.
 * @param[in]	preq	- a request structure
 *
 * @return	int
 * @retval	0 for success
 *		non-zero otherwise
 */

int
decode_DIS_CopyHookFile(int sock, struct batch_request *preq)
{
	int rc = 0;
	size_t amt;

	if (preq == NULL)
		return 0;

	preq->rq_ind.rq_hookfile.rq_data = 0;

	preq->rq_ind.rq_hookfile.rq_sequence = disrui(sock, &rc);
	if (rc)
		return rc;

	preq->rq_ind.rq_hookfile.rq_size = disrui(sock, &rc);
	if (rc)
		return rc;

	if ((rc = disrfst(sock, MAXPATHLEN + 1,
			  preq->rq_ind.rq_hookfile.rq_filename)) != 0)
		return rc;

	preq->rq_ind.rq_hookfile.rq_data = disrcs(sock, &amt, &rc);
	if ((amt != preq->rq_ind.rq_hookfile.rq_size) && (rc == 0))
		rc = DIS_EOD;
	if (rc) {
		if (preq->rq_ind.rq_hookfile.rq_data)
			(void) free(preq->rq_ind.rq_hookfile.rq_data);
		preq->rq_ind.rq_hookfile.rq_data = 0;
	}

	return rc;
}

/**
 * @brief
 *	decode a Job Credential batch request
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * NOTE:The batch_request structure must already exist (be allocated by the
 *      caller.   It is assumed that the header fields (protocol type,
 *      protocol version, request type, and user name) have already be decoded.
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_Cred(int sock, struct batch_request *preq)
{
	int rc;

	preq->rq_ind.rq_cred.rq_cred_data = NULL;

	rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_cred.rq_jobid);
	if (rc)
		return rc;

	rc = disrfst(sock, PBS_MAXUSER + 1, preq->rq_ind.rq_cred.rq_credid);
	if (rc)
		return rc;

	preq->rq_ind.rq_cred.rq_cred_type = disrui(sock, &rc);
	if (rc)
		return rc;

	preq->rq_ind.rq_cred.rq_cred_data = disrcs(sock, (size_t *) &preq->rq_ind.rq_cred.rq_cred_size, &rc);
	if (rc)
		return rc;

	preq->rq_ind.rq_cred.rq_cred_validity = disrul(sock, &rc);
	return rc;
}

/**
 * @brief
 *	Decode data item(s) needed for a Delete Hook File request.
 *
 *	Data item is:	string	hook  filename
 *			cnt str	data
 *
 * @param[in]		sock - communication channel
 * @param[in/out]	preq - request structure to fill in
 *
 * @return 	int
 * @retval 	0 for success
 * @retval 	non-zero otherwise
 */

int
decode_DIS_DelHookFile(int sock, struct batch_request *preq)
{
	int rc;

	if ((rc = disrfst(sock, MAXPATHLEN + 1,
			  preq->rq_ind.rq_hookfile.rq_filename)) != 0)
		return rc;

	return 0;
}

/**
 * @brief
 *	-decode a Delete Job Batch Request
 *
 * @par	Functionality:
 *	This function is used to decode the request for deletion of list of jobids.
 *
 *
 *      The batch_request structure must already exist (be allocated by the
 *      caller.   It is assumed that the header fields (protocol type,
 *      protocol version, request type, and user name) have already be decoded.
 *
 * @par	Data items are:\n
 *		unsigned int    command\n
 *              unsigned int    object type\n
 *              string          object name\n
 *              attropl         attributes
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_DelJobList(int sock, struct batch_request *preq)
{
	int rc;
	int count = 0;
	char **tmp_jobslist = NULL;
	int i = 0;

	preq->rq_ind.rq_deletejoblist.rq_count = disrui(sock, &rc);
	if (rc)
		return rc;

	count = preq->rq_ind.rq_deletejoblist.rq_count;

	tmp_jobslist = malloc((count + 1) * sizeof(char *));
	if (tmp_jobslist == NULL)
		return DIS_NOMALLOC;

	for (i = 0; i < count; i++) {
		tmp_jobslist[i] = disrst(sock, &rc);
		if (rc) {
			free(tmp_jobslist);
			return rc;
		}
	}
	tmp_jobslist[i] = NULL;

	preq->rq_ind.rq_deletejoblist.rq_jobslist = tmp_jobslist;
	preq->rq_ind.rq_deletejoblist.rq_resume = FALSE;

	return rc;
}

/**
 * @brief
 *	decode a Job Credential batch request
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * NOTE:The batch_request structure must already exist (be allocated by the
 *      caller.   It is assumed that the header fields (protocol type,
 *      protocol version, request type, and user name) have already be decoded.
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_JobCred(int sock, struct batch_request *preq)
{
	int rc;

	preq->rq_ind.rq_jobcred.rq_data = 0;
	preq->rq_ind.rq_jobcred.rq_type = disrui(sock, &rc);
	if (rc)
		return rc;

	preq->rq_ind.rq_jobcred.rq_data = disrcs(sock,
						 (size_t *) &preq->rq_ind.rq_jobcred.rq_size,
						 &rc);
	return rc;
}

/**
 * @brief -
 *	decode a Job Related Job File Move request
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 *
 * @par Data items are:
 *			u int -	block sequence number\n
 *		 	u int -  file type (stdout, stderr, ...)\n
 *		 	u int -  size of data in block\n
 *		 	string - job id\n
 *		 	cnt str - data\n
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_JobFile(int sock, struct batch_request *preq)
{
	int rc;
	size_t amt;

	preq->rq_ind.rq_jobfile.rq_data = 0;

	preq->rq_ind.rq_jobfile.rq_sequence = disrui(sock, &rc);
	if (rc)
		return rc;

	preq->rq_ind.rq_jobfile.rq_type = disrui(sock, &rc);
	if (rc)
		return rc;

	preq->rq_ind.rq_jobfile.rq_size = disrui(sock, &rc);
	if (rc)
		return rc;

	if ((rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_jobfile.rq_jobid)) != 0)
		return rc;

	preq->rq_ind.rq_jobfile.rq_data = disrcs(sock, &amt, &rc);
	if ((amt != preq->rq_ind.rq_jobfile.rq_size) && (rc == 0))
		rc = DIS_EOD;
	if (rc) {
		if (preq->rq_ind.rq_jobfile.rq_data)
			(void) free(preq->rq_ind.rq_jobfile.rq_data);
		preq->rq_ind.rq_jobfile.rq_data = 0;
	}

	return rc;
}

/**
 * @brief
 *	decode_DIS_JobId() - decode a Job ID string into a batch_request
 *
 * @par Functionality:
 *		This is used for the following batch requests:\n
 *              	Ready_to_Commit\n
 *              	Commit\n
 *              	Locate Job\n
 *              	Rerun Job
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_JobId(int sock, char *jobid)
{
	return (disrfst(sock, PBS_MAXSVRJOBID + 1, jobid));
}

/**
 * @brief
 *	-decode a Manager Batch Request
 *
 * @par	Functionality:
 *	This request is used for most operations where an object is being
 *      created, deleted, or altered.
 *
 *      The batch_request structure must already exist (be allocated by the
 *      caller.   It is assumed that the header fields (protocol type,
 *      protocol version, request type, and user name) have already be decoded.
 *
 * @par	Data items are:\n
 *		unsigned int    command\n
 *              unsigned int    object type\n
 *              string          object name\n
 *              attropl         attributes
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_Manage(int sock, struct batch_request *preq)
{
	int rc;

	CLEAR_HEAD(preq->rq_ind.rq_manager.rq_attr);
	preq->rq_ind.rq_manager.rq_cmd = disrui(sock, &rc);
	if (rc)
		return rc;
	preq->rq_ind.rq_manager.rq_objtype = disrui(sock, &rc);
	if (rc)
		return rc;
	rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_manager.rq_objname);
	if (rc)
		return rc;
	return (decode_DIS_svrattrl(sock, &preq->rq_ind.rq_manager.rq_attr));
}

/**
 * @brief Read the modify request for a reservation.
 *
 * @param[in] sock - connection identifier
 * @param[out] preq - batch_request that the information will be read into.
 *
 * @return 0 - on success
 * @return DIS error
 */
int
decode_DIS_ModifyResv(int sock, struct batch_request *preq)
{
	int rc = 0;

	CLEAR_HEAD(preq->rq_ind.rq_modify.rq_attr);
	preq->rq_ind.rq_modify.rq_objtype = disrui(sock, &rc);
	if (rc)
		return rc;
	rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_modify.rq_objname);
	if (rc)
		return rc;
	return (decode_DIS_svrattrl(sock, &preq->rq_ind.rq_modify.rq_attr));
}

/**
 * @brief -
 *	decode a Move Job batch request
 *	also used for an Order Job batch request
 *
 * @par	Functionality:
 *		The batch_request structure must already exist (be allocated by the
 *		caller.   It is assumed that the header fields (protocol type,
 *		protocol version, request type, and user name) have already be decoded.
 *
 * @par	 Data items are:
 *		string          job id\n
 *		string          destination
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_MoveJob(int sock, struct batch_request *preq)
{
	int rc;

	rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_move.rq_jid);
	if (rc)
		return rc;

	rc = disrfst(sock, PBS_MAXDEST + 1, preq->rq_ind.rq_move.rq_destin);

	return rc;
}

/**
 * @brief-
 *	decode a Message Job batch request
 *
 * @par	Functionality:
 *		The batch_request structure must already exist (be allocated by the
 *      	caller.   It is assumed that the header fields (protocol type,
 *      	protocol version, request type, and user name) have already be decoded.
 *
 * @par	 Data items are:
 *		string          job id
 *		unsigned int    which file
 *		string          the message
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_MessageJob(int sock, struct batch_request *preq)
{
	int rc;

	preq->rq_ind.rq_message.rq_text = 0;

	rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_message.rq_jid);
	if (rc)
		return rc;

	preq->rq_ind.rq_message.rq_file = disrui(sock, &rc);
	if (rc)
		return rc;

	preq->rq_ind.rq_message.rq_text = disrst(sock, &rc);
	return rc;
}

/**
 * @brief Read the preempt multiple jobs request.
 *
 * @param[in] sock - connection identifier
 * @param[out] preq - batch_request that the information will be read into.
 *
 * @return 0 - on success
 * @return DIS error
 */
int
decode_DIS_PreemptJobs(int sock, struct batch_request *preq)
{
	int rc = 0;
	int i = 0;
	int count = 0;
	preempt_job_info *ppj = NULL;

	preq->rq_ind.rq_preempt.count = disrui(sock, &rc);
	if (rc)
		return rc;

	count = preq->rq_ind.rq_preempt.count;

	ppj = calloc(sizeof(struct preempt_job_info), count);
	if (ppj == NULL)
		return DIS_NOMALLOC;

	for (i = 0; i < count; i++) {
		if ((rc = disrfst(sock, PBS_MAXSVRJOBID + 1, ppj[i].job_id))) {
			free(ppj);
			return rc;
		}
	}

	preq->rq_ind.rq_preempt.ppj_list = ppj;

	return rc;
}

/**
 * @brief -
 *	decode a Queue Job Batch Request
 *
 * @par	Functionality:
 *		string  job id\n
 *		string  destination\n
 *		list of attributes (attropl)
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_QueueJob(int sock, struct batch_request *preq)
{
	int rc;

	CLEAR_HEAD(preq->rq_ind.rq_queuejob.rq_attr);
	rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_queuejob.rq_jid);
	if (rc)
		return rc;

	rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_queuejob.rq_destin);
	if (rc)
		return rc;

	return (decode_DIS_svrattrl(sock, &preq->rq_ind.rq_queuejob.rq_attr));
}

/**
 * @brief -
 *	decode a Register Dependency Batch Request
 *
 * @par	Functionality:
 *		The batch_request structure must already exist (be allocated by the
 *      	caller.   It is assumed that the header fields (protocol type,
 *      	protocol version, request type, and user name) have already be decoded
 *
 * @par	Data items are:
 *		string          job owner\n
 *		string          parent job id\n
 *		string          child job id\n
 *		unsigned int    dependency type\n
 *		unsigned int    operation\n
 *		signed long     cost\n
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_Register(int sock, struct batch_request *preq)
{
	int rc;

	rc = disrfst(sock, PBS_MAXUSER, preq->rq_ind.rq_register.rq_owner);
	if (rc)
		return rc;
	rc = disrfst(sock, PBS_MAXSVRJOBID, preq->rq_ind.rq_register.rq_parent);
	if (rc)
		return rc;
	rc = disrfst(sock, PBS_MAXCLTJOBID, preq->rq_ind.rq_register.rq_child);
	if (rc)
		return rc;
	preq->rq_ind.rq_register.rq_dependtype = disrui(sock, &rc);

	if (rc)
		return rc;

	preq->rq_ind.rq_register.rq_op = disrui(sock, &rc);
	if (rc)
		return rc;

	preq->rq_ind.rq_register.rq_cost = disrsl(sock, &rc);

	return rc;
}

/**
 * @brief -
 *	decode a batch_request Extend string
 *
 * @par	Functionality:
 *		The batch_request structure must already exist (be allocated by the
 *      	caller.   It is assumed that the header fields (protocol type,
 *		protocol version, request type, and user name) and the request body
 *		have already be decoded.
 *
 * Note:The next field is an unsigned integer which is 1 if there is an
 *      extension string and zero if not.
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_ReqExtend(int sock, struct batch_request *preq)
{
	int i;
	int rc;

	i = disrui(sock, &rc); /* indicates if an extension exists */

	if (rc == 0) {
		if (i != 0) {
			preq->rq_extend = disrst(sock, &rc);
		}
	}
	return (rc);
}

/**
 * @brief-
 *	Decode the Request Header Fields
 *      common to all requests
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return	int
 * @retval	-1    on EOF (end of file on first read only)
 * @retval	0    on success
 * @retval	>0    a DIS error return, see dis.h
 *
 */

int
decode_DIS_ReqHdr(int sock, struct batch_request *preq, int *proto_type, int *proto_ver)
{
	int rc;

	*proto_type = disrui(sock, &rc);
	if (rc) {
		return rc;
	}
	if (*proto_type != PBS_BATCH_PROT_TYPE)
		return DIS_PROTO;
	*proto_ver = disrui(sock, &rc);
	if (rc) {
		return rc;
	}

	preq->rq_type = disrui(sock, &rc);
	if (rc) {
		return rc;
	}

	return (disrfst(sock, PBS_MAXUSER + 1, preq->rq_user));
}

/**
 * @brief-
 *	decode a resource request
 *
 * @par	Functionality:
 *		Used for resource query, resource reserver, resource free.
 *
 *		The batch_request structure must already exist (be allocated by the
 *		caller.   It is assumed that the header fields (protocol type,
 *		protocol version, request type, and user name) have been decoded.
 *
 * @par	Data items are:\n
 *		signed int	resource handle\n
 *		unsigned int	count of resource queries\n
 *	followed by that number of:\n
 *		string		resource list
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_Rescl(int sock, struct batch_request *preq)
{
	int ct;
	int i;
	char **ppc;
	int rc;

	/* first, the resource handle (even if not used in request) */

	preq->rq_ind.rq_rescq.rq_rhandle = disrsi(sock, &rc);
	if (rc)
		return rc;

	/* next need to know how many query strings */

	ct = disrui(sock, &rc);
	if (rc)
		return rc;
	preq->rq_ind.rq_rescq.rq_num = ct;
	if (ct) {
		if ((ppc = (char **) malloc(ct * sizeof(char *))) == 0)
			return PBSE_RMSYSTEM;

		for (i = 0; i < ct; i++)
			*(ppc + i) = NULL;

		preq->rq_ind.rq_rescq.rq_list = ppc;
		for (i = 0; i < ct; i++) {
			*(ppc + i) = disrst(sock, &rc);
			if (rc)
				break;
		}
	}

	return rc;
}

/**
 * @brief-
 *	decode a Run Job batch request
 *
 * @par	Functionality:
 *		The batch_request structure must already exist (be allocated by the
 *      	caller.   It is assumed that the header fields (protocol type,
 *      	protocol version, request type, and user name) have already be decoded.
 *
 * @par	Data items are:\n
 *		string          job id\n
 *		string          destination\n
 *		unsigned int    resource_handle\n
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_Run(int sock, struct batch_request *preq)
{
	int rc;

	/* job id */
	rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_run.rq_jid);
	if (rc)
		return rc;

	/* variable length list of vnodes (destination) */
	preq->rq_ind.rq_run.rq_destin = disrst(sock, &rc);
	if (rc)
		return rc;

	/* an optional flag, used by reservations */
	preq->rq_ind.rq_run.rq_resch = disrul(sock, &rc);
	return rc;
}

/**
 * @brief-
 *	decode a Server Shut Down batch request
 *
 * @par	Functionality:
 *		The batch_request structure must already exist (be allocated by the
 *      	caller.   It is assumed that the header fields (protocol type,
 *		protocol version, request type, and user name) have already be decoded.
 *
 * @par	 Data items are:\n
 *		u int           manner
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_ShutDown(int sock, struct batch_request *preq)
{
	int rc;

	preq->rq_ind.rq_shutdown = disrui(sock, &rc);

	return rc;
}

/**
 * @brief-
 *	decode a Signal Job batch request
 *
 * @par	Functionality:
 *		The batch_request structure must already exist (be allocated by the
 *      	caller.   It is assumed that the header fields (protocol type,
 *      	protocol version, request type, and user name) have already be decoded.
 *
 * @par	Data items are:\n
 *		string          job id\n
 *		string          signal (name)
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_SignalJob(int sock, struct batch_request *preq)
{
	int rc;

	rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_signal.rq_jid);
	if (rc)
		return rc;

	rc = disrfst(sock, PBS_SIGNAMESZ + 1, preq->rq_ind.rq_signal.rq_signame);
	return rc;
}

/**
 * @brief
 *	Decode a Status batch request
 *
 * @par
 *	The batch_request structure must already exist (be allocated by the
 *	caller).   It is assumed that the header fields (protocol type,
 *	protocol version, request type, and user name) have already be decoded.
 *
 * @param[in]     sock - socket handle from which to read.
 * @param[in,out] preq - pointer to the batch request structure. The following
 *		elements of the rq_ind.rq_status union are updated:
 *		rq_id     - object id, a variable length string.
 *		rq_status - the linked list of attribute structures
 *
 * @return int
 * @retval 0 - request read and decoded successfully.
 * @retval non-zero - DIS decode error.
 */

int
decode_DIS_Status(int sock, struct batch_request *preq)
{
	int rc;
	size_t nchars = 0;

	preq->rq_ind.rq_status.rq_id = NULL;

	CLEAR_HEAD(preq->rq_ind.rq_status.rq_attr);

	/*
	 * call the disrcs function to allocate and return a string of all ids
	 * freed in free_br()
	 */
	preq->rq_ind.rq_status.rq_id = disrcs(sock, &nchars, &rc);
	if (rc)
		return rc;

	rc = decode_DIS_svrattrl(sock, &preq->rq_ind.rq_status.rq_attr);
	return rc;
}

/**
 * @brief-
 *	decode a Track Job batch request
 *
 * @par	NOTE:
 *	The batch_request structure must already exist (be allocated by the
 *      caller.   It is assumed that the header fields (protocol type,
 *      protocol version, request type, and user name) have already be decoded.
 *
 * @par	 Data items are:\n
 *		string          job id\n
 *		unsigned int    hopcount\n
 *		string          location\n
 *		u char          state\n
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_TrackJob(int sock, struct batch_request *preq)
{
	int rc;

	rc = disrfst(sock, PBS_MAXSVRJOBID + 1, preq->rq_ind.rq_track.rq_jid);
	if (rc)
		return rc;

	preq->rq_ind.rq_track.rq_hopcount = disrui(sock, &rc);
	if (rc)
		return rc;

	rc = disrfst(sock, PBS_MAXDEST + 1, preq->rq_ind.rq_track.rq_location);
	if (rc)
		return rc;

	preq->rq_ind.rq_track.rq_state[0] = disruc(sock, &rc);
	return rc;
}

/**
 * @brief-
 *	decode a User Credential batch request
 *
 * @par	NOTE:
 *	The batch_request structure must already exist (be allocated by the
 *	caller.   It is assumed that the header fields (protocol type,
 *	protocol version, request type, and user name) have already be decoded.
 *
 * @par	Data items are:\n
 *		string          user whose credential is being set\n
 *		unsigned int	credential type\n
 *		counted string	the credential data
 *
 * @param[in] sock - socket descriptor
 * @param[out] preq - pointer to batch_request structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_UserCred(int sock, struct batch_request *preq)
{
	int rc;

	rc = disrfst(sock, PBS_MAXUSER + 1, preq->rq_ind.rq_usercred.rq_user);
	if (rc)
		return rc;

	preq->rq_ind.rq_usercred.rq_type = disrui(sock, &rc);
	if (rc)
		return rc;

	preq->rq_ind.rq_usercred.rq_data = 0;
	preq->rq_ind.rq_usercred.rq_data = disrcs(sock,
						  (size_t *) &preq->rq_ind.rq_usercred.rq_size,
						  &rc);
	return rc;
}

/**
 * @brief
 *	decode into a list of PBS API "attrl" structures
 *
 *	The space for the attrl structures is allocated as needed.
 *
 *	The first item is a unsigned integer, a count of the
 *	number of attrl entries in the linked list.  This is encoded
 *	even when there are no entries in the list.
 *
 *	Each individual entry is encoded as:
 *		u int	size of the three strings (name, resource, value)
 *			including the terminating nulls, see dec_svrattrl.c
 *		string	attribute name
 *		u int	1 or 0 if resource name does or does not follow
 *		string	resource name (if one)
 *		string  value of attribute/resource
 *		u int	"op" of attrlop (also flag of svrattrl)
 *
 *	Note, the encoding of a attrl is the same as the encoding of
 *	the pbs_ifl.h structures "attropl" and the server struct svrattrl.
 *	Any one of the three forms can be decoded into any of the three with
 *	the possible loss of the "flags" field (which is the "op" of the
 *	attrlop).
 *
 * @param[in]   sock - socket descriptor
 * @param[in]   ppatt - pointer to list of attributes
 *
 * @return int
 * @retval 0 on SUCCESS
 * @retval >0 on failure
 */

int
decode_DIS_attrl(int sock, struct attrl **ppatt)
{
	int hasresc;
	int i;
	unsigned int numpat;
	struct attrl *pat = 0;
	struct attrl *patprior = 0;
	int rc;

	numpat = disrui(sock, &rc);
	if (rc)
		return rc;

	for (i = 0; i < numpat; ++i) {

		(void) disrui(sock, &rc);
		if (rc)
			break;

		pat = new_attrl();
		if (pat == 0)
			return DIS_NOMALLOC;

		pat->name = disrst(sock, &rc);
		if (rc)
			break;

		hasresc = disrui(sock, &rc);
		if (rc)
			break;
		if (hasresc) {
			pat->resource = disrst(sock, &rc);
			if (rc)
				break;
		}

		pat->value = disrst(sock, &rc);
		if (rc)
			break;

		pat->op = (enum batch_op) disrui(sock, &rc);
		if (rc)
			break;

		if (i == 0) {
			/* first one, link to passing in pointer */
			*ppatt = pat;
		} else {
			patprior->next = pat;
		}
		patprior = pat;
	}

	if (rc)
		PBS_free_aopl((struct attropl *) pat);
	return rc;
}

/**
 * @brief
 *	decode into a list of PBS API "attropl" structures
 *
 *	The space for the attropl structures is allocated as needed.
 *
 *	The first item is a unsigned integer, a count of the
 *	number of attropl entries in the linked list.  This is encoded
 *	even when there are no entries in the list.
 *
 *	Each individual entry is encoded as:
 *		u int	size of the three strings (name, resource, value)
 *			including the terminating nulls, see dec_svrattrl.c
 *		string	attribute name
 *		u int	1 or 0 if resource name does or does not follow
 *		string	resource name (if one)
 *		string  value of attribute/resource
 *		u int	"op" of attrlop (also flag of svrattrl)
 *
 *	Note, the encoding of a attropl is the same as the encoding of
 *	the pbs_ifl.h structures "attrl" and the server struct svrattrl.
 *	Any one of the three forms can be decoded into any of the three with
 *	the possible loss of the "flags" field (which is the "op" of the
 *	attrlop).
 *
 * @param[in]   sock - socket descriptor
 * @param[in]   ppatt - pointer to list of attributes
 *
 * @return int
 * @retval 0 on SUCCESS
 * @retval >0 on failure
 */

int
decode_DIS_attropl(int sock, struct attropl **ppatt)
{
	int hasresc;
	int i;
	unsigned int numpat;
	struct attropl *pat = 0;
	struct attropl *patprior = 0;
	int rc;

	numpat = disrui(sock, &rc);
	if (rc)
		return rc;

	for (i = 0; i < numpat; ++i) {

		(void) disrui(sock, &rc);
		if (rc)
			break;

		pat = malloc(sizeof(struct attropl));
		if (pat == 0)
			return DIS_NOMALLOC;

		pat->next = NULL;
		pat->name = NULL;
		pat->resource = NULL;
		pat->value = NULL;

		pat->name = disrst(sock, &rc);
		if (rc)
			break;

		hasresc = disrui(sock, &rc);
		if (rc)
			break;
		if (hasresc) {
			pat->resource = disrst(sock, &rc);
			if (rc)
				break;
		}

		pat->value = disrst(sock, &rc);
		if (rc)
			break;

		pat->op = (enum batch_op) disrui(sock, &rc);
		if (rc)
			break;

		if (i == 0) {
			/* first one, link to passing in pointer */
			*ppatt = pat;
		} else {
			patprior->next = pat;
		}
		patprior = pat;
	}

	if (rc)
		PBS_free_aopl(pat);
	return rc;
}

/**
 * @brief-
 *	 decode into a list of server "svrattrl" structures
 *
 * @par	Functionality:
 *		The space for the svrattrl structures is allocated as needed.
 *
 *      The first item is a unsigned integer, a count of the
 *      number of svrattrl entries in the linked list.  This is encoded
 *      even when there are no entries in the list.
 *
 * @par	Each individual entry is encoded as:\n
 *			u int	- size of the three strings (name, resource, value)
 *                      	  including the terminating nulls\n
 *			string  - attribute name\n
 *			u int   - 1 or 0 if resource name does or does not follow\n
 *			string  - resource name (if one)\n
 *			string  - value of attribute/resource\n
 *			u int   - "op" of attrlop\n
 *
 * NOTE:
 *	the encoding of a svrattrl is the same as the encoding of
 *      the pbs_ifl.h structures "attrl" and "attropl".  Any one of
 *      the three forms can be decoded into any of the three with the
 *      possible loss of the "flags" field (which is the "op" of the attrlop).
 *
 * @param[in] sock - socket descriptor
 * @param[in] phead - head pointer to list entry list sub-structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
decode_DIS_svrattrl(int sock, pbs_list_head *phead)
{
	int i;
	unsigned int hasresc;
	size_t ls;
	unsigned int data_len;
	unsigned int numattr;
	svrattrl *psvrat;
	int rc;
	size_t tsize;

	numattr = disrui(sock, &rc); /* number of attributes in set */
	if (rc)
		return rc;

	for (i = 0; i < numattr; ++i) {

		data_len = disrui(sock, &rc); /* here it is used */
		if (rc)
			return rc;

		tsize = sizeof(svrattrl) + data_len;
		if ((psvrat = (svrattrl *) malloc(tsize)) == 0)
			return DIS_NOMALLOC;

		CLEAR_LINK(psvrat->al_link);
		psvrat->al_sister = NULL;
		psvrat->al_atopl.next = 0;
		psvrat->al_tsize = tsize;
		psvrat->al_name = (char *) psvrat + sizeof(svrattrl);
		psvrat->al_resc = 0;
		psvrat->al_value = 0;
		psvrat->al_nameln = 0;
		psvrat->al_rescln = 0;
		psvrat->al_valln = 0;
		psvrat->al_flags = 0;
		psvrat->al_refct = 1;

		if ((rc = disrfcs(sock, &ls, data_len, psvrat->al_name)) != 0)
			break;
		*(psvrat->al_name + ls++) = '\0';
		psvrat->al_nameln = (int) ls;
		data_len -= ls;

		hasresc = disrui(sock, &rc);
		if (rc)
			break;
		if (hasresc) {
			psvrat->al_resc = psvrat->al_name + ls;
			rc = disrfcs(sock, &ls, data_len, psvrat->al_resc);
			if (rc)
				break;
			*(psvrat->al_resc + ls++) = '\0';
			psvrat->al_rescln = (int) ls;
			data_len -= ls;
		}

		psvrat->al_value = psvrat->al_name + psvrat->al_nameln +
				   psvrat->al_rescln;
		if ((rc = disrfcs(sock, &ls, data_len, psvrat->al_value)) != 0)
			break;
		*(psvrat->al_value + ls++) = '\0';
		psvrat->al_valln = (int) ls;

		psvrat->al_op = (enum batch_op) disrui(sock, &rc);
		if (rc)
			break;

		append_link(phead, &psvrat->al_link, psvrat);
	}

	if (rc) {
		(void) free(psvrat);
	}

	return (rc);
}
