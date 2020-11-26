/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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
 * @file    svr_mail.c
 *
 * @brief
 * 		svr_mail.c - send mail to mail list or owner of job on
 *		job begin, job end, and/or job abort
 *
 * 	Included public functions are:
 *		create_socket_and_connect()
 *		read_smtp_reply()
 *		write3_smtp_data()
 *		send_mail()
 *		send_mail_detach()
 *		svr_mailowner_id()
 *		svr_mailowner()
 *		svr_mailownerResv()
 *
 */

#include <pbs_config.h>   /* the master config generated by configure */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <unistd.h>
#include <errno.h>
#include <sys/types.h>
#include "pbs_ifl.h"
#include "list_link.h"
#include "attribute.h"
#include "server_limits.h"
#include "log.h"

#include "job.h"
#include "reservation.h"
#include "server.h"
#include "tpp.h"


/* External Functions Called */

extern void net_close(int);

/* Globol Data */

extern struct server server;
extern char *msg_job_abort;
extern char *msg_job_start;
extern char *msg_job_end;
extern char *msg_resv_abort;
extern char *msg_resv_start;
extern char *msg_resv_end;
extern char *msg_resv_confirm;
extern char *msg_job_stageinfail;

#define MAIL_ADDR_BUF_LEN 1024

/**
 * @brief
 * 		Exec mailer (sendmail like) and return a descriptor with a pipe
 *		where the mailer is waiting for data on stdin. The descriptor
 *		must be closed after conveying data.
 *
 * @param[in]	mailer - path to sendmail/mailer
 * @param[in]	mailfrom - the sender of the email
 * @param[in]	mailto - the recipient of the email
 *
 * @return	FILE *
 * @retval	file descriptor : if fdopen succeed
 * @retval	NULL : failed
 */
static FILE *
svr_exec_mailer(char *mailer, char *mailfrom, char *mailto)
{
	char *margs[5];
	int mfds[2];
	pid_t mcpid;

	/* setup sendmail/mailer command line with -f from_whom */

	margs[0] = mailer;
	margs[1] = "-f";
	margs[2] = mailfrom;
	margs[3] = mailto;
	margs[4] = NULL;

	if (pipe(mfds) == -1)
		exit(1);

	mcpid = fork();
	if (mcpid == 0) {
		/* this child will be sendmail with its stdin set to the pipe */
		close(mfds[1]);
		if (mfds[0] != 0) {
			(void)close(0);
			if (dup(mfds[0]) == -1)
				exit(1);
		}
		(void)close(1);
		(void)close(2);
		if (execv(mailer, margs) == -1)
			exit(1);
	}
	if (mcpid == -1) {/* Error on fork */
		log_err(errno, __func__, "fork failed\n");
		(void)close(mfds[0]);
		exit(1);
	}

	/* parent (not the real server though) will write body of message on pipe */
	(void)close(mfds[0]);

	return(fdopen(mfds[1], "w"));
}

/**
 * @brief
 * 		Send mail to owner of a job when an event happens that
 *		requires mail, such as the job starts, ends or is aborted.
 *		The event is matched against those requested by the user.
 *		For Unix/Linux, a child is forked to not hold up the Server.  This child
 *		will fork/exec sendmail and pipe the To, Subject and body to it.
 *
 * @param[in]	jid	-	the Job ID (string)
 * @param[in]	pjob	-	pointer to the job structure
 * @param[in]	mailpoint	-	which mail event is triggering the send
 * @param[in]	force	-	if non-zero, force the mail even if not requested
 * @param[in]	text	-	the body text of the mail message
 *
 * @return	none
 */
