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
 * @file    ifl_impl.c
 *
 * @brief
 * 		Pass-through call to send batch_request to server. Interfaces can
 * 		be overridden by the developer, to implement their own definition.
 */

#include <pbs_config.h> /* the master config generated by configure */

#include "ifl_internal.h"
#include "pbs_ifl.h"
#include "pbs_share.h"

/**
 * @brief
 *	-Pass-through call to send async run job batch request.
 *
 * @param[in] c - connection handle
 * @param[in] jobid- job identifier
 * @param[in] location - string of vnodes/resources to be allocated to the job
 * @param[in] extend - extend string for encoding req
 *
 * @return      int
 * @retval      0       success
 * @retval      !0      error
 *
 */
int
pbs_asyrunjob(int c, const char *jobid, const char *location, const char *extend) {
	return (*pfn_pbs_asyrunjob)(c, jobid, location, extend);
}

/**
 * @brief
 *	-Pass-through call to send async run job batch request with ack
 *
 * @param[in] c - connection handle
 * @param[in] jobid- job identifier
 * @param[in] location - string of vnodes/resources to be allocated to the job
 * @param[in] extend - extend string for encoding req
 *
 * @return      int
 * @retval      0       success
 * @retval      !0      error
 *
 */
int pbs_asyrunjob_ack(int c, const char *jobid, const char *location, const char *extend)
{
	return (*pfn_pbs_asyrunjob_ack)(c, jobid, location, extend);
}

/**
 * @brief
 *	-Pass-through call to send alter Job request
 *	really an instance of the "manager" request.
 *
 * @param[in] c - connection handle
 * @param[in] jobid- job identifier
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
int
pbs_alterjob(int c, const char *jobid, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_alterjob)(c, jobid, attrib, extend);
}

/**
 * @brief
 *	-Pass-through call to send alter Job request
 *	really an instance of the "manager" request.
 *
 * @param[in] c - connection handle
 * @param[in] jobid- job identifier
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
int
pbs_asyalterjob(int c, const char *jobid, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_asyalterjob)(c, jobid, attrib, extend);
}

/**
 * @brief
 * 	-pbs_confirmresv - this function is for exclusive use by the Scheduler
 *	to confirm an advanced reservation.
 *
 * @param[in] rid 	Reservaion ID
 * @param[in] location  string of vnodes/resources to be allocated to the resv.
 * @param[in] start 	start time of reservation if non-zero
 * @param[in] extend PBS_RESV_CONFIRM_SUCCESS or PBS_RESV_CONFIRM_FAIL
 *
 * @return	int
 * @retval	0	Success
 * @retval	!0	error
 *
 */
int
pbs_confirmresv(int c, const char *rid, const char *location, unsigned long start, const char *extend)
{
	return (*pfn_pbs_confirmresv)(c, rid, location, start, extend);
}

/**
 * @brief
 *	Pass-through call to connect to pbs server
 *	passing any 'extend' data to the connection.
 *
 * @param[in] server - server - the hostname of the pbs server to connect to.
 *
 * @retval int	- return value of pbs_connect_extend().
 */
int
pbs_connect(const char *server) {
	return (*pfn_pbs_connect)(server);
}

/**
 * @brief
 *	Pass-through call to make a PBS_BATCH_Connect request to 'server'.
 *
 * @param[in]   server - the hostname of the pbs server to connect to.
 * @param[in]   extend_data - a string to send as "extend" data.
 *
 * @return int
 * @retval >= 0	index to the internal connection table representing the
 *		connection made.
 * @retval -1	error encountered setting up the connection.
 */
int
pbs_connect_extend(const char *server, const char *extend_data) {
	return (*pfn_pbs_connect_extend)(server, extend_data);
}

/**
 * @brief
 *	- Pass-through call to get default server name.
 *
 * @return	string
 * @retval	dflt srvr name	success
 * @retval	NULL		error
 *
 */
char *
pbs_default() {
	return (*pfn_pbs_default)();
}

/**
 * @brief
 *	Pass-through call to send the delete Job request
 * 	really just an instance of the manager request
 *
 * @param[in] c - connection handler
 * @param[in] jobid - job identifier
 * @param[in] extend - string to encode req
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
int
pbs_deljob(int c, const char *jobid, const char *extend) {
	return (*pfn_pbs_deljob)(c, jobid, extend);
}

/**
 * @brief
 *	Pass-through call to send the delete Job request
 * 	really just an instance of the manager request
 *
 * @param[in] c - connection handler
 * @param[in] jobid - job identifier
 * @param[in] extend - string to encode req
 *
 * @return	struct batch_status *
 * @retval	0	success
 * @retval	!0	error
 *
 */
