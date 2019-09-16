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

#include <pbs_config.h>   /* the master config generated by configure */

#if defined(PBS_SECURITY) && (PBS_SECURITY == KRB5)

#include "renew.h"

#include "log.h"
#include "mom_func.h"

#include <errno.h>
#include <string.h>
#include <stdlib.h>
#include <stdio.h>
#include <pwd.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <sys/fcntl.h>
#include <signal.h>
#include <unistd.h>
#include <math.h>

#include "libpbs.h"
#include "portability.h"
#include "list_link.h"
#include "server_limits.h"
#include "attribute.h"
#include "resource.h"
#include "resmon.h"

#include "rpp.h"
#include "pbs_error.h"

#include "net_connect.h"
#include "dis.h"
#include "batch_request.h"
#include "resource.h"

#include "work_task.h"

#if defined(HAVE_LIBKAFS)
#include <kafs.h>
#include <grp.h>
#elif defined(HAVE_LIBKOPENAFS)
#include <kopenafs.h>
#include <grp.h>
#endif

#include <krb5.h>
#include <com_err.h>

typedef struct eexec_job_info_t {
	time_t      endtime;        /* tickets expiration time */
	krb5_creds  *creds;          /* User's TGT */
	krb5_ccache ccache;         /* User's credentials cache */
	uid_t job_uid;
	char *username;
	char *princ;
	char *jobid;
	char *ccache_name;
	krb5_principal client;
} eexec_job_info_t, *eexec_job_info;

struct krb_holder {
	int got_ticket;
	eexec_job_info_t job_info_;
	eexec_job_info job_info;
	krb5_context context;
};

pbs_list_head	svr_allcreds;	/* all credentials received from server */

struct svrcred_data {
	pbs_list_link	cr_link;
	char		*cr_jobid;
	char		*cr_credid;
	int		cr_type;
	krb5_data	*cr_data;
	char		*cr_data_base64; /* used for sending to sis moms*/
	long		cr_validity;
};
typedef struct svrcred_data svrcred_data;

const char *str_cred_actions[] = { "singleshot", "renewal", "setenv", "destroy"};

extern char *path_jobs; // job directory path
extern struct var_table vtable;
extern time_t time_now;
extern int decode_block_base64(unsigned char *ascii_data, ssize_t ascii_len, unsigned char *bin_data, ssize_t *p_bin_len, char *msg, size_t msg_len);

static int get_job_info_from_job(const job *pjob, const task *ptask, eexec_job_info job_info);
static int get_job_info_from_principal(const char *principal, const char* jobid, eexec_job_info job_info);
static krb5_error_code get_ticket_from_storage(struct krb_holder *ticket, char *errbuf, size_t errbufsz);
static krb5_error_code get_renewed_creds(struct krb_holder *ticket, char *errbuf, size_t errbufsz, int cred_action);
static int init_ticket(struct krb_holder *ticket, int cred_action);

static svrcred_data *find_cred_data_by_jobid(char *jobid);

/**
 * @brief
 * 	init_ticket_from_req - Initialize a kerberos ticket from request
 *
 * @param[in] principal - kerberos principal
 * @param[in] jobid - job id associated with request
 * @param[out] ticket - Kerberos ticket for initialization
 * @param[in] cred_action - credentials action type
 *
 * @return 	int
 * @retval	0 on success
 * @retval	!= 0 on error
 */
int
init_ticket_from_req(char *principal, char *jobid, struct krb_holder *ticket, int cred_action)
{
	int ret;
	char buf[LOG_BUF_SIZE];

	if ((ret = get_job_info_from_principal(principal, jobid, ticket->job_info)) != 0) {
		snprintf(buf, sizeof(buf), "Could not fetch GSSAPI information from principal (get_job_info_from_principal returned %d).", ret);
		log_err(errno, __func__, buf);
		return ret;
	}

#if defined(HAVE_LIBKAFS) || defined(HAVE_LIBKOPENAFS)
	if (cred_action != CRED_DESTROY) {
		setpag(0);
	}
#endif

	ret = init_ticket(ticket, cred_action);
	if (ret == 0) {
		ticket->got_ticket = 1;
	}

	return ret;
}

/**
 * @brief
 * 	init_ticket_from_job - Initialize a kerberos ticket from job
 *
 * @param[in] pjob - job structure
 * @param[in] ptask - optional - ptask associated with job
 * @param[out] ticket - Kerberos ticket for initialization
 * @param[in] cred_action - credentials action type
 *
 * @return 	int
 * @retval	0 on success
 * @retval	!= 0 on error
 */
