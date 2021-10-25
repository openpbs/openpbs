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
 * DIS encode routines
 */

#include "batch_request.h"
#include "dis.h"

/**
 * @brief encode the Preempt Jobs request for sending to the server.
 *
 * @param[in] sock - socket descriptor for the connection.
 * @param[in] jobs - list of job ids.
 *
 * @return - error code while writing data to the socket.
 */
int
encode_DIS_JobsList(int sock, char **jobs_list, int numofjobs)
{
	int i = 0;
	int rc = 0;
	int count = 0;

	if (numofjobs == -1)
		for (; jobs_list[count]; count++)
			;
	else
		count = numofjobs;

	if (((rc = diswui(sock, count)) != 0))
		return rc;

	for (i = 0; i < count; i++)
		if ((rc = diswst(sock, jobs_list[i])) != 0)
			return rc;

	return rc;
}

/**
 *
 * @brief
 *	Encode a Copy Hook File request.
 *	Send over 'sock' the data items:
 *			u int	block sequence number
 *			u int	file type (stdout, stderr, ...)
 *			u int	size of data in block
 *			string	hook file name
 *			cnt str	data
 *
 * @param[in]	sock -  the communication end point.
 * @param[in]	seq -	sequence number of the current block of data being sent
 * @param[in] 	buf - block of data to be sent
 * @param[in]	len - # of characters in 'buf'
 * @param[in]	filename - name of the hook file being sent.
 *
 * @return 	int
 * @retval 	0 for success
 * @retval	non-zero otherwise
 */