struct batch_deljob_status *
pbs_deljoblist(int c, char **jobid, int numofjobs, const char *extend)
{
	return (*pfn_pbs_deljoblist)(c, jobid, numofjobs, extend);
}

/**
 * @brief
 *	-Pass-through call to send close connection batch request
 *
 * @param[in] connect - socket descriptor
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	error
 *
 */
int
pbs_disconnect(int connect) {
	return (*pfn_pbs_disconnect)(connect);
}

/**
 * @brief
 *	-Pass-through call to get last error message the server returned on
 *	this connection.
 *
 * @param[in] connect - soket descriptor
 *
 * @return	string
 * @retval	connection contexts
 *		TLS			multithread
 *		STRUCTURE		single thread
 * @retval	errmsg			error
 *
 */
char *
pbs_geterrmsg(int connect) {
	return (*pfn_pbs_geterrmsg)(connect);
}

/**
 * @brief
 *	- Pass-through call to send Hold Job request to the server --
 *	really just an instance of the "manager" request.
 *
 * @param[in] c - connection handler
 * @param[in] jobid - job identifier
 * @param[in] holdtype - value for holdtype
 * @param[in] extend - string to encode req
 *
 * @return      int
 * @retval      0       success
 * @retval      !0      error
 *
 */
int
pbs_holdjob(int c, const char *jobid, const char *holdtype, const char *extend) {
	return (*pfn_pbs_holdjob)(c, jobid, holdtype, extend);
}

/**
 * @brief
 *	pbs_loadconf - Populate the pbs_conf structure
 *
 * @par
 *	Load the pbs_conf structure.  The variables can be filled in
 *	from either the environment or the pbs.conf file.  The
 *	environment gets priority over the file.  If any of the
 *	primary variables are not filled in, the function fails.
 *	Primary vars: pbs_home_path, pbs_exec_path, pbs_server_name
 *
 * @note
 *	Clients can now be multithreaded. So dont call pbs_loadconf with
 *	reload = TRUE. Currently, the code flow ensures that the configuration
 *	is loaded only once (never used with reload true). Thus in the rest of
 *	the code a direct read of the pbs_conf.variables is fine. There is no
 *	race of access of pbs_conf vars against the loading of pbs_conf vars.
 *	However, if pbs_loadconf is called with reload = TRUE, this assumption
 *	will be void. In that case, access to every pbs_conf.variable has to be
 *	synchronized against the reload of those variables.
 *
 * @param[in] reload		Whether to attempt a reload
 *
 * @return int
 * @retval 1 Success
 * @retval 0 Failure
 */
int
pbs_loadconf(int reload)
{
	return (*pfn_pbs_loadconf)(reload);
}

/**
* @brief
*      Pass-through call to send LocateJob request.
*
* @param[in] c - connection handler
* @param[in] jobid - job identifier
* @param[in] extend - string to encode req
*
* @return      string
* @retval      destination name	success
* @retval      NULL      		error
*
*/
char *
pbs_locjob(int c, const char *jobid, const char *extend) {
	return (*pfn_pbs_locjob)(c, jobid, extend);
}


/**
 * @brief
 *	- Basically a pass-thru to PBS_manager
 *
 * @param[in] c - connection handle
 * @param[in] command - mgr command with respect to obj
 * @param[in] objtype - object type
 * @param[in] objname - object name
 * @param[in] attrib -  pointer to attropl structure
 * @param[in] extend - extend string to encode req
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
int
pbs_manager(int c, int command, int objtype, const char *objname,
		struct attropl *attrib, const char *extend) {
	return (*pfn_pbs_manager)(c, command, objtype, objname,
		attrib, extend);
}

/**
 * @brief
 *	Pass-through call to send move job request
 *
 * @param[in] c - connection handler
 * @param[in] jobid - job identifier
 * @param[in] destin - job moved to
 * @param[in] extend - string to encode req
 *
 * @return      int
 * @retval      0       success
 * @retval      !0      error
 *
 */
int
pbs_movejob(int c, const char *jobid, const char *destin, const char *extend) {
	return (*pfn_pbs_movejob)(c, jobid, destin, extend);
}

