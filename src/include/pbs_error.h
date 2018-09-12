/*
 * Copyright (C) 1994-2018 Altair Engineering, Inc.
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
#ifndef	_PBS_ERROR_H
#define	_PBS_ERROR_H
#ifdef	__cplusplus
extern "C" {
#endif


/*
 * The error returns possible to a Batch Request
 *
 * Each error is prefixed with the string PBSE_ for Portable (Posix)
 * Batch System Error.  The numeric values start with 15000 since the
 * POSIX Batch Extensions Working group is 1003.15
 */

/*
 * The following error numbers should not be used while adding new PBS errors.
 * As a general guideline, do not use a number if number%256=0.
 * If PBS code erroneously uses these error numbers for future errors
 * and use them as command exit code, the behavior
 * will be erroneous on many standards-compliant systems.
 */
#define PBSE_DONOTUSE1 15360
#define PBSE_DONOTUSE2 15616
#define PBSE_DONOTUSE3 15872
#define PBSE_DONOTUSE4 16128
#define PBSE_DONOTUSE5 16384

#define PBSE_	15000

#define PBSE_NONE       0		/* no error */
#define PBSE_UNKJOBID	15001		/* Unknown Job Identifier */
#define PBSE_NOATTR	15002		/* Undefined Attribute */
#define PBSE_ATTRRO	15003		/* attempt to set READ ONLY attribute */
#define PBSE_IVALREQ	15004		/* Invalid request */
#define PBSE_UNKREQ	15005		/* Unknown batch request */
#define PBSE_TOOMANY	15006		/* Too many submit retries */
#define PBSE_PERM	15007		/* No permission */
#define PBSE_BADHOST	15008		/* access from host not allowed */
#define PBSE_JOBEXIST	15009		/* job already exists */
#define PBSE_SYSTEM	15010		/* system error occurred */
#define PBSE_INTERNAL	15011		/* internal server error occurred */
#define PBSE_REGROUTE	15012		/* parent job of dependent in rte que */
#define PBSE_UNKSIG	15013		/* unknown signal name */
#define PBSE_BADATVAL	15014		/* bad attribute value */
#define PBSE_MODATRRUN	15015		/* Cannot modify attrib in run state */
#define PBSE_BADSTATE	15016		/* request invalid for job state */
#define PBSE_UNKQUE	15018		/* Unknown queue name */
#define PBSE_BADCRED	15019		/* Invalid Credential in request */
#define PBSE_EXPIRED	15020		/* Expired Credential in request */
#define PBSE_QUNOENB	15021		/* Queue not enabled */
#define PBSE_QACESS	15022		/* No access permission for queue */
#define PBSE_BADUSER	15023		/* Bad user - no password entry */
#define PBSE_HOPCOUNT	15024		/* Max hop count exceeded */
#define PBSE_QUEEXIST	15025		/* Queue already exists */
#define PBSE_ATTRTYPE	15026		/* incompatable queue attribute type */
#define PBSE_OBJBUSY	15027		/* Object Busy (not empty) */
#define PBSE_QUENBIG	15028		/* Queue name too long */
#define PBSE_NOSUP	15029		/* Feature/function not supported */
#define PBSE_QUENOEN	15030		/* Cannot enable queue,needs add def */
#define PBSE_PROTOCOL	15031		/* Batch Protocol error */
#define PBSE_BADATLST	15032		/* Bad attribute list structure */
#define PBSE_NOCONNECTS	15033		/* No free connections */
#define PBSE_NOSERVER	15034		/* No server to connect to */
#define PBSE_UNKRESC	15035		/* Unknown resource */
#define PBSE_EXCQRESC	15036		/* Job exceeds Queue resource limits */
#define PBSE_QUENODFLT	15037		/* No Default Queue Defined */
#define PBSE_NORERUN	15038		/* Job Not Rerunnable */
#define PBSE_ROUTEREJ	15039		/* Route rejected by all destinations */
#define PBSE_ROUTEEXPD	15040		/* Time in Route Queue Expired */
#define PBSE_MOMREJECT  15041		/* Request to MOM failed */
#define PBSE_BADSCRIPT	15042		/* (qsub) cannot access script file */
#define PBSE_STAGEIN	15043		/* Stage In of files failed */
#define PBSE_RESCUNAV	15044		/* Resources temporarily unavailable */
#define PBSE_BADGRP	15045		/* Bad Group specified */
#define PBSE_MAXQUED	15046		/* Max number of jobs in queue */
#define PBSE_CKPBSY	15047		/* Checkpoint Busy, may be retries */
#define PBSE_EXLIMIT	15048		/* Limit exceeds allowable */
#define PBSE_BADACCT	15049		/* Bad Account attribute value */
#define PBSE_ALRDYEXIT	15050		/* Job already in exit state */
#define PBSE_NOCOPYFILE	15051		/* Job files not copied */
#define PBSE_CLEANEDOUT	15052		/* unknown job id after clean init */
#define PBSE_NOSYNCMSTR	15053		/* No Master in Sync Set */
#define PBSE_BADDEPEND	15054		/* Invalid dependency */
#define PBSE_DUPLIST	15055		/* Duplicate entry in List */
#define PBSE_DISPROTO	15056		/* Bad DIS based Request Protocol */
#define PBSE_EXECTHERE	15057		/* cannot execute there */
#define PBSE_SISREJECT	15058		/* sister rejected */
#define PBSE_SISCOMM	15059		/* sister could not communicate */
#define PBSE_SVRDOWN	15060		/* req rejected -server shutting down */
#define PBSE_CKPSHORT	15061		/* not all tasks could checkpoint */
#define PBSE_UNKNODE	15062		/* Named node is not in the list */
#define PBSE_UNKNODEATR	15063		/* node-attribute not recognized */
#define PBSE_NONODES	15064		/* Server has no node list */
#define PBSE_NODENBIG	15065		/* Node name is too big */
#define PBSE_NODEEXIST	15066		/* Node name already exists */
#define PBSE_BADNDATVAL	15067		/* Bad node-attribute value */
#define PBSE_MUTUALEX	15068		/* State values are mutually exclusive */
#define PBSE_GMODERR	15069		/* Error(s) during global modification of nodes */
#define PBSE_NORELYMOM	15070		/* could not contact Mom */
#define PBSE_NOTSNODE	15071		/* No time-share node available */
#define PBSE_RESV_NO_WALLTIME 15075	/* job reserv lacking walltime */
#define PBSE_JOBNOTRESV 15076		/* not a reservation job       */
#define PBSE_TOOLATE	15077		/* too late for job reservation*/
#define PBSE_IRESVE	15078		/* internal reservation-system error */
#define PBSE_UNKRESVTYPE 15079		/* unknown reservation type */
#define PBSE_RESVEXIST	15080		/* reservation already exists */
#define PBSE_resvFail	15081		/* reservation failed */
#define PBSE_genBatchReq 15082		/* batch request generation failed */
#define PBSE_mgrBatchReq 15083		/* qmgr batch request failed */
#define PBSE_UNKRESVID   15084		/* unknown reservation ID */
#define PBSE_delProgress 15085		/* delete already in progress */
#define PBSE_BADTSPEC    15086		/* bad time specification(s) */
#define PBSE_RESVMSG     15087		/* so reply_text can send back a msg */
#define PBSE_NOTRESV     15088		/* not a reservation */
#define PBSE_BADNODESPEC 15089		/* node(s) specification error */
#define PBSE_LICENSECPU	 15090		/* Licensed CPUs exceeded */
#define PBSE_LICENSEINV	 15091		/* License is invalid     */
#define PBSE_RESVAUTH_H	 15092		/* Host machine not authorized to */
/* submit reservations            */
#define PBSE_RESVAUTH_G	 15093		/* Requestor's group not authorized */
/* to submit reservations           */
#define PBSE_RESVAUTH_U	 15094		/* Requestor not authorized to make */
/* reservations                     */
#define PBSE_R_UID	15095		/* Bad effective UID for reservation */
#define PBSE_R_GID	15096		/* Bad effective GID for reservation */
#define PBSE_IBMSPSWITCH 15097		/* IBM SP Switch error */
#define PBSE_LICENSEUNAV 15098		/* Floating License unavailable  */
#define PBSE_NOSCHEDULER 15099		/* Unable to contact Scheduler */
#define PBSE_RESCNOTSTR  15100		/* resource is not of type string */
#define PBSE_SSIGNON_UNSET_REJECT 15101	/* SVR_ssignon_enable not set */
#define PBSE_SSIGNON_SET_REJECT 15102	/* SVR_ssignon_enable set */
#define PBSE_SSIGNON_BAD_TRANSITION1 15103 /* bad attempt: true to false */