int
init_ticket_from_job(job *pjob, const task *ptask, struct krb_holder *ticket, int cred_action)
{
	int ret;
	char buf[LOG_BUF_SIZE];

	if ((ret = get_job_info_from_job(pjob, ptask, ticket->job_info)) != 0) {
		snprintf(buf, sizeof(buf), "Could not fetch GSSAPI information from job (get_job_info_from_job returned %d).", ret);
		log_err(errno, __func__, buf);
		return ret;
	}

#if defined(HAVE_LIBKAFS) || defined(HAVE_LIBKOPENAFS)
	if (cred_action != CRED_DESTROY) {
		setpag(pjob->ji_extended.ji_ext.ji_pag);
		if (pjob->ji_extended.ji_ext.ji_pag == 0)
			pjob->ji_extended.ji_ext.ji_pag = getpag();
	}
#endif

	ret = init_ticket(ticket, cred_action);
	if (ret == 0) {
		ticket->got_ticket = 1;
	}

	return ret;
}

/**
 * @brief
 * 	init_ticket - Initialize a kerberos ticket
 *
 * @param[out] ticket - Kerberos ticket for initialization
 * @param[in] cred_action - credentials action type
 *
 * @return 	int
 * @retval	PBS_KRB5_OK on success
 * @retval	!= PBS_KRB5_OK on error
 */
static int
init_ticket(struct krb_holder *ticket, int cred_action)
{
	int ret;
	char buf[LOG_BUF_SIZE];

	if((ret = krb5_init_context(&ticket->context)) != 0) {
		log_err(ret, __func__, "Failed to initialize context.");
		return PBS_KRB5_ERR_CONTEXT_INIT;
	}

	if (cred_action < CRED_SETENV) {
		if ((ret = get_renewed_creds(ticket, buf, LOG_BUF_SIZE, cred_action)) != 0) {
			char buf2[LOG_BUF_SIZE];

			krb5_free_context(ticket->context);
			snprintf(buf2, sizeof(buf2), "get_renewed_creds returned %d, %s", ret, buf);
			log_err(errno, __func__, buf2);
			return PBS_KRB5_ERR_GET_CREDS;
		}
	}

	if (cred_action == CRED_DESTROY) {
		if((ret = krb5_cc_resolve(ticket->context, ticket->job_info->ccache_name, &ticket->job_info->ccache))) {
			snprintf(buf, sizeof(buf), "Could not resolve ccache name \"krb5_cc_resolve()\" : %s.", error_message(ret));
			log_err(errno, __func__, buf);
		return(ret);
		}
	}

	if (vtable.v_envp != NULL)
		bld_env_variables(&vtable, "KRB5CCNAME", ticket->job_info->ccache_name);
	else
		setenv("KRB5CCNAME", ticket->job_info->ccache_name, 1);

	return PBS_KRB5_OK;
}

#if defined(HAVE_LIBKAFS) || defined(HAVE_LIBKOPENAFS)
/**
 * @brief
 * 	do_afslog - tests the presence of AFS and do the AFS log if the test is true
 *
 * @param[in] context - GSS context
 * @param[in] job_info - eexec_job_info
 *
 * @return 	krb5_error_code
 * @retval	0
 */
static krb5_error_code
do_afslog(krb5_context context, eexec_job_info job_info)
{
	krb5_error_code ret = 0;

	if(k_hasafs() && (ret = krb5_afslog(context, job_info->ccache, NULL, NULL)) != 0) {
		/* ignore this error */
		ret = 0;
	}

	return(ret);
}
#endif

/**
 * @brief
 * 	store_ticket - store the credentials into ccache file
 *
 * @param[in] ticket - ticket with credential
 * @param[out] errbuf - buffer to be filled on error
 * @param[in] errbufsz - size of error buffer
 *
 * @return 	krb5_error_code
 * @retval	0 on success
 * @retval	error code on error
 */
static krb5_error_code
store_ticket(struct krb_holder *ticket, char *errbuf, size_t errbufsz)
{
	krb5_error_code  ret;

	if((ret = krb5_cc_resolve(ticket->context, ticket->job_info->ccache_name, &ticket->job_info->ccache))) {
		snprintf(errbuf, errbufsz, "%s - Could not resolve cache name \"krb5_cc_resolve()\" : %s.", __func__, error_message(ret));
		return(ret);
	}

	if((ret = krb5_cc_initialize(ticket->context, ticket->job_info->ccache, ticket->job_info->creds->client))) {
		snprintf(errbuf, errbufsz, "%s - Could not initialize cache \"krb5_cc_initialize()\" : %s.", __func__, error_message(ret));
		return(ret);
	}

	if((ret = krb5_cc_store_cred(ticket->context, ticket->job_info->ccache, ticket->job_info->creds))) {
		snprintf(errbuf, errbufsz, "%s - Could not store credentials initialize cache \"krb5_cc_store_cred()\" : %s.", __func__, error_message(ret));
		return(ret);
	}

	return(0);
}