/**
 * @brief
 *	-Pass-through call to send the MessageJob request and get the reply.
 *
 * @param[in] c - socket descriptor
 * @param[in] jobid - job id
 * @param[in] fileopt - which file
 * @param[in] msg - msg to be encoded
 * @param[in] extend - extend string for encoding req
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
int
pbs_msgjob(int c, const char *jobid, int fileopt, const char *msg, const char *extend) {
	return (*pfn_pbs_msgjob)(c, jobid, fileopt, msg, extend);
}

/**
 * @brief
 *	-Pass-through call to send order job batch request
 *
 * @param[in] c - connection handler
 * @param[in] job1 - job identifier
 * @param[in] job2 - job identifier
 * @param[in] extend - string to encode req
 *
 * @return      int
 * @retval      0       success
 * @retval      !0      error
 *
 */
int
pbs_orderjob(int c, const char *job1, const char *job2, const char *extend) {
	return (*pfn_pbs_orderjob)(c, job1, job2, extend);
}

/**
 * @brief
 *	-Pass-through call to send rerun batch request
 *
 * @param[in] c - connection handler
 * @param[in] jobid - job identifier
 * @param[in] extend - string to encode req
 *
 * @return      int
 * @retval      0       success
 * @retval      !0      error
 *
 */
int
pbs_rerunjob(int c, const char *jobid, const char *extend) {
	return (*pfn_pbs_rerunjob)(c, jobid, extend);
}

/**
 * @brief
 *	-Pass-through call to release a hold on a job.
 * 	really just an instance of the "manager" request.
 *
 * @param[in] c - connection handler
 * @param[in] jobid - job identifier
 * @param[in] holdtype - type of hold
 * @param[in] extend - string to encode req
 *
 * @return      int
 * @retval      0       success
 * @retval      !0      error
 *
 */
int
pbs_rlsjob(int c, const char *jobid, const char *holdtype, const char *extend) {
	return (*pfn_pbs_rlsjob)(c, jobid, holdtype, extend);
}

/**
 * @brief
 *	-Pass-through call to send preempt jobs batch request
 *
 * @param[in] c - connection handler
 * @param[in] preempt_jobs_list - list of jobs to be preempted
 *
 * @return      preempt_job_info *
 * @retval      preempt_job_info object       success
 * @retval      NULL      error
 *
 */
preempt_job_info *
pbs_preempt_jobs(int c, char **preempt_jobs_list) {
	return (*pfn_pbs_preempt_jobs)(c, preempt_jobs_list);
}

/**
 * @brief
 *	-Pass-through call to send runjob batch request
 *
 * @param[in] c - communication handle
 * @param[in] jobid - job identifier
 * @param[in] location - location where job running
 * @param[in] extend - extend string to encode req
 *
 * @return      int
 * @retval      DIS_SUCCESS(0)  success
 * @retval      error code      error
 *
 */
int
pbs_runjob(int c, const char *jobid, const char *location, const char *extend) {
	return (*pfn_pbs_runjob)(c, jobid, location, extend);
}

/**
 * @brief
 *	-Pass-through call to send SelectJob request
 *	Return a list of job ids that meet certain selection criteria.
 *
 * @param[in] c - communication handle
 * @param[in] attrib - pointer to attropl structure(selection criteria)
 * @param[in] extend - extend string to encode req
 *
 * @return	string
 * @retval	job ids		success
 * @retval	NULL		error
 *
 */
char **
pbs_selectjob(int c, struct attropl *attrib, const char *extend) {
	return (*pfn_pbs_selectjob)(c, attrib, extend);
}

/**
 * @brief
 *	Pass-through call to sends and reads signal job batch request.
 *
 * @param[in] c - communication handle
 * @param[in] jobid - job identifier
 * @param[in] signal - signal
 * @param[in] extend - extend string for request
 *
 * @return	int
 * @retval	0	success
 * @retval	!0	error
 *
 */
int
pbs_sigjob(int c, const char *jobid, const char *signal, const char *extend) {
	return (*pfn_pbs_sigjob)(c, jobid, signal, extend);
}

/**
 * @brief
 *	-Pass-through call to deallocates a "batch_status" structure
 *
 * @param[in] bsp - pointer to batch request.
 *
 * @return	Void
 *
 */
void
pbs_statfree(struct batch_status *bsp) {
	(*pfn_pbs_statfree)(bsp);
}

/**
 * @brief
 *	-Pass-through call to deallocates a "batch_deljob_status" structure
 *
 * @param[in] bsp - pointer to batch request.
 *
 * @return	Void
 *
 */
void
pbs_delstatfree(struct batch_deljob_status *bdsp) {
	(*pfn_pbs_delstatfree)(bdsp);
}