/*
 * Error number 15104 for PBSE_SSIGNON_BAD_TRANSITION2
 * will no longer be supported because returning this error as
 * exit code would be erroneously interpreted as 0(success) on
 * systems whose exit code is a single byte (15104%256 = 0).
 * Changed error number from 15104 to 15207.
 * #define PBSE_SSIGNON_BAD_TRANSITION2 15104
 */
#define PBSE_SSIGNON_BAD_TRANSITION2 15207 /* bad attempt: false to true */

#define PBSE_SSIGNON_NOCONNECT_DEST  15105 /* couldn't connect to dest. host */

/* during a user migration request */
#define PBSE_SSIGNON_NO_PASSWORD     15106 /* no per user/per server password */
#define PBSE_MaxArraySize	     15107 /* max array size exceeded */
#define PBSE_INVALSELECTRESC	     15108 /* resc invalid in select spec */
#define PBSE_INVALJOBRESC	     15109 /* invalid job resource */
#define PBSE_INVALNODEPLACE	     15110 /* node invalid w/ place|select */
#define PBSE_PLACENOSELECT	     15111 /* cannot have place w/o select */
#define PBSE_INDIRECTHOP	     15112 /* too many indirect resc levels */
#define PBSE_INDIRECTBT		     15113 /* target resc undefined */
#define PBSE_NGBLUEGENE		     15114 /* No node_group_enable and bgl */
#define PBSE_NODESTALE		     15115 /* Cannot change state of stale nd */
#define PBSE_DUPRESC		     15116 /* cannot dup resc within a chunk */
#define PBSE_CONNFULL		     15117 /* server connection table full */
#define	PBSE_LICENSE_MIN_BADVAL      15118 /* bad value for pbs_license_min */
#define	PBSE_LICENSE_MAX_BADVAL      15119 /* bad value for pbs_license_max */
#define	PBSE_LICENSE_LINGER_BADVAL   15120 /* bad value for pbs_license_linger_time*/
#define PBSE_LICENSE_SERVER_DOWN     15121 /* License server is down */
#define PBSE_LICENSE_BAD_ACTION	     15122 /* Not allowed action with FLEX licensing */
#define PBSE_BAD_FORMULA	     15123 /* invalid sort formula */
#define PBSE_BAD_FORMULA_KW	     15124 /* invalid keyword in formula */
#define PBSE_BAD_FORMULA_TYPE	     15125 /* invalid resource type in formula */
#define PBSE_BAD_RRULE_YEARLY	     15126 /* reservation duration exceeds 1 year */
#define PBSE_BAD_RRULE_MONTHLY	     15127 /* reservation duration exceeds 1 month */
#define PBSE_BAD_RRULE_WEEKLY	     15128 /* reservation duration exceeds 1 week */
#define PBSE_BAD_RRULE_DAILY	     15129 /* reservation duration exceeds 1 day */
#define PBSE_BAD_RRULE_HOURLY	     15130 /* reservation duration exceeds 1 hour */
#define PBSE_BAD_RRULE_MINUTELY	     15131 /* reservation duration exceeds 1 minute */
#define PBSE_BAD_RRULE_SECONDLY	     15132 /* reservation duration exceeds 1 second */
#define PBSE_BAD_RRULE_SYNTAX	     15133 /* invalid recurrence rule syntax */
#define PBSE_BAD_RRULE_SYNTAX2	     15134 /* invalid recurrence rule syntax. COUNT/UNTIL required*/
#define PBSE_BAD_ICAL_TZ	     15135 /* Undefined timezone info directory */
#define PBSE_HOOKERROR		     15136 /* error encountered related to hooks */
#define PBSE_NEEDQUET		     15137 /* need queue type set */
#define PBSE_ETEERROR		     15138 /* not allowed to alter attribute when eligible_time_enable is off */
#define PBSE_HISTJOBID		     15139 /* History job ID */
#define PBSE_JOBHISTNOTSET	     15140 /* job_history_enable not SET */
#define PBSE_MIXENTLIMS		     15141 /* mixing old and new limit enformcement */
#define PBSE_ENTLIMCT		     15142 /* entity count limit exceeded */
#define PBSE_ENTLIMRESC		     15143 /* entity resource limit exceeded */
#define PBSE_ATVALERANGE	     15144 /* attribute value out of range */
#define PBSE_PROV_HEADERROR	     15145 /* not allowed to set provisioningattributes on head node */
#define PBSE_NODEPROV_NOACTION	     15146 /* cannot modify attribute while node is provisioning */
#define PBSE_NODEPROV		     15147 /* Cannot change state of provisioning node */
#define PBSE_NODEPROV_NODEL	     15148 /* Cannot del node if provisioning*/
#define PBSE_NODE_BAD_CURRENT_AOE    15149 /* current aoe is not one of resources_available.aoe */
#define PBSE_NOLOOPBACKIF	     15153 /* Local host does not have loopback interface configured. */
#define PBSE_IVAL_AOECHUNK	     15155 /* aoe not following chunk rules */
#define PBSE_JOBINRESV_CONFLICT      15156 /* job and reservation conflict */

