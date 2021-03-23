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


#ifndef _PBS_INTERNAL_H
#define	_PBS_INTERNAL_H

#ifdef	__cplusplus
extern "C" {
#endif

#include "pbs_ifl.h"
#include "portability.h"
#include "libutil.h"
#include "auth.h"

/*
 *
 *  pbs_internal.h
 *  This file contains all the definitions that are used by internal tools/cmds
 *  by pbs/pbs suite products like Aif.
 *
 */

/* node-attribute values (state,ntype) */

#define	ND_free			"free"
#define ND_offline		"offline"
#define ND_offline_by_mom	"offline_by_mom"
#define ND_down			"down"
#define ND_Stale		"Stale"
#define ND_jobbusy		"job-busy"
#define ND_job_exclusive	"job-exclusive"
#define ND_resv_exclusive	"resv-exclusive"
#define ND_job_sharing		"job-sharing"
#define ND_busy			"busy"
#define ND_state_unknown	"state-unknown"
#define ND_prov			"provisioning"
#define ND_wait_prov		"wait-provisioning"
#define ND_maintenance		"maintenance"
#define ND_pbs			"PBS"
#define ND_Default_Shared	"default_shared"
#define ND_Default_Excl		"default_excl"
#define ND_Default_Exclhost	"default_exclhost"
#define ND_Ignore_Excl		"ignore_excl"
#define ND_Force_Excl		"force_excl"
#define ND_Force_Exclhost	"force_exclhost"
#define ND_Initializing		"initializing"
#define ND_unresolvable		"unresolvable"
#define ND_sleep			"sleep"

/* Defines for type of Attribute based on data type 			*/
/* currently limited to 4 bits (max number 15)				*/

#define ATR_TYPE_NONE		0	/* Not to be used */
#define ATR_TYPE_LONG		1	/* Long integer, also Boolean */
#define ATR_TYPE_CHAR		2	/* single character */
#define ATR_TYPE_STR		3	/* string, null terminated */
#define ATR_TYPE_ARST		4	/* Array of strings (char **) */
#define ATR_TYPE_SIZE		5	/* size (integer + suffix) */
#define ATR_TYPE_RESC		6	/* list type: resources only */
#define ATR_TYPE_LIST		7	/* list type:  dependencies, unkn, etc */
#define ATR_TYPE_ACL		8	/* Access Control Lists */
#define ATR_TYPE_LL		9	/* Long (64 bit) integer */
#define ATR_TYPE_SHORT	10	/* short integer    */
#define ATR_TYPE_BOOL		11	/* boolean	    */
#define ATR_TYPE_JINFOP	13	/* struct jobinfo*  */
#define ATR_TYPE_FLOAT	14	/* Float  */
#define ATR_TYPE_ENTITY	15	/* FGC Entity Limit */
/* WARNING: adding anther WILL overflow the type field in the attribut_def */

/* Defines for  Flag field in attribute_def */

#define ATR_DFLAG_USRD   0x01	/* User client can read (status) attribute */
#define ATR_DFLAG_USWR   0x02	/* User client can write (set)   attribute */
#define ATR_DFLAG_OPRD   0x04	/* Operator client can read   attribute */
#define ATR_DFLAG_OPWR   0x08	/* Operator client can write  attribute */
#define ATR_DFLAG_MGRD   0x10	/* Manager client can read  attribute */
#define ATR_DFLAG_MGWR   0x20	/* Manager client can write attribute */
#define ATR_DFLAG_OTHRD	 0x40	/* Reserved */
#define ATR_DFLAG_Creat	 0x80	/* Can be set on create only */
#define ATR_DFLAG_SvRD	 0x100	/* job attribute is sent to server on move */
#define ATR_DFLAG_SvWR	 0x200	/* job attribute is settable by server/Sch */
#define ATR_DFLAG_MOM    0x400	/* attr/resc sent to MOM "iff" set	   */
#define ATR_DFLAG_RDACC  0x515	/* Read access mask  */
#define ATR_DFLAG_WRACC  0x6AA	/* Write access mask */
#define ATR_DFLAG_ACCESS 0x7ff	/* Mask access flags */

#define ATR_DFLAG_ALTRUN 0x0800	/* (job) attr/resc is alterable in Run state  */
#define ATR_DFLAG_NOSAVM 0x1000	/* object not saved on attribute modify       */
#define ATR_DFLAG_SELEQ  0x2000	/* attribute is only selectable eq/ne	      */
#define ATR_DFLAG_RASSN  0x4000 /* resc in server/queue resources_assigned    */
#define ATR_DFLAG_ANASSN 0x8000  /* resource in all node resources_assigned  */
#define ATR_DFLAG_FNASSN 0x10000 /* resource in 1st node resources_assigned  */
#define ATR_DFLAG_CVTSLT 0x20000 /* used in or converted to select directive */
#define ATR_DFLAG_SCGALT 0x40000 /* if altered during sched cycle dont run job*/
#define ATR_DFLAG_HIDDEN  0x80000 /* if set, keep attribute hidden to client */

#define SHUT_MASK	0xf
#define SHUT_WHO_MASK   0x1f0
#define SHUT_SIG	8
#define SHUT_WHO_SCHED  0x10	/* also shutdown Scheduler	  */
#define SHUT_WHO_MOM    0x20	/* also shutdown Moms		  */
#define SHUT_WHO_SECDRY 0x40	/* also shutdown Secondary Server */
#define SHUT_WHO_IDLESECDRY 0x80  /* idle the Secondary Server    */
#define SHUT_WHO_SECDONLY   0x100 /* shut down the Secondary only */


#define SIG_RESUME	"resume"
#define SIG_SUSPEND	"suspend"
#define SIG_TermJob	"TermJob"
#define SIG_RERUN	"Rerun"
#define SIG_ADMIN_SUSPEND "admin-suspend"
#define SIG_ADMIN_RESUME "admin-resume"


#define PLACE_Group	"group"
#define PLACE_Excl	"excl"
#define PLACE_ExclHost	"exclhost"
#define PLACE_Shared	"shared"
#define PLACE_Free	"free"
#define PLACE_Pack	"pack"
#define PLACE_Scatter	"scatter"
#define PLACE_VScatter	"vscatter"


#define ATR_TRUE	"True"
#define ATR_FALSE	"False"

#ifdef WIN32
#define	ESC_CHAR	'^'	/* commonly used in windows cmd shell */
#else
#define	ESC_CHAR	'\\'
#endif

/* set of characters that are not allowed in a queue name */
#define INVALID_QUEUE_NAME_CHARS "`~!$%^&*()+=<>?;'\"|"

/*constant related to sum of string lengths for above strings*/
#define	MAX_ENCODE_BFR		100

/* Default value of Node fail requeue (ATTR_nodefailrq)*/
#define PBS_NODE_FAIL_REQUEUE_DEFAULT	310

/* Default value of preempt_queue_prio */
#define PBS_PREEMPT_QUEUE_PRIO_DEFAULT	150

/* Default value of server_dyn_res_alarm */
#define PBS_SERVER_DYN_RES_ALARM_DEFAULT	30

/* Default value of preempt_prio */
#define PBS_PREEMPT_PRIO_DEFAULT	"express_queue, normal_jobs"

/* Default value of preempt_order */
#define PBS_PREEMPT_ORDER_DEFAULT	"SCR"

/* Default value of preempt_sort */
#define PBS_PREEMPT_SORT_DEFAULT	"min_time_since_start"

/* Structure to store each server instance details */
typedef struct pbs_server_instance {
	char name[PBS_MAXSERVERNAME + 1];
	unsigned int port;
} psi_t;

struct pbs_config
{
	unsigned loaded:1;			/* has the conf file been loaded? */
	unsigned load_failed:1;		/* previously loaded and failed */
	unsigned start_server:1;		/* should the server be started */
	unsigned start_mom:1;			/* should the mom be started */
	unsigned start_sched:1;		/* should the scheduler be started */
	unsigned start_comm:1; 		/* should the comm daemon be started */
	unsigned locallog:1;			/* do local logging */
	char **supported_auth_methods;		/* supported auth methods on server */
	char encrypt_method[MAXAUTHNAME + 1];	/* auth method to used for encrypt/decrypt data */
	char auth_method[MAXAUTHNAME + 1];	/* default auth_method to used by client */
	unsigned int sched_modify_event:1;	/* whether to trigger modifyjob hook event or not */
	unsigned syslogfac;		        /* syslog facility */
	unsigned syslogsvr;			/* min priority to log to syslog */
	unsigned int batch_service_port;	/* PBS batch_service_port */
	unsigned int batch_service_port_dis;	/* PBS batch_service_port_dis */
	unsigned int mom_service_port;	/* PBS mom_service_port */
	unsigned int manager_service_port;	/* PBS manager_service_port */
	unsigned int pbs_data_service_port;    /* PBS data_service port */
	char *pbs_conf_file;			/* full path of the pbs.conf file */
	char *pbs_home_path;			/* path to the pbs home dir */
	char *pbs_exec_path;			/* path to the pbs exec dir */
	char *pbs_server_name;		/* name of PBS Server, usually hostname of host on which PBS server is executing */
	unsigned int pbs_num_servers;	/* currently configured number of instances */
	psi_t *psi;						/* array of pbs server instances loaded from comma separated host:port[,host:port] */
	char *psi_str;			/* psi in string format */
	char *cp_path;			/* path to local copy function */
	char *scp_path;			/* path to ssh */
	char *rcp_path;			/* path to pbs_rsh */
	char *pbs_demux_path;			/* path to pbs demux */
	char *pbs_environment;		/* path to pbs_environment file */
	char *iff_path;			/* path to pbs_iff */
	char *pbs_primary;			/* FQDN of host with primary server */
	char *pbs_secondary;			/* FQDN of host with secondary server */
	char *pbs_mom_home;			/* path to alternate home for Mom */
	char *pbs_core_limit;			/* RLIMIT_CORE setting */
	char *pbs_data_service_host;		/* dataservice host */
	char *pbs_tmpdir;			/* temporary file directory */
	char *pbs_server_host_name;	/* name of host on which Server is running */
	char *pbs_public_host_name;	/* name of the local host for outgoing connections */
	char *pbs_mail_host_name;	/* name of host to which to address mail */
	char *pbs_smtp_server_name;   /* name of SMTP host to which to send mail */
	char *pbs_output_host_name;	/* name of host to which to stage std out/err */
	unsigned pbs_use_compression:1;	/* whether pbs should compress communication data */
	unsigned pbs_use_mcast:1;		/* whether pbs should multicast communication */
	char *pbs_leaf_name;			/* non-default name of this leaf in the communication network */
	char *pbs_leaf_routers;		/* for this leaf, the optional list of routers to talk to */
	char *pbs_comm_name;			/* non-default name of this router in the communication network */
	char *pbs_comm_routers;		/* for this router, the optional list of other routers to talk to */
	long  pbs_comm_log_events;      /* log_events for pbs_comm process, default 0 */
	unsigned int pbs_comm_threads;	/* number of threads for router, default 4 */
	char *pbs_mom_node_name;	/* mom short name used for natural node, default NULL */
	char *pbs_lr_save_path;		/* path to store undo live recordings */
	unsigned int pbs_log_highres_timestamp; /* high resolution logging */
	unsigned int pbs_sched_threads;	/* number of threads for scheduler */
	char *pbs_daemon_service_user; /* user the scheduler runs as */
	char current_user[PBS_MAXUSER+1]; /* current running user */
#ifdef WIN32
	char *pbs_conf_remote_viewer; /* Remote viewer client executable for PBS GUI jobs, along with launch options */
#endif
};

extern struct pbs_config pbs_conf;

/*
 * NOTE: PBS_CONF_PATH is no longer defined here. It has moved into
 * the pbs_config.h file generated by configure and has been renamed
 * to PBS_CONF_FILE to reflect the environment variable that can
 * now override the value defined at compile time.
 */

/* names in the pbs.conf file */
#define PBS_CONF_START_SERVER	"PBS_START_SERVER"	/* start the server? */
#define PBS_CONF_START_MOM	"PBS_START_MOM"		   /* start the mom? */
#define PBS_CONF_START_SCHED	"PBS_START_SCHED"    /* start the scheduler? */
#define PBS_CONF_START_COMM 	"PBS_START_COMM"    /* start the comm? */
#define PBS_CONF_LOCALLOG	"PBS_LOCALLOG"	/* non-zero to force logging */
#define PBS_CONF_SYSLOG		"PBS_SYSLOG"	  /* non-zero for syslogging */
#define PBS_CONF_SYSLOGSEVR	"PBS_SYSLOGSEVR"  /* severity lvl for syslog */
#define PBS_CONF_BATCH_SERVICE_PORT	     "PBS_BATCH_SERVICE_PORT"
#define PBS_CONF_BATCH_SERVICE_PORT_DIS	     "PBS_BATCH_SERVICE_PORT_DIS"
#define PBS_CONF_MOM_SERVICE_PORT	     "PBS_MOM_SERVICE_PORT"
#define PBS_CONF_MANAGER_SERVICE_PORT	     "PBS_MANAGER_SERVICE_PORT"
#define PBS_CONF_DATA_SERVICE_PORT           "PBS_DATA_SERVICE_PORT"
#define PBS_CONF_DATA_SERVICE_HOST           "PBS_DATA_SERVICE_HOST"
#define PBS_CONF_USE_COMPRESSION     	     "PBS_USE_COMPRESSION"
#define PBS_CONF_USE_MCAST		     "PBS_USE_MCAST"
#define PBS_CONF_LEAF_NAME		     "PBS_LEAF_NAME"
#define PBS_CONF_LEAF_ROUTERS		     "PBS_LEAF_ROUTERS"
#define PBS_CONF_COMM_NAME		     "PBS_COMM_NAME"
#define PBS_CONF_COMM_ROUTERS		     "PBS_COMM_ROUTERS"
#define PBS_CONF_COMM_THREADS		     "PBS_COMM_THREADS"
#define PBS_CONF_COMM_LOG_EVENTS	     "PBS_COMM_LOG_EVENTS"
#define PBS_CONF_HOME		"PBS_HOME"	 	 /* path to pbs home */
#define PBS_CONF_EXEC		"PBS_EXEC"		 /* path to pbs exec */
#define PBS_CONF_DEFAULT_NAME	"PBS_DEFAULT"	  /* old name for PBS_SERVER */
#define PBS_CONF_SERVER_NAME	"PBS_SERVER"	   /* name of the pbs server */
#define PBS_CONF_SERVER_INSTANCES	"PBS_SERVER_INSTANCES" /* comma separated list (host:port) of server instances */
#define PBS_CONF_INSTALL_MODE    "PBS_INSTALL_MODE" /* PBS installation mode */
#define PBS_CONF_RCP		"PBS_RCP"
#define PBS_CONF_CP		"PBS_CP"
#define PBS_CONF_SCP		"PBS_SCP"		      /* path to ssh */
#define PBS_CONF_ENVIRONMENT    "PBS_ENVIRONMENT" /* path to pbs_environment */
#define PBS_CONF_PRIMARY	"PBS_PRIMARY"  /* Primary Server in failover */
#define PBS_CONF_SECONDARY	"PBS_SECONDARY"	/* Secondary Server failover */
#define PBS_CONF_MOM_HOME	"PBS_MOM_HOME"  /* alt Mom home for failover */
#define PBS_CONF_CORE_LIMIT	"PBS_CORE_LIMIT"      /* RLIMIT_CORE setting */
#define PBS_CONF_SERVER_HOST_NAME "PBS_SERVER_HOST_NAME"
#define PBS_CONF_PUBLIC_HOST_NAME "PBS_PUBLIC_HOST_NAME"
#define PBS_CONF_MAIL_HOST_NAME "PBS_MAIL_HOST_NAME"
#define PBS_CONF_OUTPUT_HOST_NAME "PBS_OUTPUT_HOST_NAME"
#define PBS_CONF_SMTP_SERVER_NAME "PBS_SMTP_SERVER_NAME" /* Name of SMTP Host to send mail to */
#define PBS_CONF_TMPDIR		"PBS_TMPDIR"     /* temporary file directory */
#define PBS_CONF_AUTH		"PBS_AUTH_METHOD"
#define PBS_CONF_ENCRYPT_METHOD	"PBS_ENCRYPT_METHOD"
#define PBS_CONF_SUPPORTED_AUTH_METHODS	"PBS_SUPPORTED_AUTH_METHODS"
#define PBS_CONF_SCHEDULER_MODIFY_EVENT	"PBS_SCHEDULER_MODIFY_EVENT"
#define PBS_CONF_MOM_NODE_NAME	"PBS_MOM_NODE_NAME"
#define PBS_CONF_LR_SAVE_PATH	"PBS_LR_SAVE_PATH"
#define PBS_CONF_LOG_HIGHRES_TIMESTAMP	"PBS_LOG_HIGHRES_TIMESTAMP"
#define PBS_CONF_SCHED_THREADS	"PBS_SCHED_THREADS"
#define PBS_CONF_DAEMON_SERVICE_USER "PBS_DAEMON_SERVICE_USER"
#ifdef WIN32
#define PBS_CONF_REMOTE_VIEWER "PBS_REMOTE_VIEWER"	/* Executable for remote viewer application alongwith its launch options, for PBS GUI jobs */
#endif
#define LOCALHOST_FULLNAME "localhost.localdomain"
#define LOCALHOST_SHORTNAME "localhost"

/* someday the PBS_*_PORT definition will go away and only the	*/
/* PBS_*_SERVICE_NAME form will be used, maybe			*/

#define PBS_BATCH_SERVICE_NAME		"pbs"
#define PBS_BATCH_SERVICE_PORT		15001
#define PBS_BATCH_SERVICE_NAME_DIS	"pbs_dis"	/* new DIS port   */
#define PBS_BATCH_SERVICE_PORT_DIS	15001		/* new DIS port   */
#define PBS_MOM_SERVICE_NAME		"pbs_mom"
#define PBS_MOM_SERVICE_PORT		15002
#define PBS_MANAGER_SERVICE_NAME	"pbs_resmon"
#define PBS_MANAGER_SERVICE_PORT	15003
#define PBS_SCHEDULER_SERVICE_NAME	"pbs_sched"
#define PBS_SCHEDULER_SERVICE_PORT	15004
#define PBS_DATA_SERVICE_NAME           "pbs_dataservice"
#define PBS_DATA_SERVICE_STORE_NAME     "pbs_datastore"

/* Values for Job's ATTR_accrue_type */
enum accrue_types {
	JOB_INITIAL = 0,
	JOB_INELIGIBLE,
	JOB_ELIGIBLE,
	JOB_RUNNING,
	JOB_EXIT
};

#define	ACCRUE_NEW	"0"
#define	ACCRUE_INEL	"1"
#define	ACCRUE_ELIG	"2"
#define	ACCRUE_RUNN	"3"
#define	ACCRUE_EXIT	"4"


/* Default values for degraded reservation retry times boundary. 7200 seconds
 * is 2hrs and is considered to be a reasonable amount of time to wait before
 * confirming that a reservation is indeed degraded, and that an attempt to
 * reconfirm won't be made if the reservation is to start within the cutoff
 * time.
 */

#define RESV_RETRY_TIME_DEFAULT 600

#define PBS_RESV_CONFIRM_FAIL "PBS_RESV_CONFIRM_FAIL"   /* Used to inform server that a reservation could not be confirmed */
#define PBS_RESV_CONFIRM_SUCCESS "PBS_RESV_CONFIRM_SUCCESS"   /* Used to inform server that a reservation could be confirmed */
#define DEFAULT_PARTITION "pbs-default" /* Default partition name set on the reservation queue when the reservation is confirmed by default scheduler */

#define PBS_USE_IFF		1	/* pbs_connect() to call pbs_iff */


/* time flag 2030-01-01 01:01:00 for ASAP reservation */
#define PBS_RESV_FUTURE_SCH 1893488460L


/* this is the PBS default max_concurrent_provision value */
#define PBS_MAX_CONCURRENT_PROV 5

/* this is the PBS max lenth of quote parse error messages */
#define PBS_PARSE_ERR_MSG_LEN_MAX 50

/* this is the PBS defult jobscript_max_size default value is 100MB*/
#define DFLT_JOBSCRIPT_MAX_SIZE "100mb"

/* internal attributes */
#define ATTR_prov_vnode	"prov_vnode"	/* job attribute */
#define ATTR_ProvisionEnable	"provision_enable"  /* server attribute */
#define ATTR_provision_timeout	"provision_timeout" /* server attribute */
#define ATTR_node_set		"node_set"	    /* job attribute */
#define ATTR_sched_preempted    "ptime"   /* job attribute */
#define ATTR_restrict_res_to_release_on_suspend "restrict_res_to_release_on_suspend"	    /* server attr */
#define ATTR_resv_alter_revert		"reserve_alter_revert"
#define ATTR_resv_standing_revert	"reserve_standing_revert"

#ifndef IN_LOOPBACKNET
#define IN_LOOPBACKNET	127
#endif
#define LOCALHOST_SHORTNAME "localhost"

#if HAVE__BOOL
#include "stdbool.h"
#else
#ifndef __cplusplus
typedef enum { false, true } bool;
#endif
#endif

#ifdef _USRDLL		/* This is only for building Windows DLLs
			 * and not their static libraries
			 */

#ifdef DLL_EXPORT
#define DECLDIR __declspec(dllexport)
#else
#define DECLDIR __declspec(dllimport)
#endif

DECLDIR int pbs_connect_noblk(char *, int);

DECLDIR int pbs_query_max_connections(void);

DECLDIR int pbs_connection_set_nodelay(int);

DECLDIR int pbs_geterrno(void);

DECLDIR int pbs_py_spawn(int, char *, char **, char **);

DECLDIR int pbs_encrypt_pwd(unsigned char *, int *, unsigned char **, size_t *, const unsigned char *, const unsigned char *);

DECLDIR int pbs_decrypt_pwd(unsigned char *, int, size_t, unsigned char **, const unsigned char * , const unsigned char *);

DECLDIR char *
pbs_submit_with_cred(int, struct attropl *, char *,
	char *, char *, int, size_t, char *);

DECLDIR char *pbs_get_tmpdir(void);

DECLDIR char *pbs_strsep(char **, const char *);

DECLDIR int pbs_defschreply(int, int, char *, int, char *, char *);

DECLDIR int pbs_quote_parse(char *, char **, char **, int);

DECLDIR const char *pbs_parse_err_msg(int);

DECLDIR void pbs_prt_parse_err(char *, char *, int, int);

/* This was added to pbs_ifl.h for use by AIF */
DECLDIR int      pbs_isexecutable(char *);
DECLDIR char    *pbs_ispbsdir(char *, char *);
DECLDIR int      pbs_isjobid(char *);
DECLDIR int      check_job_name(char *, int);
DECLDIR int      chk_Jrange(char *);
DECLDIR time_t   cvtdate(char *);
DECLDIR int      locate_job(char *, char *, char *);
DECLDIR int      parse_destination_id(char *, char **, char **);
DECLDIR int      parse_at_list(char *, int, int);
DECLDIR int      parse_equal_string(char *, char **, char **);
DECLDIR int      parse_depend_list(char *, char **, int);
DECLDIR int      parse_stage_list(char *);
DECLDIR int      prepare_path(char *, char*);
DECLDIR void     prt_job_err(char *, int, char *);
DECLDIR int		 set_attr(struct attrl **, const char *, const char *);
DECLDIR int      set_attr_resc(struct attrl **, char *, char *, char *);
DECLDIR int      set_resources(struct attrl **, char *, int, char **);
DECLDIR int      cnt2server(char *);
DECLDIR int      cnt2server_extend(char *, char *);
DECLDIR int      get_server(char *, char *, char *);
DECLDIR int      PBSD_ucred(int, char *, int, char *, int);

#else

extern int pbs_connect_noblk(char *, int);

extern int pbs_connection_set_nodelay(int);

extern int pbs_geterrno(void);

extern int pbs_py_spawn(int, char *, char **, char **);

extern int pbs_encrypt_pwd(char *, int *, char **, size_t *, const unsigned char *, const unsigned char *);

extern int pbs_decrypt_pwd(char *, int, size_t, char **, const unsigned char *, const unsigned char *);

extern char *pbs_submit_with_cred(int, struct attropl *, char *,
	char *, char *, int, size_t , char *);

extern int pbs_query_max_connections(void);

extern char *pbs_get_tmpdir(void);

extern char *pbs_get_conf_var(char *);

extern char *get_psi_str();

extern FILE *pbs_popen(const char *, const char *);

extern int pbs_pkill(FILE *, int);

extern int pbs_pclose(FILE *);

extern char* pbs_strsep(char **, const char *);

extern int pbs_defschreply(int, int, char *, int, char *, char *);

extern char *pbs_strsep(char **, const char *);

extern int pbs_quote_parse(char *, char **, char **, int);

extern const char *pbs_parse_err_msg(int);

extern void pbs_prt_parse_err(char *, char *, int, int);

extern int pbs_rescquery(int, char **, int, int *, int *, int *, int *);

extern int pbs_rescreserve(int, char **, int, pbs_resource_t *);

extern int pbs_rescrelease(int, pbs_resource_t);

extern char *avail(int, char *);

extern int totpool(int, int);

extern int usepool(int, int);

extern enum vnode_sharing place_sharing_type(char *, enum vnode_sharing);

/* This was added to pbs_ifl.h for use by AIF */
extern int 	pbs_isexecutable(char *);
extern char 	*pbs_ispbsdir(char *, char *);
extern int 	pbs_isjobid(char *);
extern int      check_job_name(char *, int);
extern int      chk_Jrange(char *);
extern time_t   cvtdate(char *);
extern int      locate_job(char *, char *, char *);
extern int      parse_destination_id(char *, char **, char **);
extern int      parse_at_list(char *, int, int);
extern int      parse_equal_string(char *, char **, char **);
extern int      parse_depend_list(char *, char **, int);
extern int      parse_destination_id(char *, char **, char **);
extern int      parse_stage_list(char *);
extern int      prepare_path(char *, char*);
extern void     prt_job_err(char *, int, char *);
extern int     set_attr(struct attrl **, const char *, const char *);
#ifndef pbs_get_dataservice_usr
extern char*    pbs_get_dataservice_usr(char *, int);
#endif
extern char*	get_attr(struct attrl *, const char *, const char *);
extern int      set_resources(struct attrl **, char *, int, char **);
extern int      cnt2server(char *server);
extern int      cnt2server_extend(char *server, char *);
extern int      get_server(char *, char *, char *);
extern int      PBSD_ucred(int, char *, int, char *, int);
extern char	*encode_xml_arg_list(int, int, char **);
extern int	decode_xml_arg_list(char *, char *, char **, char ***);
extern int	decode_xml_arg_list_str(char *, char **);
extern char *convert_time(char *);
extern struct batch_status *bs_isort(struct batch_status *bs,
	int (*cmp_func)(struct batch_status*, struct batch_status *));
extern struct batch_status *bs_find(struct batch_status *, const char *);
extern void init_bstat(struct batch_status *);
extern int frame_psi(psi_t *, char *);


#endif /* _USRDLL */

extern const char pbs_parse_err_msges[][PBS_PARSE_ERR_MSG_LEN_MAX + 1];

#ifdef	__cplusplus
}
#endif

#endif	/* _PBS_INTERNAL_H */