/**
 * @brief
 *	Pass-through call to get status of one or more resources.
 *
 * @param[in] c - communication handle
 * @param[in] id - object id
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return      structure handle
 * @retval      pointer to batch_status struct          Success
 * @retval      NULL                                    error
 *
 */
struct batch_status *
pbs_statrsc(int c, const char *id, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_statrsc)(c, id, attrib, extend);
}

/**
 * @brief
 *	-Pass-through call to get status of a job.
 *
 * @param[in] c - communication handle
 * @param[in] id - job id
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for req
 *
 * @return	structure handle
 * @retval	pointer to batch_status struct		success
 * @retval	NULL					error
 *
 */
struct batch_status *
pbs_statjob(int c, const char *id, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_statjob)(c, id, attrib, extend);
}

/**
 * @brief
 *	-Pass-through call to SelectJob request
 *	Return a list of job ids that meet certain selection criteria.
 *
 * @param[in] c - communication handle
 * @param[in] attrib - pointer to attropl structure(selection criteria)
 * @param[in] extend - extend string to encode req
 *
 * @return	struct batch_status
 * @retval	batch_status object for job		success
 * @retval	NULL		error
 *
 */
struct batch_status *
pbs_selstat(int c, struct attropl *attrib, struct attrl   *rattrib, const char *extend) {
	return (*pfn_pbs_selstat)(c, attrib, rattrib, extend);
}

/**
 * @brief
 *	-Pass-through call to get status of a queue.
 *
 * @param[in] c - communication handle
 * @param[in] id - object id
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return      structure handle
 * @retval      pointer to batch_status struct          Success
 * @retval      NULL                                    error
 *
 */
struct batch_status *
pbs_statque(int c, const char *id, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_statque)(c, id, attrib, extend);
}

/**
 * @brief
 *	- Pass-through call to return the status of a server.
 *
 * @param[in] c - communication handle
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return      structure handle
 * @retval      pointer to batch_status struct          Success
 * @retval      NULL                                    error
 *
 */
struct batch_status *
pbs_statserver(int c, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_statserver)(c, attrib, extend);
}

/**
 * @brief
 *	- Pass-through call to return the status of sched objects.
 *
 * @param[in] c - communication handle
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return      structure handle
 * @retval      pointer to batch_status struct          Success
 * @retval      NULL                                    error
 *
 */
struct batch_status *
pbs_statsched(int c, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_statsched)(c, attrib, extend);
}

/**
 * @brief
 * 	- Pass-through call to return the status of all possible hosts.
 *
 * @param[in] con - communication handle
 * @param[in] hid - hostname to filter
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return      structure handle
 * @retval      pointer to batch_status struct          Success
 * @retval      NULL                                    error
 *
 */
struct batch_status *
pbs_stathost(int con, const char *hid, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_stathost)(con, hid, attrib, extend);
}

/**
 * @brief
 * 	-Pass-through call to returns status of host
 *	maintained for backward compatibility
 *
 * @param[in] c - communication handle
 * @param[in] id - object id
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return      structure handle
 * @retval      pointer to batch_status struct          Success
 * @retval      NULL					error
 *
 */
struct batch_status *
pbs_statnode(int c, const char *id, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_statnode)(c, id, attrib, extend);
}

/**
 * @brief
 * 	-Pass-through call to to get information about virtual nodes (vnodes)
 *
 * @param[in] c - communication handle
 * @param[in] id - object id
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return	structure handle
 * @retval	pointer to batch_status struct		Success
 * @retval	NULL					error
 *
 */
struct batch_status *
pbs_statvnode(int c, const char *id, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_statvnode)(c, id, attrib, extend);
}


/**
 * @brief
 *	-Pass-through call to get the status of a reservation.
 *
 * @param[in] c - communication handle
 * @param[in] id - object id
 * @param[in] attrib - pointer to attribute list
 * @param[in] extend - extend string for encoding req
 *
 * @return      structure handle
 * @retval      pointer to batch_status struct          Success
 * @retval      NULL                                    error
 *
 */
struct batch_status *
pbs_statresv(int c, const char *id, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_statresv)(c, id, attrib, extend);
}


/**
 * @brief
 *	Pass-through call to get status of a hook.
 *
 * @param[in] c - communication handle
 * @param[in] id - object name
 * @param[in] attrib - pointer to attrl structure(list)
 * @param[in] extend - extend string for req
 *
 * @return	structure handle
 * @retval	pointer to attr list	success
 * @retval	NULL			error
 *
 */
