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

#ifndef _MOM_FUNC_H
#define _MOM_FUNC_H
#ifdef __cplusplus
extern "C" {
#endif

#include <stdio.h>

#ifndef MOM_MACH
#include "mom_mach.h"
#endif /* MOM_MACH */

#include "port_forwarding.h"
#include "batch_request.h"
#include "pbs_internal.h"

/* struct sig_tbl = used to hold map of local signal names to values */

struct sig_tbl {
	char *sig_name;
	int sig_val;
};

#define NUM_LCL_ENV_VAR 10

/* used by mom_main.c and requests.c for $usecp */

struct cphosts {
	char *cph_hosts;
	char *cph_from;
	char *cph_to;
#ifdef NAS /* localmod 009 */
	/* support $usecp rules that exclude a pattern */
	int cph_exclude;
#endif /* localmod 009 */
};
extern int cphosts_num;
extern struct cphosts *pcphosts;

/* used by mom_main.c and start_exec.c for TMPDIR */

extern char pbs_tmpdir[];

/* used by mom_main.c and start_exec.c for PBS_JOBDIR */
extern char pbs_jobdir_root[];
extern int pbs_jobdir_root_shared;
#define JOBDIR_DEFAULT "PBS_USER_HOME"

/* test bits */
#define PBSQA_DELJOB_SLEEP 1
#define PBSQA_DELJOB_CRASH 2
#define PBSQA_POLLJOB_CRASH 4
#define PBSQA_POLLJOB_SLEEP 8
#define PBSQA_NTBL_STATUS 16
#define PBSQA_NTBL_ADAPTER 32
#define PBSQA_NTBL_LOAD 64
#define PBSQA_NTBL_UNLOAD 128
#define PBSQA_NTBL_CLEAN 256
#define PBSQA_DELJOB_SLEEPLONG 512
#define PBSQA_NTBL_NOPORTS 1024

extern unsigned long QA_testing;

/* used by Mom for external actions */

enum Action_Event {		     /* enum should start with zero	*/
		    TerminateAction, /* On Job Termination		*/
		    ChkptAction,     /* On Checkpoint		*/
		    ChkptAbtAction,  /* On Checkpoint with abort	*/
		    RestartAction,   /* On Restart (chkpt)		*/
		    MultiNodeBusy,   /* when desktop goes keyboard busy */
		    LastAction	     /* Must be last entry		*/
};

enum Action_Verb {
	Default, /* default action  */
	Script,	 /* external script */
	Requeue	 /* requeue job     */
};

extern struct mom_action {
	char *ma_name;		  /* action name (noun)	     */
	int ma_timeout;		  /* allowable time for action */
	enum Action_Verb ma_verb; /* action verb		     */
	char *ma_script;	  /* absolute script path      */
	char **ma_args;		  /* args to pass to script    */
} mom_action[(int) LastAction];

/**
 * values for call_hup
 */
enum hup_action {
	HUP_CLEAR = 0, /* No HUP processing needed */
	HUP_REAL,      /* a HUP signal was received */
	HUP_INIT       /* a job failure requires init processing */
};

/**
 * Flag used to indicate that HUP processing should take place.
 */
extern enum hup_action call_hup;

extern int mock_run;

/* public funtions within MOM */

#ifdef _PBS_JOB_H

#define COMM_MATURITY_TIME 60 /* time when we consider a pbs_comm connection as mature */
#define MOM_DELTA_NORMAL 1    /* Normal mode of operation for time_delta_hellosvr function */
#define MOM_DELTA_RESET 0     /* Reset the values of time_delta_hellosvr function back to 1 */

typedef int (*pbs_jobfunc_t)(job *);
typedef int (*pbs_jobnode_t)(job *, hnodent *);
typedef int (*pbs_jobstream_t)(job *, int);
typedef int (*pbs_jobndstm_t)(job *, hnodent *, int);
typedef void (*pbs_jobvoid_t)(job *);
typedef void (*pbs_jobnodevoid_t)(job *, hnodent *);

extern pbs_jobnode_t job_join_extra;
extern pbs_jobndstm_t job_join_ack;
extern pbs_jobndstm_t job_join_read;
extern pbs_jobndstm_t job_setup_send;
extern pbs_jobstream_t job_setup_final;
extern pbs_jobvoid_t job_end_final;
extern pbs_jobfunc_t job_clean_extra;
extern pbs_jobvoid_t job_free_extra;
extern pbs_jobnodevoid_t job_free_node;

extern int local_supres(job *, int, struct batch_request *);
extern void post_suspend(job *, int);
extern void post_resume(job *, int);
extern void post_restart(job *, int);
extern void post_chkpt(job *, int);
extern int start_checkpoint(job *, int, struct batch_request *);
extern int local_checkpoint(job *, int, struct batch_request *);
extern int start_restart(job *, struct batch_request *);
extern int local_restart(job *, struct batch_request *);
extern int time_delta_hellosvr(int);

#ifdef WIN32
extern void wait_action(void);
#endif

typedef enum {
	HANDLER_FAIL = 0,
	HANDLER_SUCCESS = 1,
	HANDLER_REPARSE = 2
} handler_ret_t;
extern handler_ret_t set_boolean(const char *id, char *value, int *flag);
extern int do_susres(job *pjob, int which);
extern int error(char *string, int value);
extern int kill_job(job *, int sig);
extern int kill_task(pbs_task *, int sig, int dir);
extern void del_job_hw(job *);
extern void mom_deljob(job *);
extern void mom_deljob_wait2(job *);
extern int send_sisters_deljob_wait(job *);
extern void del_job_resc(job *);
extern int do_mom_action_script(int, job *, pbs_task *, char *,
				void (*)(job *, int));
extern enum Action_Verb chk_mom_action(enum Action_Event);
extern void mom_freenodes(job *);
extern void unset_job(job *, int);
struct passwd *check_pwd(job *);
extern char *set_shell(job *, struct passwd *);
extern void start_exec(job *);
extern void send_obit(job *, int);
extern void send_hellosvr(int);
extern void send_wk_job_idle(char *, int);
extern int site_job_setup(job *);
extern int site_mom_chkuser(job *);
extern int site_mom_postchk(job *, int);
extern int site_mom_prerst(job *);
extern int terminate_job(job *, int);
extern int mom_deljob_wait(job *);
extern int run_pelog(int which, char *file, job *pjob, int pe_io_type);
extern int is_joined(job *);
extern void update_jobs_status(void);
extern void calc_cpupercent(job *, unsigned long, unsigned long, time_t);
extern void dorestrict_user(void);
extern int task_save(pbs_task *ptask);
extern void send_join_job_restart(int, eventent *, int, job *, pbs_list_head *);
extern int send_resc_used_to_ms(int stream, job *pjob);
extern int recv_resc_used_from_sister(int stream, job *pjob, int nodeidx);
extern int is_comm_up(int);

/* Defines for pe_io_type, see run_pelog() */

#define PE_IO_TYPE_NULL -1
#define PE_IO_TYPE_ASIS 0
#define PE_IO_TYPE_STD 1
#define PE_PROLOGUE 1
#define PE_EPILOGUE 2

typedef enum {
	PRE_FINISH_SUCCESS,
	PRE_FINISH_SUCCESS_JOB_SETUP_SEND,
	PRE_FINISH_FAIL,
	PRE_FINISH_FAIL_JOB_SETUP_SEND,
	PRE_FINISH_FAIL_JOIN_EXTRA
} pre_finish_results_t;

#ifdef _LIBPBS_H
extern int open_std_file(job *, enum job_file, int, gid_t);
extern char *std_file_name(job *, enum job_file, int *keeping);
extern int task_recov(job *pjob);
extern int send_sisters(job *pjob, int com, pbs_jobndstm_t);
extern int send_sisters_inner(job *pjob, int com, pbs_jobndstm_t, char *);
extern int send_sisters_job_update(job *pjob);
extern int im_compose(int stream, char *jobid, char *cookie, int command, tm_event_t event, tm_task_id taskid, int version);
extern int message_job(job *pjob, enum job_file jft, char *text);
extern void term_job(job *pjob);
extern int start_process(pbs_task *pt, char **argv, char **envp, bool nodemux);
extern pre_finish_results_t pre_finish_exec(job *pjob, int do_job_setup_send);
extern void finish_exec(job *pjob);
extern void exec_bail(job *pjob, int code, char *txt);
extern int generate_pbs_nodefile(job *pjob, char *nodefile, int nodefile_sz, char *err_msg, int err_msg_sz);
extern int job_nodes_inner(struct job *pjob, hnodent **mynp);
extern int job_nodes(job *pjob);
extern int tm_reply(int stream, int version, int com, tm_event_t event);
#ifdef WIN32
extern void end_proc(void);
extern int dep_procinfo(pid_t pid, pid_t *psid, uid_t *puid, char *puname, size_t uname_len, char *comm, size_t comm_len);
#else
extern int dep_procinfo(pid_t, pid_t *, uid_t *, char *, size_t);
#endif
#ifdef NAS_UNKILL /* localmod 011 */
extern int kill_procinfo(pid_t, pid_t *, u_Long *);
#endif /* localmod 011 */
extern int dep_attach(pbs_task *ptask);
#endif /* _LIBPBS_H */

#ifdef _RESOURCE_H
extern u_long gettime(resource *pres);
extern u_long getsize(resource *pres);
extern int local_gettime(resource *, unsigned long *ret);
extern int local_getsize(resource *, unsigned long *ret);
#endif /* _RESOURCE_H */

#ifdef _BATCH_REQUEST_H
extern int start_checkpoint(job *, int abt, struct batch_request *pq);

#endif /* _BATCH_REQUEST_H */

#endif /* _PBS_JOB_H */

struct cpy_files {
	int stageout_failed; /* for stageout failed */
	int bad_files;	     /* for failed to stageout file */
	int from_spool;	     /* copy from spool */
	int file_num;	     /* no. of file name in file_list */
	int file_max;	     /* no. of file name that can reside in file_list */
	char **file_list;    /* list of file name to be deleted later*/
	int sandbox_private; /* for stageout with PRIVATE sandbox */
	char *bad_list;	     /* list of failed stageout filename */
	int direct_write;    /* whether direct write has requested by the job */
};
typedef struct cpy_files cpy_files;

#ifdef WIN32
enum stagefile_errcode {
	STAGEFILE_OK = 0,
	STAGEFILE_NOCOPYFILE,
	STAGEFILE_FATAL,
	STAGEFILE_BADUSER,
	STAGEFILE_LAST
};

struct copy_info {
	pbs_list_link al_link;	    /* link to all copy info list */
	char *jobid;		    /* job id to which this info belongs */
	job *pjob;		    /* pointer to job structure */
	struct work_task *ptask;    /* pointer to work task */
	struct batch_request *preq; /* pointer to batch request */
	pio_handles pio;	    /* process info struct */
};
typedef struct copy_info copy_info;

#define CPY_PIPE_BUFSIZE 4096 /* buffer size for pipe */
extern pbs_list_head mom_copyreqs_list;
extern void post_cpyfile(struct work_task *);
extern copy_info *get_copyinfo_from_list(char *);
#endif
extern char *tmpdirname(char *);
#ifdef NAS /* localmod 010 */
extern char *NAS_tmpdirname(job *);
#endif /* localmod 010 */
extern char *jobdirname(char *, char *);
extern void rmtmpdir(char *);
extern int local_or_remote(char **);
extern void add_bad_list(char **, char *, int);
extern int is_child_path(char *, char *);
extern int pbs_glob(char *, char *);
extern void rmjobdir(char *, char *, uid_t, gid_t, int);
extern int stage_file(int, int, char *, struct rqfpair *, int, cpy_files *, char *, char *);
#ifdef WIN32
extern int mktmpdir(char *, char *);
extern int mkjobdir(char *, char *, char *, HANDLE login_handle);
extern int isdriveletter(int);
extern void send_pcphosts(pio_handles *, struct cphosts *);
extern int send_rq_cpyfile_cred(pio_handles *, struct rq_cpyfile *);
extern int recv_pcphosts(void);
extern int recv_rq_cpyfile_cred(struct rq_cpyfile *);
extern int remdir(char *);
extern void check_err(const char *func_name, char *buf, int len);
#else
extern int mktmpdir(char *, uid_t, gid_t, struct var_table *);
extern int mkjobdir(char *, char *, uid_t, gid_t);
extern int impersonate_user(uid_t, gid_t);
extern void revert_from_user(void);
extern int open_file_as_user(char *path, int oflag, mode_t mode,
			     uid_t exuid, gid_t exgid);
#endif
extern int find_env_slot(struct var_table *, char *);
extern void bld_env_variables(struct var_table *, char *, char *);
extern void add_envp(char **, struct var_table *);
extern pid_t fork_me(int sock);

extern ssize_t readpipe(int pfd, void *vptr, size_t nbytes);
extern ssize_t writepipe(int pfd, void *vptr, size_t nbytes);
extern int get_la(double *);
extern void init_abort_jobs(int, pbs_list_head *);
extern void checkret(char **spot, int len);
extern void mom_nice(void);
extern void mom_unnice(void);
extern int mom_reader(int, int, char *);
extern int mom_reader_Xjob(int);
extern int mom_writer(int, int);
extern void log_mom_portfw_msg(char *msg);
extern void nodes_free(job *);
extern int open_demux(u_long, int);
extern int open_master(char **);
extern int open_slave(void);
extern char *rcvttype(int);
extern int rcvwinsize(int);
extern int remtree(char *);
extern void scan_for_exiting(void);
extern void scan_for_terminated(void);
extern int setwinsize(int);
extern void set_termcc(int);
extern int conn_qsub(char *host, long port);
extern int conn_qsub_resvport(char *host, long port);
extern int state_to_server(int, int);
extern int send_hook_vnl(void *vnl);
extern int hook_requests_to_server(pbs_list_head *);
extern int init_x11_display(struct pfwdsock *, int, char *, char *, char *);
extern int setcurrentworkdir(char *);
extern int becomeuser(job *);
extern int becomeuser_args(char *, uid_t, gid_t, gid_t);
extern void close_update_pipes(job *);
extern void mom_set_use_all(void);
void job_purge_mom(job *pjob);

/* From popen.c */
extern FILE *pbs_popen(const char *, const char *);
extern int pbs_pkill(FILE *, int);
extern int pbs_pclose(FILE *);

/* from mom_walltime.c */
extern void start_walltime(job *);
extern void update_walltime(job *);
extern void stop_walltime(job *);
extern void recover_walltime(job *);

/* Define for max xauth data*/
#define X_DISPLAY_LEN 512

/* Defines for when resource usage is polled by Mom */
#define MAX_CHECK_POLL_TIME 120
#define MIN_CHECK_POLL_TIME 10

/* For windows only, define the window station to use */
/* for launching processes. */
#define PBS_DESKTOP_NAME "PBSWS\\default"

/* max # of users that will be exempted from dorestrict_user process killing */
#ifdef NAS /* localmod 008 */
#define NUM_RESTRICT_USER_EXEMPT_UIDS 99
#else
#define NUM_RESTRICT_USER_EXEMPT_UIDS 10
#endif /* localmod 008 */

/* max length of the error message generated due to database issues */
#define PBS_MAX_DB_ERR 500

/* Defines for state_to_server */
#define UPDATE_VNODES 0
#define UPDATE_MOM_ONLY 1
#ifdef __cplusplus
}
#endif
#endif /* _MOM_FUNC_H */