/**
 * @brief
 * 	get_renewed_creds - Get and store renewed credentials for a given ticket.
 *	The credentilas are obtained from storage (which is the memory) and stored
 *	into ccache file.
 *
 * @param[in] ticket - ticket for which to get and store credentials
 * @param[out] errbuf - buffer to be filled on error
 * @param[in] errbufsz - size of error buffer
 * @param[in] cred_action - type of action with credentials
 *
 * @return 	krb5_error_code
 * @retval	0 on success
 * @retval	error code on error
 */
static krb5_error_code
get_renewed_creds(struct krb_holder *ticket, char *errbuf, size_t errbufsz, int cred_action)
{
	krb5_error_code ret;
	char strerrbuf[LOG_BUF_SIZE];

	/* Get TGT for user */
	if ((ret = get_ticket_from_storage(ticket, errbuf, errbufsz)) != 0) {
		log_record(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG, ticket->job_info->jobid, "no credentials supplied");
		return ret;
	}

	/* Go user */
	if(seteuid(ticket->job_info->job_uid) < 0) {
		strerror_r(errno, strerrbuf, LOG_BUF_SIZE);
		snprintf(errbuf, errbufsz, "%s - Could not set uid using \"setuid()\": %s.", __func__, strerrbuf);
		return errno;
	}

	/* Store TGT */
	if((ret = store_ticket(ticket, errbuf, errbufsz))) {
		seteuid(0);
		return ret;
	}

#if defined(HAVE_LIBKAFS) || defined(HAVE_LIBKOPENAFS)
	/* Login to AFS cells  */
	if (cred_action < CRED_SETENV) {
		if((ret = do_afslog(ticket->context, ticket->job_info))) {
			seteuid(0);
			return ret;
		}
	}
#endif

	/* Go root */
	if(seteuid(0) < 0) {
		snprintf(errbuf, errbufsz, "%s - Could not reset root privileges.", __func__);
		return errno;
	}

	return 0;
}

/**
 * @brief
 * 	get_ticket_from_storage - Acquire a user ticket. The credentials are
 *	expected to be stored in the mom's memory (supplied by the pbs server). 
 *
 * @param[in] ticket - ticket to be filled with credentials
 * @param[out] errbuf - buffer to be filled on error
 * @param[in] errbufsz - size of error buffer
 *
 * @return 	krb5_error_code
 * @retval	0 on success
 * @retval	error code on error
 */
static krb5_error_code
get_ticket_from_storage(struct krb_holder *ticket, char *errbuf, size_t errbufsz)
{
	krb5_error_code ret = 0;
	krb5_auth_context auth_context = NULL;
	krb5_creds **creds = NULL;
	krb5_data *datatmp;
	krb5_data *data;
	int32_t flags;
	svrcred_data *cred_data;

	cred_data = find_cred_data_by_jobid(ticket->job_info->jobid);
	if (cred_data == NULL || (datatmp = cred_data->cr_data) == NULL) {
		snprintf(errbuf, errbufsz, "find_cred_by_jobid failed; no credentials supplied for job: %s", ticket->job_info->jobid);
		ret = KRB5_NOCREDS_SUPPLIED;
		goto out;
	}

	if ((ret = krb5_copy_data(ticket->context, datatmp, &data))) {
		const char *krb5_err = krb5_get_error_message(ticket->context, ret);
		snprintf(errbuf, errbufsz, "krb5_copy_data failed; Error text: %s", krb5_err);
		krb5_free_error_message(ticket->context, krb5_err);
		goto out;
	}

	if ((ret = krb5_auth_con_init(ticket->context, &auth_context))) {
		const char *krb5_err = krb5_get_error_message(ticket->context, ret);
		snprintf(errbuf, errbufsz, "krb5_auth_con_init failed; Error text: %s", krb5_err);
		krb5_free_error_message(ticket->context, krb5_err);
		goto out;
	}

	krb5_auth_con_getflags(ticket->context, auth_context, &flags);
	/* We disable timestamps in the message so the expected message could be cached
	 * and re-sent. The following flag needs to be also set by the tool
	 * that supplies credential.
	 * N.B. The semantics of KRB5_AUTH_CONTEXT_DO_TIME applied in
	 * krb5_fwd_tgt_creds() seems to differ between Heimdal and MIT. MIT uses
	 * it to (also) enable replay cache checks (that are useless and
	 * troublesome for us). Heimdal uses it to just specify whether or not the
	 * timestamp is included in the forwarded message. */
	flags &= ~(KRB5_AUTH_CONTEXT_DO_TIME);
	krb5_auth_con_setflags(ticket->context, auth_context, flags);

	if ((ret = krb5_rd_cred(ticket->context, auth_context, data , &creds, NULL))) {
		const char *krb5_err = krb5_get_error_message(ticket->context, ret);
		snprintf(errbuf,errbufsz, "krb5_rd_cred - reading credentials; Error text: %s", krb5_err);
		krb5_free_error_message(ticket->context, krb5_err);
		goto out;
	}

	ticket->job_info->creds = creds[0];

	ticket->job_info->endtime = ticket->job_info->creds->times.endtime;

	if (ticket->job_info->endtime < time_now)
		return KRB5_NOCREDS_SUPPLIED;

out:
	return ret;
}

