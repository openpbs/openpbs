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

#ifndef _ACCT_H
#define _ACCT_H
#ifdef __cplusplus
extern "C" {
#endif

/*
 * header file supporting PBS accounting information
 */

#define PBS_ACCT_MAX_RCD 4095
#define PBS_ACCT_LEAVE_EXTRA 500

/* for JOB accounting */

#define PBS_ACCT_QUEUE (int) 'Q'   /* Job Queued record */
#define PBS_ACCT_RUN (int) 'S'	   /* Job run (Started) */
#define PBS_ACCT_PRUNE (int) 's'   /* Job run (Reliably-Started, assigned resources pruned) */
#define PBS_ACCT_RERUN (int) 'R'   /* Job Rerun record */
#define PBS_ACCT_CHKPNT (int) 'C'  /* Job Checkpointed and held */
#define PBS_ACCT_RESTRT (int) 'T'  /* Job resTart (from chkpnt) record */
#define PBS_ACCT_END (int) 'E'	   /* Job Ended/usage record */
#define PBS_ACCT_DEL (int) 'D'	   /* Job Deleted by request */
#define PBS_ACCT_ABT (int) 'A'	   /* Job Abort by server */
#define PBS_ACCT_LIC (int) 'L'	   /* Floating License Usage */
#define PBS_ACCT_MOVED (int) 'M'   /* Job moved to other server */
#define PBS_ACCT_UPDATE (int) 'u'  /* phased job update record */
#define PBS_ACCT_NEXT (int) 'c'	   /* phased job next record */
#define PBS_ACCT_LAST (int) 'e'	   /* phased job last usage record */
#define PBS_ACCT_ALTER (int) 'a'   /* Job attribute is being altered */
#define PBS_ACCT_SUSPEND (int) 'z' /* Job is suspended */
#define PBS_ACCT_RESUME (int) 'r'  /* Suspended Job is resumed */

/* for RESERVATION accounting */

#define PBS_ACCT_UR (int) 'U'	    /* Unconfirmed reservation enters system */
#define PBS_ACCT_CR (int) 'Y'	    /* Unconfirmed to a Confirmed reservation */
#define PBS_ACCT_BR (int) 'B'	    /* Beginning of the reservation period */
#define PBS_ACCT_FR (int) 'F'	    /* Reservation period Finished */
#define PBS_ACCT_DRss (int) 'K'	    /* sched/server requests reservation's removal */
#define PBS_ACCT_DRclient (int) 'k' /* client requests reservation's removal */

/* for PROVISIONING accounting */
#define PBS_ACCT_PROV_START (int) 'P' /* Provisioning start record */
#define PBS_ACCT_PROV_END (int) 'p'   /* Provisioning end record */

extern int acct_open(char *filename);
extern void acct_close(void);
extern void account_record(int acctype, const job *pjob, char *text);
extern void write_account_record(int acctype, const char *jobid, char *text);

#ifdef _RESERVATION_H
extern void account_recordResv(int acctype, resc_resv *presv, char *text);
extern void account_resvstart(resc_resv *presv);
#endif

extern void account_jobstr(const job *pjob, int type);
extern void account_job_update(job *pjob, int type);
extern void account_jobend(job *pjob, char *used, int type);
extern void log_alter_records_for_attrs(job *pjob, svrattrl *plist);
extern void log_suspend_resume_record(job *pjob, int acct_type);
extern void set_job_ProvAcctRcd(job *pjob, long time_se, int type);

extern int concat_rescused_to_buffer(char **buffer, int *buffer_size, svrattrl *patlist, char *delim, const job *pjob);

#define PROVISIONING_STARTED 1
#define PROVISIONING_SUCCESS 2
#define PROVISIONING_FAILURE 3

#ifdef __cplusplus
}
#endif
#endif /* _ACCT_H */