void
svr_mailowner_id(char *jid, job *pjob, int mailpoint, int force, char *text)
{
	int	 addmailhost;
	int	 i;
	char    *mailer;
	char	*mailfrom;
	char	 mailto[MAIL_ADDR_BUF_LEN];
	int	 mailaddrlen = 0;
	struct array_strings *pas;
	char	*stdmessage = NULL;
	char	*pat;
	extern  char server_host[];

	FILE   *outmail;
	pid_t   mcpid;


	/* if force is true, force the mail out regardless of mailpoint */

	if (force != MAIL_FORCE) {
		if (pjob != 0) {

			if (pjob->ji_qs.ji_svrflags & JOB_SVFLG_SubJob) {
				if (is_jattr_set(pjob, JOB_ATR_mailpnts)) {
					if (strchr(get_jattr_str(pjob, JOB_ATR_mailpnts), MAIL_SUBJOB) == NULL)
						return;
				} else
					return;
			}

			/* see if user specified mail of this type */

			if (is_jattr_set(pjob, JOB_ATR_mailpnts)) {
				if (strchr(get_jattr_str(pjob, JOB_ATR_mailpnts), mailpoint) == NULL)
					return;
			} else if (mailpoint != MAIL_ABORT)	/* not set, default to abort */
				return;

		} else if ((server.sv_attr[(int)SVR_ATR_mailfrom].at_flags & ATR_VFLAG_SET) == 0) {

			/* not job related, must be system related;  not sent unless */
			/* forced or if "mailfrom" attribute set         		 */
			return;
		}
	}

	/*
	 * ok, now we will fork a process to do the mailing to not
	 * hold up the server's other work.
	 */

	mcpid = fork();
	if (mcpid == -1) { /* Error on fork */
		log_err(errno, __func__, "fork failed\n");
		return;
	}
	if (mcpid > 0)
		return;		/* its all up to the child now */

	/*
	 * From here on, we are a child process of the server.
	 * Fix up file descriptors and signal handlers.
	 */
	net_close(-1);
	tpp_terminate();

	/* Unprotect child from being killed by kernel */
	daemon_protect(0, PBS_DAEMON_PROTECT_OFF);

	if (is_attr_set(&server.sv_attr[(int)SVR_ATR_mailer]))
		mailer = server.sv_attr[(int)SVR_ATR_mailer].at_val.at_str;
	else
		mailer = SENDMAIL_CMD;

	/* Who is mail from, if SVR_ATR_mailfrom not set use default */

	if (is_attr_set(&server.sv_attr[(int)SVR_ATR_mailfrom]))
		mailfrom = server.sv_attr[(int)SVR_ATR_mailfrom].at_val.at_str;
	else
		mailfrom = PBS_DEFAULT_MAIL;

	/* Who does the mail go to?  If mail-list, them; else owner */

	*mailto = '\0';
	if (pjob != 0) {
		if (jid == NULL)
			jid = pjob->ji_qs.ji_jobid;

		if (is_jattr_set(pjob, JOB_ATR_mailuser)) {

			/* has mail user list, send to them rather than owner */

			pas = pjob->ji_wattr[(int)JOB_ATR_mailuser].at_val.at_arst;
			if (pas != NULL) {
				for (i = 0; i < pas->as_usedptr; i++) {
					addmailhost = 0;
					mailaddrlen += strlen(pas->as_string[i]) + 2;
					if ((pbs_conf.pbs_mail_host_name)  &&
					    (strchr(pas->as_string[i], (int)'@') == NULL)) {
							/* no host specified in address and      */
							/* pbs_mail_host_name is defined, use it */
							mailaddrlen += strlen(pbs_conf.pbs_mail_host_name) + 1;
							addmailhost = 1;
					}
					if (mailaddrlen < sizeof(mailto)) {
						(void)strcat(mailto, pas->as_string[i]);
						if (addmailhost) {
							/* append pbs_mail_host_name */
							(void)strcat(mailto, "@");
							(void)strcat(mailto, pbs_conf.pbs_mail_host_name);
						}
						(void)strcat(mailto, " ");
					} else {
					  	sprintf(log_buffer,"Email list is too long: \"%.77s...\"", mailto);
						log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_WARNING, pjob->ji_qs.ji_jobid, log_buffer);
						break;
					}
				}
			}

		} else {

			/* no mail user list, just send to owner */

			strcpy(mailto, get_jattr_str(pjob, JOB_ATR_job_owner));
			/* if pbs_mail_host_name is set in pbs.conf, then replace the */
			/* host name with the name specified in pbs_mail_host_name    */
			if (pbs_conf.pbs_mail_host_name) {
				if ((pat = strchr(mailto, (int)'@')) != NULL)
					*pat = '\0';	/* remove existing @host */
				if ((strlen(mailto) + strlen(pbs_conf.pbs_mail_host_name) + 1) < sizeof(mailto)) {
					/* append the pbs_mail_host_name since it fits */
					strcat(mailto, "@");
					strcat(mailto, pbs_conf.pbs_mail_host_name);
				} else {
				  	if (pat)
						*pat = '@';	/* did't fit, restore the "at" sign */
				  	sprintf(log_buffer,"Email address is too long: \"%.77s...\"", mailto);
					log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_WARNING, pjob->ji_qs.ji_jobid, log_buffer);
				}
			}
		}

	} else {
		/* send system related mail to "mailfrom" */
		strcpy(mailto, mailfrom);
	}

	if ((outmail = svr_exec_mailer(mailer, mailfrom, mailto)) == NULL)
		exit(1);

	/* Pipe in mail headers: To: and Subject: */

	fprintf(outmail, "To: %s\n", mailto);

	if (pjob)
		fprintf(outmail, "Subject: PBS JOB %s\n\n", jid);
	else
		fprintf(outmail, "Subject: PBS Server on %s\n\n", server_host);

	/* Now pipe in "standard" message */

	switch (mailpoint) {

		case MAIL_ABORT:
			stdmessage = msg_job_abort;
			break;

		case MAIL_BEGIN:
			stdmessage = msg_job_start;
			break;

		case MAIL_END:
			stdmessage = msg_job_end;
			break;

		case MAIL_STAGEIN:
			stdmessage = msg_job_stageinfail;
			break;

	}

	if (pjob) {
		fprintf(outmail, "PBS Job Id: %s\n", jid);
		fprintf(outmail, "Job Name:   %s\n",
			get_jattr_str(pjob, JOB_ATR_jobname));
	}
	if (stdmessage)
		fprintf(outmail, "%s\n", stdmessage);
	if (text != NULL)
		fprintf(outmail, "%s\n", text);
	fclose(outmail);

	exit(0);
}
/**
 * @brief
 * 		svr_mailowner - Send mail to owner of a job when an event happens that
 *		requires mail, such as the job starts, ends or is aborted.
 *		The event is matched against those requested by the user.
 *		For Unix/Linux, a child is forked to not hold up the Server.  This child
 *		will fork/exec sendmail and pipe the To, Subject and body to it.
 *
 * @param[in]	pjob	-	ptr to job (null for server based mail)
 * @param[in]	mailpoint	-	note, single character
 * @param[in]	force	-	if set, force mail delivery
 * @param[in]	text	-	additional message text
 */