/**
 * @brief
 * 	get_ticket_ccname - Get ccname file name from ticket
 *
 * @param[in] ticket
 *
 * @return 	char
 * @retval	ccache file
 * @retval	NULL on error
 */
char
*get_ticket_ccname(struct krb_holder *ticket)
{
	if (ticket == NULL || ticket->job_info == NULL)
		return NULL;

	return ticket->job_info->ccache_name;
}

/**
 * @brief
 * 	got_ticket - Allocated a new krb_holder structure (ticket)
 *
 * @return 	krb_holder
 * @retval	structure - on success
 * @retval	NULL - otherwise
 */
struct krb_holder
*alloc_ticket()
{
	struct krb_holder *ticket = (struct krb_holder*)malloc(sizeof(struct krb_holder));
	if (ticket == NULL)
		return NULL;

	ticket->job_info = &ticket->job_info_;

	ticket->job_info->creds = malloc(sizeof(krb5_creds));
	memset(ticket->job_info->creds, 0, sizeof(krb5_creds));

	ticket->got_ticket = 0;

	return ticket;
}

/**
 * @brief
 * 	free_ticket - Free a kerberos ticket. Distinguishes whether the
 *	credentials should be also destroyed (removed ccache) or only
 *	free the structures.
 *
 * @param[in] ticket - Ticket with context and job info information
 * @param[in] cred_action - requested action
 *
 */
void
free_ticket(struct krb_holder *ticket, int cred_action)
{
	krb5_error_code ret = 0;

	if (ticket == NULL)
		return;

	if (ticket->got_ticket) {
		if (cred_action == CRED_DESTROY && ticket->job_info->ccache) {
			if ((ret = krb5_cc_destroy(ticket->context, ticket->job_info->ccache))) {
				const char *krb5_err = krb5_get_error_message(ticket->context, ret);
				log_err(ret, __func__, krb5_err);
				krb5_free_error_message(ticket->context, krb5_err);
			}

			unlink(ticket->job_info->ccache_name);
		}

		krb5_free_creds(ticket->context, ticket->job_info->creds);
		krb5_free_principal(ticket->context, ticket->job_info->client);
		krb5_free_context(ticket->context);

#if defined(HAVE_LIBKAFS) || defined(HAVE_LIBKOPENAFS)
		if (cred_action == CRED_DESTROY && k_hasafs())
			k_unlog();
#endif

	}

	free(ticket->job_info->ccache_name);
	free(ticket->job_info->princ);
	free(ticket->job_info->username);

	free(ticket);
}

/**
 * @brief
 * 	get_job_info_from_job - Fill in job info from job structure
 *
 * @param[in] pjob - job structure
 * @param[in] ptask - optional ptask associated with job process
 * @param[out] job_info - filled job information
 *
 * @return 	int
 * @retval	PBS_KRB5_OK - on sucess
 * @retval	!= PBS_KRB5_OK - on error
 */