#define PBSE_NORUNALTEREDJOB	     15157 /* cannot run altered/moved job */
#define PBSE_HISTJOBDELETED	     15158 /* Job was in F or M state . Its history deleted upon request. */
#define PBSE_NOHISTARRAYSUBJOB	     15159 /* Request invalid for finished array subjob */
#define PBSE_FORCE_QSUB_UPDATE       15160 /* a qsub action needs to be redone */
#define PBSE_SAVE_ERR		     15161 /* failed to save job or resv to database */
#define PBSE_MAX_NO_MINWT	     15162 /* no max walltime w/o min walltime */
#define PBSE_MIN_GT_MAXWT	     15163 /* min_walltime can not be > max_walltime */
#define PBSE_NOSTF_RESV		     15164 /* There can not be a shrink-to-fit reservation */
#define PBSE_NOSTF_JOBARRAY	     15165 /* There can not be a shrink-to-fit job array */
#define PBSE_NOLIMIT_RESOURCE	     15166 /* Resource limits can not be set for the resource */
#define PBSE_MOM_INCOMPLETE_HOOK     15167 /* mom hook not fully transferred */
#define PBSE_MOM_REJECT_ROOT_SCRIPTS 15168 /* no hook, root job scripts */
#define PBSE_HOOK_REJECT	     15169 /* mom receives a hook rejection */
#define PBSE_HOOK_REJECT_RERUNJOB    15170 /* hook rejection requiring a job rerun */
#define PBSE_HOOK_REJECT_DELETEJOB   15171 /* hook rejection requiring a job delete */
#define PBSE_IVAL_OBJ_NAME	     15172 /* invalid object name */