struct batch_status *
pbs_stathook(int c, const char *id, struct attrl *attrib, const char *extend) {
	return (*pfn_pbs_stathook)(c, id, attrib, extend);
}

/**
 * @brief
 *	-Pass-through call to get the attributes that failed verification
 *
 * @param[in] connect - socket descriptor
 *
 * @return	structure handle
 * @retval	pointer to ecl_attribute_errors struct		success
 * @retval	NULL						error
 *
 */
struct ecl_attribute_errors *
pbs_get_attributes_in_error(int connect) {
	return (*pfn_pbs_get_attributes_in_error)(connect);
}

/**
 * @brief
 *	-Pass-through call to submit job request
 *
 * @param[in] c - communication handle
 * @param[in] attrib - ponter to attr list
 * @param[in] script - job script
 * @param[in] destination - host where job submitted
 * @param[in] extend - buffer to hold cred info
 *
 * @return      string
 * @retval      jobid   success
 * @retval      NULL    error
 *
 */
char *
pbs_submit(int c, struct attropl  *attrib, const char *script, const char *destination, const char *extend) {
	return (*pfn_pbs_submit)(c, attrib, script, destination, extend);
}

/**
 * @brief
 *	Pass-through call to submit reservation request
 *
 * @param[in]   c - socket on which connected
 * @param[in]   attrib - the list of attributes for batch request
 * @parma[in]   extend - extension of batch request
 *
 * @return char*
 * @retval SUCCESS returns the reservation ID
 * @retval ERROR NULL
 */
char *
pbs_submit_resv(int c, struct attropl *attrib, const char *extend) {
	return (*pfn_pbs_submit_resv)(c, attrib, extend);
}

/**
 * @brief
 *	Passes modify reservation request to PBSD_modify_resv( )
 *
 * @param[in]   c - socket on which connected
 * @param[in]   attrib - the list of attributes for batch request
 * @param[in]   extend - extension of batch request
 *
 * @return char*
 * @retval SUCCESS returns the response from the server.
 * @retval ERROR NULL
 */
char *
pbs_modify_resv(int c, const char *resv_id, struct attropl *attrib, const char *extend) {
	return (*pfn_pbs_modify_resv)(c, resv_id, attrib, extend);
}

/**
 * @brief
 *      Pass-through call to Delete reservation
 *
 * @param[in] c - connection handler
 * @param[in] resv_id - reservation identifier
 * @param[in] extend - string to encode req
 *
 * @return      int
 * @retval      0       success
 * @retval      !0      error
 *
 */
int
pbs_delresv(int c, const char *resv_id, const char *extend) {
	return (*pfn_pbs_delresv)(c, resv_id, extend);
}

/**
 * @brief
 * 	 	Release a set of sister nodes or vnodes,
 * 	or all sister nodes or vnodes assigned to the specified PBS
 * 	batch job.
 *
 * @param[in] c 	communication handle
 * @param[in] jobid  job identifier
 * @param[in] node_list 	list of hosts or vnodes to be released
 * @param[in] extend 	additional params, currently passes -k arguments
 *
 * @return	int
 * @retval	0	Success
 * @retval	!0	error
 *
 */
int
pbs_relnodesjob(int c, const char *jobid, const char *node_list, const char *extend) {
	return (*pfn_pbs_relnodesjob)(c, jobid, node_list, extend);
}

/**
 * @brief
 *	-Pass-through call to send termination batch_request to server.
 *
 * @param[in] c - communication handle
 * @param[in] manner - manner in which server to be terminated
 * @param[in] extend - extension string for request
 *
 * @return	int
 * @retval	0		success
 * @retval	pbs_error	error
 *
 */
int
pbs_terminate(int c, int manner, const char *extend) {
	return (*pfn_pbs_terminate)(c, manner, extend);
}

/**
 * @brief Registers the Scheduler with all the Servers configured
 *
 * param[in]	sched_id - sched identifier which is known to server
 * param[in]	primary_conn_id - primary connection handle which represents all servers returned by pbs_connect
 * param[in]	secondary_conn_id - secondary connection handle which represents all servers returned by pbs_connect
 *
 * @return int
 * @retval !0  - couldn't register with a connected server
 * @return 0  - success
 */
int
pbs_register_sched(const char *sched_id, int primary_conn_sd, int secondary_conn_sd)
{
	return (*pfn_pbs_register_sched)(sched_id, primary_conn_sd, secondary_conn_sd);
}