static int
get_job_info_from_job(const job *pjob, const task *ptask, eexec_job_info job_info)
{
	char *principal = NULL;
	size_t len;
	char *ccname = NULL;

	if (pjob->ji_wattr[(int)JOB_ATR_cred_id].at_flags & ATR_VFLAG_SET)
		principal = strdup(pjob->ji_wattr[(int)JOB_ATR_cred_id].at_val.at_str);
	else {
		log_err(-1, __func__, "No ticket found on job.");
		return PBS_KRB5_ERR_NO_KRB_PRINC;
	}

	if (principal == NULL) // memory allocation error
		return PBS_KRB5_ERR_INTERNAL;

	if (ptask == NULL) {
		len = snprintf(NULL, 0, "FILE:/tmp/krb5cc_pbsjob_%s", pjob->ji_qs.ji_jobid);
		ccname = (char*)(malloc(len + 1));
		if (ccname != NULL)
			snprintf(ccname,len + 1,"FILE:/tmp/krb5cc_pbsjob_%s", pjob->ji_qs.ji_jobid);
	} else {
		len = snprintf(NULL, 0, "FILE:/tmp/krb5cc_pbsjob_%s_%ld", pjob->ji_qs.ji_jobid, (long)ptask->ti_qs.ti_task);
		ccname = (char*)(malloc(len + 1));
		if (ccname != NULL)
			snprintf(ccname, len + 1, "FILE:/tmp/krb5cc_pbsjob_%s_%ld", pjob->ji_qs.ji_jobid, (long)ptask->ti_qs.ti_task);
	}

	if (ccname == NULL) { /* memory allocation error */
		free(principal);
		return PBS_KRB5_ERR_INTERNAL;
	}

	if (pjob->ji_wattr[(int)JOB_ATR_euser].at_val.at_str == NULL) {
		free(principal);
		free(ccname);
		return PBS_KRB5_ERR_NO_USERNAME;
	}

	char *username = strdup(pjob->ji_wattr[(int)JOB_ATR_euser].at_val.at_str);
	if (username == NULL) {
		free(principal);
		free(ccname);
		return PBS_KRB5_ERR_INTERNAL;
	}

	krb5_context context;
	krb5_init_context(&context);
	krb5_parse_name(context,principal,&job_info->client);

	krb5_free_context(context);

	job_info->princ = principal;
	job_info->ccache_name = ccname;
	job_info->username = username;
	job_info->job_uid = pjob->ji_qs.ji_un.ji_momt.ji_exuid;

	job_info->jobid = strdup(pjob->ji_qs.ji_jobid);
	if (job_info->jobid == NULL) {
		free(principal);
		free(ccname);
		return PBS_KRB5_ERR_INTERNAL;
	}

	return PBS_KRB5_OK;
}

/**
 * @brief
 * 	get_job_info_from_principal - Fill in job info from a principal
 *
 * @param[in] principal - Principal for which to construct job info
 * @param[in] jobid - Job ID for which to construct job info
 * @param[out] job_info - filled job information
 *
 * @return 	int
 * @retval	PBS_KRB5_OK - on sucess
 * @retval	!= PBS_KRB5_OK - on error
 */
static int
get_job_info_from_principal(const char *principal, const char* jobid, eexec_job_info job_info)
{
	struct passwd pwd;
	struct passwd *result;
	char *buf;
	long int bufsize;

	if (principal == NULL) {
		log_err(-1, __func__, "No principal provided.");
		return PBS_KRB5_ERR_NO_KRB_PRINC;
	}

	char *princ = strdup(principal);
	if (princ == NULL)
		return PBS_KRB5_ERR_INTERNAL;

	char login[PBS_MAXUSER + 1];
	strncpy(login, principal, PBS_MAXUSER + 1);
	char *c = strchr(login, '@');
	if (c != NULL)
		*c = '\0';

	// get users uid
	bufsize = sysconf(_SC_GETPW_R_SIZE_MAX);
	if (bufsize == -1)          /* Value was indeterminate */
		bufsize = 16384;          /* Should be more than enough */

	if ((buf = (char*)(malloc(bufsize))) == NULL) {
		free(princ);
		return PBS_KRB5_ERR_INTERNAL;
	}

	int ret = getpwnam_r(login, &pwd, buf, bufsize, &result);

	if (result == NULL) {
		free(princ);
		free(buf);
		if (ret == 0)
			return PBS_KRB5_ERR_CANT_OPEN_FILE;
		else
			return PBS_KRB5_ERR_INTERNAL;
	}

	uid_t uid = pwd.pw_uid;
	free(buf);

	char *username = strdup(login);
	if (username == NULL) {
		free(princ);
		return PBS_KRB5_ERR_INTERNAL;
	}

	size_t len;
	char *ccname;
	len = snprintf(NULL, 0, "FILE:/tmp/krb5cc_pbsjob_%s", jobid);
	ccname = (char*)(malloc(len + 1));
	if (ccname != NULL)
		snprintf(ccname, len + 1, "FILE:/tmp/krb5cc_pbsjob_%s", jobid);

	if (ccname == NULL) {
		free(princ);
		free(username);
	}

	krb5_context context;
	krb5_init_context(&context);
	krb5_parse_name(context, principal, &job_info->client);

	krb5_free_context(context);

	job_info->princ = princ;
	job_info->job_uid = uid;
	job_info->username = username;
	job_info->ccache_name = ccname;

	job_info->jobid = strdup(jobid);
	if (job_info->jobid == NULL) {
		free(princ);
		free(ccname);
		free(username);
		return PBS_KRB5_ERR_INTERNAL;
	}

	return PBS_KRB5_OK;
}