#define PBSE_JOBNBIG		     15173 /* Job name is too long */

#define PBSE_RESCBUSY		     15174 /* Resource is set on an object */
#define PBSE_JOBSCRIPTMAXSIZE	     15175 /* job script max size exceeded */
#define PBSE_BADJOBSCRIPTMAXSIZE     15176 /* user set size more than 2GB */
#define PBSE_WRONG_RESUME	     15177 /* user tried to resume job with wrong resume signal*/

/* Error code specific to altering reservation start and end times */
#define PBSE_RESV_NOT_EMPTY	     15178 /* cannot change start time of a non-empty reservation */
#define PBSE_STDG_RESV_OCCR_CONFLICT 15179 /* cannot change start time of a non-empty reservation */

#define PBSE_SOFTWT_STF		     15180 /* soft_walltime is incompatible with STF jobs */
#define PBSE_BAD_NODE_STATE          15181 /* node is in the wrong state for the operation */

/*
 ** 	Resource monitor specific
 */
#define PBSE_RMUNKNOWN	15201		/* resource unknown */
#define PBSE_RMBADPARAM	15202		/* parameter could not be used */
#define PBSE_RMNOPARAM	15203		/* a parameter needed did not exist */
#define PBSE_RMEXIST	15204		/* something specified didn't exist */
#define PBSE_RMSYSTEM	15205		/* a system error occured */
#define PBSE_RMPART	15206		/* only part of reservation made */
#define RM_ERR_UNKNOWN	PBSE_RMUNKNOWN
#define RM_ERR_BADPARAM	PBSE_RMBADPARAM
#define RM_ERR_NOPARAM	PBSE_RMNOPARAM
#define RM_ERR_EXIST	PBSE_RMEXIST
#define RM_ERR_SYSTEM	PBSE_RMSYSTEM