int
encode_DIS_CopyHookFile(int sock, int seq, const char *buf, int len, const char *filename)
{
	int rc;

	if ((rc = diswui(sock, seq) != 0) ||
	    (rc = diswui(sock, len) != 0) ||
	    (rc = diswst(sock, filename) != 0) ||
	    (rc = diswcs(sock, buf, len) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *	-encode a Copy Files Dependency Batch Request
 *
 * @param[in] sock - socket descriptor
 * @param[in] preq - pointer to batch_request
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
int
encode_DIS_CopyFiles(int sock, struct batch_request *preq)
{
	int pair_ct = 0;
	char *nullstr = "";
	struct rqfpair *ppair;
	int rc;

	ppair = (struct rqfpair *) GET_NEXT(preq->rq_ind.rq_cpyfile.rq_pair);
	while (ppair) {
		++pair_ct;
		ppair = (struct rqfpair *) GET_NEXT(ppair->fp_link);
	}

	if ((rc = diswst(sock, preq->rq_ind.rq_cpyfile.rq_jobid) != 0) ||
	    (rc = diswst(sock, preq->rq_ind.rq_cpyfile.rq_owner) != 0) ||
	    (rc = diswst(sock, preq->rq_ind.rq_cpyfile.rq_user) != 0) ||
	    (rc = diswst(sock, preq->rq_ind.rq_cpyfile.rq_group) != 0) ||
	    (rc = diswui(sock, preq->rq_ind.rq_cpyfile.rq_dir) != 0))
		return rc;

	if ((rc = diswui(sock, pair_ct) != 0))
		return rc;
	ppair = (struct rqfpair *) GET_NEXT(preq->rq_ind.rq_cpyfile.rq_pair);
	while (ppair) {
		if (ppair->fp_rmt == NULL)
			ppair->fp_rmt = nullstr;
		if ((rc = diswui(sock, ppair->fp_flag) != 0) ||
		    (rc = diswst(sock, ppair->fp_local) != 0) ||
		    (rc = diswst(sock, ppair->fp_rmt) != 0))
			return rc;
		ppair = (struct rqfpair *) GET_NEXT(ppair->fp_link);
	}

	return 0;
}

/**
 * @brief
 * 	-encode_DIS_CopyFiles_Cred() - encode a Copy Files with Credential Dependency
 *	Batch Request
 *
 * @par Note:
 *	This request is used by the server ONLY; its input is a server
 *	batch request structure.
 *
 * @param[in] sock - socket descriptor
 * @param[in] preq - pointer to batch request
 *
 * @par	Data items are:\n
 *		string		job id\n
 *		string		job owner(may be null)\n
 *		string		execution user name\n
 *		string		execution group name(may be null)\n
 *		unsigned int	direction & job_dir_enable flag\n
 *		unsigned int	count of file pairs in set\n
 *	set of	file pairs:\n
 *		unsigned int	flag\n
 *		string		local path name\n
 *		string		remote path name (may be null)\n
 *		unsigned int	credential type\n
 *		unsigned int	credential length (bytes)\n
 *		byte string	credential\n
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
int
encode_DIS_CopyFiles_Cred(int sock, struct batch_request *preq)
{
	int pair_ct = 0;
	char *nullstr = "";
	struct rqfpair *ppair;
	int rc;
	size_t clen;
	struct rq_cpyfile *rcpyf;

	clen = (size_t) preq->rq_ind.rq_cpyfile_cred.rq_credlen;
	rcpyf = &preq->rq_ind.rq_cpyfile_cred.rq_copyfile;
	ppair = (struct rqfpair *) GET_NEXT(rcpyf->rq_pair);

	while (ppair) {
		++pair_ct;
		ppair = (struct rqfpair *) GET_NEXT(ppair->fp_link);
	}

	if ((rc = diswst(sock, rcpyf->rq_jobid) != 0) ||
	    (rc = diswst(sock, rcpyf->rq_owner) != 0) ||
	    (rc = diswst(sock, rcpyf->rq_user) != 0) ||
	    (rc = diswst(sock, rcpyf->rq_group) != 0) ||
	    (rc = diswui(sock, rcpyf->rq_dir) != 0))
		return rc;

	if ((rc = diswui(sock, pair_ct) != 0))
		return rc;
	ppair = (struct rqfpair *) GET_NEXT(rcpyf->rq_pair);
	while (ppair) {
		if (ppair->fp_rmt == NULL)
			ppair->fp_rmt = nullstr;
		if ((rc = diswui(sock, ppair->fp_flag) != 0) ||
		    (rc = diswst(sock, ppair->fp_local) != 0) ||
		    (rc = diswst(sock, ppair->fp_rmt) != 0))
			return rc;
		ppair = (struct rqfpair *) GET_NEXT(ppair->fp_link);
	}

	rc = diswui(sock, preq->rq_ind.rq_cpyfile_cred.rq_credtype);
	if (rc != 0)
		return rc;
	rc = diswcs(sock, preq->rq_ind.rq_cpyfile_cred.rq_pcred, clen);
	if (rc != 0)
		return rc;

	return 0;
}

/**
 *
 * @brief
 *	Encode a Hook Delete File request
 *	Send over to 'sock' the data item:
 *			string	hook filename
 * @param[in]	sock - communication channel
 * @param[in]	filename - hook filename
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */

int
encode_DIS_DelHookFile(int sock, const char *filename)
{
	int rc;

	if ((rc = diswst(sock, filename) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *	-encode a Job Credential Batch Request
 *
 * @par	Data items are:\n
 *		char		job id
 *		char		cred id (e.g principal)
 *		int	credential type
 *		counted string	the message
 *		long		credential validity
 *
 * @param[in] sock - socket descriptor
 * @param[in] jobid - job id
 * @param[in] owner - cred id (e.g. principal)
 * @param[in] type - cred type
 * @param[in] data - credential
 * @param[in] size - length of credential
 * @param[in] long - credential validity
 *
 * @return	int
 * @retval      0 for success
 * @retval      non-zero otherwise
 */

int
encode_DIS_Cred(int sock, char *jobid, char *credid, int type, char *data, size_t size, long validity)
{
	int rc;

	if ((rc = diswst(sock, jobid) != 0) ||
	    (rc = diswst(sock, credid) != 0) ||
	    (rc = diswui(sock, type) != 0) ||
	    (rc = diswcs(sock, data, size) != 0) ||
	    (rc = diswul(sock, validity) != 0))
		return rc;

	return rc;
}

/**
 * @brief
 *	-encode a Job Credential Batch Request
 *
 * @par	Data items are:\n
 *		unsigned int    Credential type\n
 *		string          the credential (octet array)\n
 *
 * @param[in] sock - socket descriptor
 * @param[in] type - cred type
 * @param[in] cred - credential
 * @param[in] len - length of credentials
 *
 * @return	int
 * @retval      0 for success
 * @retval      non-zero otherwise
 */

int
encode_DIS_JobCred(int sock, int type, const char *cred, int len)
{
	int rc;

	if ((rc = diswui(sock, type)) != 0)
		return rc;
	rc = diswcs(sock, cred, (size_t) len);

	return rc;
}

/**
 * @brief
 *	-encode a Job Releated File
 *
 * @param[in]   sock -  the communication end point.
 * @param[in]   seq -   sequence number of the current block of data being sent
 * @param[in]   buf - block of data to be sent
 * @param[in]   len - # of characters in 'buf'
 * @param[in]	jobid - job id
 * @param[in] 	which - file type
 *
 * @return      int
 * @retval      0 for success
 * @retval      non-zero otherwise
 */

int
encode_DIS_JobFile(int sock, int seq, const char *buf, int len, const char *jobid, int which)
{
	int rc;

	if (jobid == NULL)
		jobid = "";
	if ((rc = diswui(sock, seq) != 0) ||
	    (rc = diswui(sock, which) != 0) ||
	    (rc = diswui(sock, len) != 0) ||
	    (rc = diswst(sock, jobid) != 0) ||
	    (rc = diswcs(sock, buf, len) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *      - decode a Job ID string into a batch_request
 *
 * @par Functionality:
 *              This is used for the following batch requests:\n
 *                      Ready_to_Commit\n
 *                      Commit\n
 *                      Locate Job\n
 *                      Rerun Job
 *
 * @param[in] sock - socket descriptor
 * @param[in] jobid - job id
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_JobId(int sock, const char *jobid)
{
	return (diswst(sock, jobid));
}

/**
 * @brief
 *	-encode a Manager Batch Request
 *
 * @par	Functionality:
 *		This request is used for most operations where an object is being
 *      	created, deleted, or altered.
 *
 * @param[in] sock - socket descriptor
 * @param[in] command - command type
 * @param[in] objtype - object type
 * @param[in] objname - object name
 * @param[in] aoplp - pointer to attropl structure(list)
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_Manage(int sock, int command, int objtype, const char *objname, struct attropl *aoplp)
{
	int rc;

	if ((rc = diswui(sock, command) != 0) ||
	    (rc = diswui(sock, objtype) != 0) ||
	    (rc = diswst(sock, objname) != 0))
		return rc;

	return (encode_DIS_attropl(sock, aoplp));
}

/**
 * @brief encode the Modify Reservation request for sending to the server.
 *
 * @param[in] sock - socket descriptor for the connection.
 * @param[in] resv_id - Reservation identifier of the reservation that would be modified.
 * @param[in] aoplp - list of attributes that will be modified.
 *
 * @return - error code while writing data to the socket.
 */
int
encode_DIS_ModifyResv(int sock, const char *resv_id, struct attropl *aoplp)
{
	int rc = 0;

	if (resv_id == NULL)
		resv_id = "";

	if (((rc = diswui(sock, MGR_OBJ_RESV)) != 0) ||
	    ((rc = diswst(sock, resv_id)) != 0))
		return rc;

	return (encode_DIS_attropl(sock, aoplp));
}

/**
 * @brief
 *	-encode a Move Job Batch Request
 *	also used for an Order Job Batch Request
 *
 * @param[in] sock - socket descriptor
 * @param[in] jobid - job id to be moved
 * @param[in] destin - destination to which job to be moved
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_MoveJob(int sock, const char *jobid, const char *destin)
{
	int rc;

	if ((rc = diswst(sock, jobid) != 0) ||
	    (rc = diswst(sock, destin) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *	- encode a Message Job Batch Request
 *
 * @param[in] sock - socket descriptor
 * @param[in] jobid - job id
 * @param[in] fileopt - which file
 * @param[in] msg - msg to be encoded
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_MessageJob(int sock, const char *jobid, int fileopt, const char *msg)
{
	int rc;

	if ((rc = diswst(sock, jobid) != 0) ||
	    (rc = diswui(sock, fileopt) != 0) ||
	    (rc = diswst(sock, msg) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *	-Write a python spawn request onto the wire.
 *	Each of the argv and envp arrays is sent by writing a counted
 *	string followed by a zero length string ("").  They are read
 *	by the function read_carray() in dec_MsgJob.c
 *
 * @param[in] sock - socket descriptor
 * @param[in] jobid - job id
 * @param[in] argv - pointer to argument list
 * @param[in] envp - pointer to environment variable
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */
int
encode_DIS_PySpawn(int sock, const char *jobid, char **argv, char **envp)
{
	int rc, i;
	char *cp;

	if ((rc = diswst(sock, jobid)) != DIS_SUCCESS)
		return rc;

	if (argv != NULL) {
		for (i = 0; (cp = argv[i]) != NULL; i++) {
			if ((rc = diswcs(sock, cp, strlen(cp))) != DIS_SUCCESS)
				return rc;
		}
	}
	if ((rc = diswcs(sock, "", 0)) != DIS_SUCCESS)
		return rc;

	if (envp != NULL) {
		for (i = 0; (cp = envp[i]) != NULL; i++) {
			if ((rc = diswcs(sock, cp, strlen(cp))) != DIS_SUCCESS)
				return rc;
		}
	}
	rc = diswcs(sock, "", 0);

	return rc;
}

int
encode_DIS_RelnodesJob(int sock, const char *jobid, const char *node_list)
{
	int rc;

	if ((rc = diswst(sock, jobid) != 0) ||
	    (rc = diswst(sock, node_list) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *	-encode a Queue Job Batch Request
 *
 * @par	Functionality:
 *		This request is used for the first step in submitting a job, sending
 *      	the job attributes.
 *
 * @param[in] sock - socket descriptor
 * @param[in] jobid - job id
 * @param[in] destin - destination queue name
 * @param[in] aoplp - pointer to attropl structure(list)
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_QueueJob(int sock, char *jobid, const char *destin, struct attropl *aoplp)
{
	int rc;

	if (jobid == NULL)
		jobid = "";
	if (destin == NULL)
		destin = "";

	if ((rc = diswst(sock, jobid) != 0) ||
	    (rc = diswst(sock, destin) != 0))
		return rc;

	return (encode_DIS_attropl(sock, aoplp));
}

/**
 * @brief
 *      -encode a Register Dependency Batch Request
 *
 * @par Functionality:
 *       	This request is used by the server ONLY; its input is a server
 *      	batch request structure.
 *
 * @par Data items are:
 *              string          job owner\n
 *              string          parent job id\n
 *              string          child job id\n
 *              unsigned int    dependency type\n
 *              unsigned int    operation\n
 *              signed long     cost\n
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
encode_DIS_Register(int sock, struct batch_request *preq)
{
	int rc;

	if ((rc = diswst(sock, preq->rq_ind.rq_register.rq_owner) != 0) ||
	    (rc = diswst(sock, preq->rq_ind.rq_register.rq_parent) != 0) ||
	    (rc = diswst(sock, preq->rq_ind.rq_register.rq_child) != 0) ||
	    (rc = diswui(sock, preq->rq_ind.rq_register.rq_dependtype) != 0) ||
	    (rc = diswui(sock, preq->rq_ind.rq_register.rq_op) != 0) ||
	    (rc = diswsl(sock, preq->rq_ind.rq_register.rq_cost) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *	-write an extension to a Batch Request
 *
 * @par	The extension is in two parts:
 *		unsigned integer - 1 if an extension string follows, 0 if not\n
 *		character string - if 1 above
 *
 * @param[in] sock - socket descriptor
 * @param[in] extend - string which used as extension for req
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_ReqExtend(int sock, const char *extend)
{
	int rc;

	if ((extend == NULL) || (*extend == '\0')) {
		rc = diswui(sock, 0);
	} else {
		if ((rc = diswui(sock, 1)) == 0) {
			rc = diswst(sock, extend);
		}
	}

	return rc;
}

/**
 * @brief
 *	-encode a Request Header
 *
 * @param[in] sock - socket descriptor
 * @param[in] reqt - request type
 * @param[in] user - user name
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_ReqHdr(int sock, int reqt, const char *user)
{
	int rc;

	if ((rc = diswui(sock, PBS_BATCH_PROT_TYPE)) ||
	    (rc = diswui(sock, PBS_BATCH_PROT_VER)) ||
	    (rc = diswui(sock, reqt)) ||
	    (rc = diswst(sock, user))) {
		return rc;
	}
	return 0;
}

/**
 * @brief
 *	-used to encode the basic information for the
 *      RunJob request and the ConfirmReservation request
 *
 * @param[in] sock - soket descriptor
 * @param[in] id - reservation id
 * @param[in] where - reservation on
 * @param[in] arg - ar
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_Run(int sock, const char *id, const char *where, unsigned long arg)
{
	int rc;

	if ((rc = diswst(sock, id) != 0) ||
	    (rc = diswst(sock, where) != 0) ||
	    (rc = diswul(sock, arg) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *	-encode a Server Shut Down Batch Request
 *
 * @param[in] sock - socket descriptor
 * @param[in] manner - type of shutdown
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_ShutDown(int sock, int manner)
{
	return (diswui(sock, manner));
}

/**
 * @brief
 *	-encode a Signal Job Batch Request
 *
 * @param[in] sock - socket descriptor
 * @param[in] jobid - job id
 * @param[in] signal - signal
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_SignalJob(int sock, const char *jobid, const char *signal)
{
	int rc;

	if ((rc = diswst(sock, jobid) != 0) ||
	    (rc = diswst(sock, signal) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *	-encode a Status Job Batch Request
 *
 * @param[in] sock - socket descriptor
 * @param[in] objid - object id
 * @param[in] pattrl - pointer to attrl struct(list)
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_Status(int sock, const char *objid, struct attrl *pattrl)
{
	int rc;

	if ((rc = diswst(sock, objid) != 0) ||
	    (rc = encode_DIS_attrl(sock, pattrl) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *	-encode a Submit Resvervation Batch Request
 *
 * @par	Functionality:
 *		This request is used for the first step in submitting a reservation
 *      	sending the reservation attributes.
 *
 * @param[in] sock - socket descriptor
 * @param[in] resv_id - reservation id
 * @param[id] aoplp - pointer to attropl struct(list)
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_SubmitResv(int sock, const char *resv_id, struct attropl *aoplp)
{
	int rc;

	if (resv_id == NULL)
		resv_id = "";

	/* send the reservation ID and then an empty destination
	 * This is done so the server can use the queuejob structure
	 */
	if ((rc = diswst(sock, resv_id) != 0) ||
	    (rc = diswst(sock, "") != 0))
		return rc;

	return (encode_DIS_attropl(sock, aoplp));
}

/**
 * @brief
 *      -encode a Track Job batch request
 *
 * @par NOTE:
 *      This request is used by the server ONLY; its input is a server
 *      batch request structure.
 *
 * @par  Data items are:\n
 *              string          job id\n
 *              unsigned int    hopcount\n
 *              string          location\n
 *              u char          state\n
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
encode_DIS_TrackJob(int sock, struct batch_request *preq)
{
	int rc;

	if ((rc = diswst(sock, preq->rq_ind.rq_track.rq_jid) != 0) ||
	    (rc = diswui(sock, preq->rq_ind.rq_track.rq_hopcount) != 0) ||
	    (rc = diswst(sock, preq->rq_ind.rq_track.rq_location) != 0) ||
	    (rc = diswuc(sock, preq->rq_ind.rq_track.rq_state[0]) != 0))
		return rc;

	return 0;
}

/**
 * @brief
 *	- encode a User Credential Batch Request
 *
 * @param[in] sock - socket descriptor
 * @param[in] user - user name
 * @param[in] type -  Credential type
 * @param[in] cred- the credential
 * @param[in] len - length of credential
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_UserCred(int sock, const char *user, int type, const char *cred, int len)
{
	int rc;

	if ((rc = diswst(sock, user)) != 0)
		return rc;
	if ((rc = diswui(sock, type)) != 0)
		return rc;
	rc = diswcs(sock, cred, (size_t) len);

	return rc;
}

/**
 * @brief-
 *	encode a list of PBS API "attrl" structures
 *
 * @par	Functionality:
 *		The first item encoded is a unsigned integer, a count of the
 *      	number of attrl entries in the linked list.  This is encoded
 *      	even when there are no svrattrl entries in the list.
 *
 * @par	 Each individual entry is then encoded as:\n
 *		u int   size of the three strings (name, resource, value)
 *                      including the terminating nulls\n
 *		string  attribute name\n
 *		u int   1 or 0 if resource name does or does not follow\n
 *		string  resource name (if one)\n
 *		string  value of attribute/resource\n
 *		u int   "op" of attrlop, forced to "Set"\n
 *
 * @param[in] sock - socket descriptor
 * @param[in] pattrl - pointer to attrl structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_attrl(int sock, struct attrl *pattrl)
{
	unsigned int ct = 0;
	unsigned int name_len;
	struct attrl *ps;
	int rc;
	char *value;

	/* count how many */
	for (ps = pattrl; ps; ps = ps->next) {
		++ct;
	}

	if ((rc = diswui(sock, ct)) != 0)
		return rc;

	for (ps = pattrl; ps; ps = ps->next) {
		/* length of three strings */
		value = ps->value ? ps->value : "";
		name_len = (int) strlen(ps->name) + (int) strlen(value) + 2;
		if (ps->resource)
			name_len += strlen(ps->resource) + 1;

		if ((rc = diswui(sock, name_len)) != 0)
			break;
		if ((rc = diswst(sock, ps->name)) != 0)
			break;
		if (ps->resource) { /* has a resource name */
			if ((rc = diswui(sock, 1)) != 0)
				break;
			if ((rc = diswst(sock, ps->resource)) != 0)
				break;
		} else {
			if ((rc = diswui(sock, 0)) != 0) /* no resource name */
				break;
		}
		if ((rc = diswst(sock, value)) ||
		    (rc = diswui(sock, (unsigned int) SET)))
			break;
	}

	return rc;
}

/**
 * @brief
 *	- encode a list of PBS API "attropl" structures
 *
 * @par	Note:
 *	The first item encoded is a unsigned integer, a count of the
 *      number of attropl entries in the linked list.  This is encoded
 *      even when there are no attropl entries in the list.
 *
 * @par	 Each individual entry is then encoded as:\n
 *			u int   size of the three strings (name, resource, value)
 *                      	including the terminating nulls\n
 *			string  attribute name\n
 *			u int   1 or 0 if resource name does or does not follow\n
 *			string  resource name (if one)\n
 *			string  value of attribute/resource\n
 *			u int   "op" of attrlop\n
 *
 * @par	Note:
 *	the encoding of a attropl is the same as the encoding of
 *      the pbs_ifl.h structures "attrl" and the server svrattrl.  Any
 *      one of the three forms can be decoded into any of the three with the
 *      possible loss of the "flags" field (which is the "op" of the attrlop).
 *
 * @param[in] sock - socket id
 * @param[in] pattropl - pointer to attropl structure
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_attropl(int sock, struct attropl *pattropl)
{
	unsigned int ct = 0;
	unsigned int name_len;
	struct attropl *ps;
	int rc;

	/* count how many */

	for (ps = pattropl; ps; ps = ps->next) {
		++ct;
	}

	if ((rc = diswui(sock, ct)) != 0)
		return rc;

	for (ps = pattropl; ps; ps = ps->next) {
		/* length of three strings */
		name_len = (int) strlen(ps->name) + (int) strlen(ps->value) + 2;
		if (ps->resource)
			name_len += strlen(ps->resource) + 1;

		if ((rc = diswui(sock, name_len)) != 0)
			break;
		if ((rc = diswst(sock, ps->name)) != 0)
			break;
		if (ps->resource) { /* has a resource name */
			if ((rc = diswui(sock, 1)) != 0)
				break;
			if ((rc = diswst(sock, ps->resource)) != 0)
				break;
		} else {
			if ((rc = diswui(sock, 0)) != 0) /* no resource name */
				break;
		}
		if ((rc = diswst(sock, ps->value)) ||
		    (rc = diswui(sock, (unsigned int) ps->op)))
			break;
	}
	return rc;
}

/**
 * @brief
 *	-encode a list of server "svrattrl" structures
 *
 * @par	Functionality:
 *		The first item encoded is a unsigned integer, a count of the
 *      	number of svrattrl entries in the linked list.  This is encoded
 *      	even when there are no svrattrl entries in the list.
 *
 * @par	Each individual entry is then encoded as:\n
 *			u int   size of the three strings (name, resource, value)
 *                      	including the terminating nulls\n
 *			string  attribute name\n
 *			u int   1 or 0 if resource name does or does not follow\n
 *			string  resource name (if one)\n
 *			string  value of attribute/resource\n
 *			u int   "op" of attrlop
 *
 * @param[in] sock - socket descriptor
 * @param[in] psattl - pointer to svr attr list
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */

int
encode_DIS_svrattrl(int sock, svrattrl *psattl)
{
	unsigned int ct = 0;
	unsigned int name_len;
	svrattrl *ps;
	int rc;

	/* count how many */

	for (ps = psattl; ps; ps = (svrattrl *) GET_NEXT(ps->al_link)) {
		++ct;
	}

	if ((rc = diswui(sock, ct)) != 0)
		return rc;

	for (ps = psattl; ps; ps = (svrattrl *) GET_NEXT(ps->al_link)) {
		/* length of three strings */
		name_len = (int) strlen(ps->al_atopl.name) +
			   (int) strlen(ps->al_atopl.value) + 2;
		if (ps->al_atopl.resource)
			name_len += strlen(ps->al_atopl.resource) + 1;

		if ((rc = diswui(sock, name_len)) != 0)
			break;
		if ((rc = diswst(sock, ps->al_atopl.name)) != 0)
			break;
		if (ps->al_rescln) { /* has a resource name */
			if ((rc = diswui(sock, 1)) != 0)
				break;
			if ((rc = diswst(sock, ps->al_atopl.resource)) != 0)
				break;
		} else {
			if ((rc = diswui(sock, 0)) != 0) /* no resource name */
				break;
		}
		if ((rc = diswst(sock, ps->al_atopl.value)) ||
		    (rc = diswui(sock, (unsigned int) ps->al_op)))
			break;
	}
	return rc;
}