/**
 * @brief
 * 	cred_by_job - renew/create or destroy credential associated with job id
 *
 * @param[in] pjob - job structure
 * @param[in] cred_action - type of action (renewal, destroy)
 *
 * @return 	int
 * @retval	PBS_KRB5_OK - on sucess
 * @retval	!= PBS_KRB5_OK - on error
 */
int
cred_by_job(job *pjob, int cred_action)
{
	struct krb_holder *ticket = NULL;
	int ret;

	ticket = alloc_ticket();
	if (ticket == NULL)
		return PBS_KRB5_ERR_INTERNAL;

	ret = init_ticket_from_job(pjob, NULL, ticket, cred_action);
	if (ret == PBS_KRB5_ERR_NO_KRB_PRINC) {
		/* job without a principal */
		/* not an error, but do nothing */
		return PBS_KRB5_OK;
	}

	if (ret == PBS_KRB5_OK) {
		sprintf(log_buffer, "%s for %s succeed",
			str_cred_actions[cred_action],
			ticket->job_info->ccache_name);
		log_record(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB, LOG_DEBUG, pjob->ji_qs.ji_jobid, log_buffer);
	} else {
		sprintf(log_buffer, "%s for %s failed with error: %d",
			str_cred_actions[cred_action],
			ticket->job_info->ccache_name,
			ret);
		log_record(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_DEBUG, pjob->ji_qs.ji_jobid, log_buffer);
	}

	free_ticket(ticket, cred_action);

	return ret;
}

/**
 * @brief
 * 	renew_job_cred - renew credentials for job and also do the AFS log.
 *
 * @param[in] pjob - job structure
 *
 */
void
renew_job_cred(job *pjob)
{
	int ret = 0;

	if ((ret = cred_by_job(pjob, CRED_RENEWAL)) != PBS_KRB5_OK) {
		sprintf(log_buffer, "renewal failed, error: %d", ret);
		log_record(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_ERR,
			pjob->ji_qs.ji_jobid, log_buffer);
	}

	/* we don't want mom to have ccache of some user... */
	unsetenv("KRB5CCNAME");
}

/**
 * @brief
 * 	store_or_update_cred - save received credentials into mom's memory
 *
 * @param[in] jobid - Job ID
 * @param[in] princ - cred id (e.g. principal)
 * @param[in] data - the credentials itself
 * @param[in] data_base64 - the credentials in base64
 *
 */
void
store_or_update_cred(char *jobid, char *credid, int cred_type, krb5_data *data, char *data_base64, long validity)
{
	svrcred_data *cred_data;

	cred_data = (svrcred_data *)GET_NEXT(svr_allcreds);
	while (cred_data) {
		if (strcmp(cred_data->cr_jobid, jobid) == 0) {
			free(cred_data->cr_data->data);
			free(cred_data->cr_data);
			if (cred_data->cr_data_base64)
				free(cred_data->cr_data_base64);

			cred_data->cr_type = cred_type;
			cred_data->cr_data = data;
			cred_data->cr_data_base64 = data_base64;
			cred_data->cr_validity = validity;
			return;
		}
		cred_data = (svrcred_data *)GET_NEXT(cred_data->cr_link);
	}

	if ((cred_data = (svrcred_data *)malloc(sizeof(svrcred_data))) == NULL) {
		log_err(errno, __func__, "Unable to allocate Memory!\n");
		return;
	}

	CLEAR_LINK(cred_data->cr_link);

	cred_data->cr_jobid = strdup(jobid);
	cred_data->cr_credid = strdup(credid);
	cred_data->cr_type = cred_type;
	cred_data->cr_data = data;
	cred_data->cr_data_base64 = data_base64;
	cred_data->cr_validity = validity;

	append_link(&svr_allcreds, &cred_data->cr_link, cred_data);
}

/**
 * @brief
 * 	delete_cred - delete credentials associated with job id from the mom's
 *	memory
 *
 * @param[in] jobid - Job ID
 *
 */
void
delete_cred(char *jobid)
{
	svrcred_data *cred_data;

	cred_data = (svrcred_data *)GET_NEXT(svr_allcreds);
	while (cred_data) {
		if (strcmp(cred_data->cr_jobid, jobid) == 0) {
			free(cred_data->cr_jobid);
			free(cred_data->cr_credid);
			free(cred_data->cr_data->data);
			free(cred_data->cr_data);
			if (cred_data->cr_data_base64)
				free(cred_data->cr_data_base64);

			delete_link(&cred_data->cr_link);
			return;
		}
		cred_data = (svrcred_data *)GET_NEXT(cred_data->cr_link);
	}
}