/* PBSE_SSIGNON_BAD_TRANSITION2 is using 15207 (see above) */

#define PBSE_TRYAGAIN	15208		/* Try the request again later */
#define PBSE_ALPSRELERR	15209		/* ALPS failed to release the resv */

#define PBSE_JOB_MOVED	15210		/* Job moved to another server */
#define PBSE_SCHEDEXIST	15211		/* Scheduler already exists */
#define PBSE_SCHED_NAME_BIG 15212	/* Scheduler name too long */
#define PBSE_UNKSCHED 15213		/* sched not in the list */
#define PBSE_SCHED_NO_DEL 15214		/* can not delete scheduler */
#define PBSE_SCHED_PRIV_EXIST 15215	/* Scheduler sched_priv directory already exists */
#define PBSE_SCHED_LOG_EXIST 15216	/* Scheduler sched_log directory already exists */
#define PBSE_ROUTE_QUE_NO_PARTITION  15217 /*Partition can not be assigned to route queue */
#define PBSE_CANNOT_SET_ROUTE_QUE 15218 /*Can not set queue type to route */
#define PBSE_QUE_NOT_IN_PARTITION 15219  /* Queue does not belong to the partition */
#define PBSE_PARTITION_NOT_IN_QUE 15220  /* Partition does not belong to the queue */
#define PBSE_INVALID_PARTITION_QUE 15221 /* Invalid partition to the queue */
#define PBSE_ALPS_SWITCH_ERR 15222	/* ALPS failed to do the suspend/resume */
#define PBSE_SCHED_OP_NOT_PERMITTED 15223 /* Operation not permitted on default scheduler */
#define PBSE_SCHED_PARTITION_ALREADY_EXISTS 15224 /* Partition already exists */

/* the following structure is used to tie error number      */
/* with text to be returned to a client, see svr_messages.c */

struct pbs_err_to_txt {
	int    err_no;
	char **err_txt;
};

extern char *pbse_to_txt(int);

/* This variable has been moved to Thread local storage
 * The define points to a function pointer which locates
 * the actual variable from the TLS of the calling thread
 */
#ifndef __PBS_ERRNO
#define __PBS_ERRNO
extern int *__pbs_errno_location(void);
#define pbs_errno (*__pbs_errno_location ())
#endif
#ifdef	__cplusplus
}
#endif
#endif	/* _PBS_ERROR_H */