void
svr_mailowner(job *pjob, int mailpoint, int force, char *text)
{
	svr_mailowner_id(NULL, pjob, mailpoint, force, text);
}

/**
 * @brief
 * 		Send mail to owner of a reservation when an event happens that
 *		requires mail, such as the reservation starts, ends or is aborted.
 *		The event is matched against those requested by the user.
 *		For Unix/Linux, a child is forked to not hold up the Server.  This child
 *		will fork/exec sendmail and pipe the To, Subject and body to it.
 *
 * @param[in]	presv	-	pointer to the reservation structure
 * @param[in]	mailpoint	-	which mail event is triggering the send
 * @param[in]	force	-	if non-zero, force the mail even if not requested
 * @param[in]	text	-	the body text of the mail message
 *
 * @return	none
 */
void
svr_mailownerResv(resc_resv *presv, int mailpoint, int force, char *text)
{
	int	 i;
	int	 addmailhost;
	char    *mailer;
	char	*mailfrom;
	char	 mailto[MAIL_ADDR_BUF_LEN];
	int	 mailaddrlen = 0;
	struct array_strings *pas;
	char	*pat;
	char	*stdmessage = NULL;

	FILE	*outmail;
	pid_t	 mcpid;

	if (force != MAIL_FORCE) {
		/*Not forcing out mail regardless of mailpoint */

		if (presv->ri_wattr[(int)RESV_ATR_mailpnts].at_flags &ATR_VFLAG_SET) {
			/*user has set one or mode mailpoints is this one included?*/
			if (strchr(presv->ri_wattr[(int)RESV_ATR_mailpnts].at_val.at_str,
				mailpoint) == NULL)
				return;
		} else {
			/*user hasn't bothered to set any mailpoints so default to
			 *sending mail only in the case of reservation deletion and
			 *reservation confirmation
			 */
			if ((mailpoint != MAIL_ABORT) && (mailpoint != MAIL_CONFIRM))
				return;
		}
	}

	if (presv->ri_wattr[(int)RESV_ATR_mailpnts].at_flags &ATR_VFLAG_SET) {
		if (strchr(presv->ri_wattr[(int)RESV_ATR_mailpnts].at_val.at_str,
			MAIL_NONE) != NULL)
			return;
	}

	/*
	 * ok, now we will fork a process to do the mailing to not
	 * hold up the server's other work.
	 */

	mcpid = fork();
	if (mcpid == -1) { /* Error on fork */
		log_err(errno, __func__, "fork failed\n");
		return;
	}
	if (mcpid > 0)
		return;		/* its all up to the child now */

	/*
	 * From here on, we are a child process of the server.
	 * Fix up file descriptors and signal handlers.
	 */

	net_close(-1);
	tpp_terminate();

	/* Unprotect child from being killed by kernel */
	daemon_protect(0, PBS_DAEMON_PROTECT_OFF);

	if (is_attr_set(&server.sv_attr[(int)SVR_ATR_mailer]))
		mailer = server.sv_attr[(int)SVR_ATR_mailer].at_val.at_str;
	else
		mailer = SENDMAIL_CMD;

	/* Who is mail from, if SVR_ATR_mailfrom not set use default */

	if (is_attr_set(&server.sv_attr[(int)SVR_ATR_mailfrom]))
		mailfrom = server.sv_attr[(int)SVR_ATR_mailfrom].at_val.at_str;
	else
		mailfrom = PBS_DEFAULT_MAIL;

	/* Who does the mail go to?  If mail-list, them; else owner */

	*mailto = '\0';
	if (presv->ri_wattr[(int)RESV_ATR_mailuser].at_flags & ATR_VFLAG_SET) {

		/* has mail user list, send to them rather than owner */

		pas = presv->ri_wattr[(int)RESV_ATR_mailuser].at_val.at_arst;
		if (pas != NULL) {
			for (i = 0; i < pas->as_usedptr; i++) {
				addmailhost = 0;
				mailaddrlen += strlen(pas->as_string[i]) + 2;
				if ((pbs_conf.pbs_mail_host_name)  &&
				    (strchr(pas->as_string[i], (int)'@') == NULL)) {
						/* no host specified in address and      */
						/* pbs_mail_host_name is defined, use it */
						mailaddrlen += strlen(pbs_conf.pbs_mail_host_name) + 1;
						addmailhost = 1;
				}
				if (mailaddrlen < sizeof(mailto)) {
					(void)strcat(mailto, pas->as_string[i]);
					if (addmailhost) {
						/* append pbs_mail_host_name */
						(void)strcat(mailto, "@");
						(void)strcat(mailto, pbs_conf.pbs_mail_host_name);
					} else {
					  	sprintf(log_buffer,"Email list is too long: \"%.77s...\"", mailto);
						log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_WARNING, presv->ri_qs.ri_resvID, log_buffer);
						break;
					}
					(void)strcat(mailto, " ");
				}
			}
		}

	} else {

		/* no mail user list, just send to owner */

		(void)strcpy(mailto, presv->ri_wattr[(int)RESV_ATR_resv_owner].at_val.at_str);
		/* if pbs_mail_host_name is set in pbs.conf, then replace the */
		/* host name with the name specified in pbs_mail_host_name    */
		if (pbs_conf.pbs_mail_host_name) {
			if ((pat = strchr(mailto, (int)'@')) != NULL)
				*pat = '\0';	/* remove existing @host */
			if ((strlen(mailto) + strlen(pbs_conf.pbs_mail_host_name) + 1) < sizeof(mailto)) {
				/* append the pbs_mail_host_name since it fits */
				strcat(mailto, "@");
				strcat(mailto, pbs_conf.pbs_mail_host_name);
			} else {
				if (pat)
					*pat = '@';	/* did't fit, restore the "at" sign */
			  	sprintf(log_buffer,"Email address is too long: \"%.77s...\"", mailto);
				log_event(PBSEVENT_JOB, PBS_EVENTCLASS_JOB, LOG_WARNING, presv->ri_qs.ri_resvID, log_buffer);
			}
		}
	}

	if ((outmail = svr_exec_mailer(mailer, mailfrom, mailto)) == NULL)
		exit(1);

	/* Pipe in mail headers: To: and Subject: */

	fprintf(outmail, "To: %s\n", mailto);
	fprintf(outmail, "Subject: PBS RESERVATION %s\n\n", presv->ri_qs.ri_resvID);

	/* Now pipe in "standard" message */

	switch (mailpoint) {

		case MAIL_ABORT:
			/*"Aborted by Server, Scheduler, or User "*/
			stdmessage = msg_resv_abort;
			break;

		case MAIL_BEGIN:
			/*"Reservation period starting"*/
			stdmessage = msg_resv_start;
			break;

		case MAIL_END:
			/*"Reservation terminated"*/
			stdmessage = msg_resv_end;
			break;

		case MAIL_CONFIRM:
			/*scheduler requested, "CONFIRM reservation"*/
			stdmessage = msg_resv_confirm;
			break;
	}

	fprintf(outmail, "PBS Reservation Id: %s\n", presv->ri_qs.ri_resvID);
	fprintf(outmail, "Reservation Name:   %s\n",
		presv->ri_wattr[(int)RESV_ATR_resv_name].at_val.at_str);
	if (stdmessage)
		fprintf(outmail, "%s\n", stdmessage);
	if (text != NULL)
		fprintf(outmail, "%s\n", text);
	fclose(outmail);

	exit(0);
}