/**
 * @brief
 * 	find_cred_by_jobid - try to find credentials in mom's memory by the jobid
 *
 * @param[in] jobid - Job ID
 *
 * @return 	svrcred_data
 * @retval	credentials data on success
 * @retval	NULL otherwise
 */
static svrcred_data
*find_cred_data_by_jobid(char *jobid)
{
	svrcred_data *cred_data;

	cred_data = (svrcred_data *)GET_NEXT(svr_allcreds);
	while (cred_data) {
		if (strcmp(cred_data->cr_jobid, jobid) == 0)
			return cred_data;

		cred_data = (svrcred_data *)GET_NEXT(cred_data->cr_link);
	}
	return NULL;
}

/**
 * @brief
 * 	im_cred_send - send job's credentials from superior mom to sister mom.
 *	Find the credentials in base64 in superior mom's memory and send them
 *	via IM protocol. This function is meant to by run by send_sisters and
 *	it shouldn't be sent via mcast because mcast can't be wrapped by GSS
 *
 * @param[in] jobid - Job ID
 *
 * @return 	int
 * @retval	DIS_SUCCESS on success
 * @retval	!= DIS_SUCCESS otherwise
 */
int
im_cred_send(job *pjob, hnodent *xp, int stream)
{
	int		ret;
	svrcred_data	*cred_data;
	char		*data_base64;

	cred_data = find_cred_data_by_jobid(pjob->ji_qs.ji_jobid);

	if (cred_data == NULL || (data_base64 = cred_data->cr_data_base64) == NULL) {
		ret = DIS_PROTO;
		goto done;
	}

	ret = diswui(stream, cred_data->cr_type);
	if (ret != DIS_SUCCESS)
		goto done;

	ret = diswst(stream, data_base64);
	if (ret != DIS_SUCCESS)
		goto done;

	ret = diswul(stream, cred_data->cr_validity);
	if (ret != DIS_SUCCESS)
		goto done;

	return DIS_SUCCESS;

done:
	sprintf(log_buffer, "dis err %d (%s)", ret, dis_emsg[ret]);
	DBPRT(("%s: %s\n", __func__, log_buffer))
	log_joberr(-1, __func__, log_buffer, pjob->ji_qs.ji_jobid);
	return ret;
}

/**
 * @brief
 * 	im_cred_read - read received (via IM) credentials in base64 on sister
 *	mom, store the credentials in mom's memory and renew the credentials for
 *	associated job.
 *
 * @param[in] pjob - job structure
 * @param[in] np - node structure
 * @param[in] stream - tpp channel
 *
 * @return 	int
 * @retval	DIS_SUCCESS on success
 * @retval	!= DIS_SUCCESS otherwise
 */
int
im_cred_read(job *pjob, hnodent *np, int stream)
{
	int		ret;
	char		*data_base64;
	unsigned char	out_data[CRED_DATA_SIZE];
	ssize_t		out_len = 0;
	char		buf[LOG_BUF_SIZE];
	krb5_data	*data;
	int		cred_type;
	long		validity;

	DBPRT(("%s: entry\n", __func__))

	cred_type = disrui(stream, &ret);
	if (ret != DIS_SUCCESS)
		goto err;

	data_base64 = disrst(stream, &ret);
	if (ret != DIS_SUCCESS)
		goto err;

	validity = disrul(stream, &ret);
	if (ret != DIS_SUCCESS)
		goto err;

	if (decode_block_base64((unsigned char *)data_base64, strlen(data_base64), out_data, &out_len, buf, LOG_BUF_SIZE) != 0) {
		log_err(errno, __func__, buf);
		ret = DIS_PROTO;
		goto err;
	}

	if ((data = (krb5_data *)malloc(sizeof(krb5_data))) == NULL) {
		log_err(errno, __func__, "Unable to allocate Memory!\n");
		ret = DIS_NOMALLOC;
		goto err;
	}

	if ((data->data = (char *)malloc(sizeof(unsigned char)*out_len)) == NULL) {
		log_err(errno, __func__, "Unable to allocate Memory!\n");
		ret = DIS_NOMALLOC;
		goto err;
	}

	data->length = out_len;
	memcpy(data->data, out_data, out_len);

	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
		LOG_INFO,
		pjob->ji_qs.ji_jobid,
		"credentials from superior mom received");

	store_or_update_cred(pjob->ji_qs.ji_jobid,
		pjob->ji_wattr[(int)JOB_ATR_cred_id].at_val.at_str,
		cred_type,
		data,
		NULL,
		validity);

	/* I am the sister and new cred has been received - lets renew creds */
	renew_job_cred(pjob);

	return DIS_SUCCESS;

err:
	/*
	 ** Getting here means we had a read failure.
	 */
	sprintf(log_buffer, "dis err %d (%s)", ret, dis_emsg[ret]);
	DBPRT(("%s: %s\n", __func__, log_buffer))
	log_joberr(-1, __func__, log_buffer, pjob->ji_qs.ji_jobid);
	return ret;
}

/**
 * @brief
 * 	send_cred_sisters - send credentials from superior mom to all sister moms
 *
 * @param[in] pjob - job structure
 *
 */
void
send_cred_sisters(job *pjob)
{
	int i;

	if (pjob->ji_numnodes > 1) {
		log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_JOB,
			LOG_INFO,
			pjob->ji_qs.ji_jobid,
			"sending credentials to sisters");

		i = send_sisters(pjob, IM_CRED, im_cred_send);

		if (i != pjob->ji_numnodes-1) {
			/* If send_sisters() fails, the job is probably doomed anyway.
			 * Should we resend credentials on fail? */
			//(void)set_task(WORK_Timed, time_now + 2, send_cred_sisters, pjob);

			log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_JOB, LOG_ERR,
				pjob->ji_qs.ji_jobid,
				"could not send credentials to sisters");
		}
	}
}

#if defined(HAVE_LIBKAFS) || defined(HAVE_LIBKOPENAFS)
/**
 * @brief
 * 	getpag - recognize afs pag in groups and return the pag.
 *
 * @return 	int32_t
 * @retval	pag > 0 on success
 * @retval	0 otherwise
 */
int32_t
getpag()
{
	gid_t *grplist = NULL;
	int    i;
	int    numsup;
	static int   maxgroups = 0;
	int32_t pag = 0;

	if (k_hasafs() == 0)
		return 0;

	maxgroups = (int)sysconf(_SC_NGROUPS_MAX);

	grplist = calloc((size_t)maxgroups, sizeof(gid_t));
	if (grplist == NULL)
		return 0;

	numsup = getgroups(maxgroups, grplist);

	for (i = 0; i < numsup; ++i) {
		/* last (4th) byte in pag is char 'A' */
		if ((grplist[i] >> 24) == 'A') {
			pag = grplist[i];
			break;
		}
	}

	if (grplist)
		free(grplist);

	return pag;
}

/**
 * @brief
 * 	setpag - if afs pag != 0 is provided then the pag is added to groups
 *	if the pag is not provided, a new pag is set
 *
 * @param[in] pag - the pag group id
 *
 */
void
setpag(int32_t pag)
{
	gid_t *grplist = NULL;
	int    numsup;
	static int   maxgroups = 0;

	if (k_hasafs() == 0)
		return;

	if (pag == 0) {
		k_setpag();
		return;
	}

	/* first remove any other pag - for sure */
	removepag();

	maxgroups = (int)sysconf(_SC_NGROUPS_MAX);

	grplist = calloc((size_t)maxgroups, sizeof(gid_t));
	if (grplist == NULL)
		return;

	/* get the current list of groups */
	numsup = getgroups(maxgroups, grplist);

	grplist[numsup++] = pag;

	if (setgroups((size_t)numsup, grplist) != -1) {
		free(grplist);
		return;
	}

	if (grplist)
		free(grplist);

	return;
}

/**
 * @brief
 * 	removepag - if afs pag is set then it is removed from groups
 *
 */
void
removepag()
{
	gid_t *grplist = NULL;
	int    numsup;
	static int   maxgroups = 0;
	int32_t pag;
	int i;
	int found;

	if (k_hasafs() == 0)
		return;

	if ((pag = getpag()) == 0)
		return;

	maxgroups = (int)sysconf(_SC_NGROUPS_MAX);

	grplist = calloc((size_t)maxgroups, sizeof(gid_t));
	if (grplist == NULL)
		return;

	/* get the current list of groups */
	numsup = getgroups(maxgroups, grplist);

	i = 0;
	found = 0;
	for (i = 0; i < numsup; i++) {
		if (grplist[i] == pag) {
			numsup--;
			found = i;
			break;
		}
	}

	if (found) {
		for (i = found; i < numsup; i++)
			grplist[i] = grplist[i + 1];
	} else {
		free(grplist);
		return;
	}

	if (setgroups((size_t)numsup, grplist) != -1) {
		free(grplist);
		return;
	}

	if (grplist)
		free(grplist);

	return;
}
#endif
#endif
