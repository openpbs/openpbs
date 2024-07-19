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

#ifndef _SVRFUNC_H
#define _SVRFUNC_H
#ifdef __cplusplus
extern "C" {
#endif

/*
 * misc server function prototypes
 */

#include "net_connect.h"
#include "pbs_db.h"
#include "reservation.h"
#include "resource.h"
#include "pbs_sched.h"
#include "pbs_entlim.h"

extern int check_num_cpus(void);
extern int chk_hold_priv(long, int);
extern void close_client(int);
extern void scheduler_close(int);
extern int send_sched_cmd(pbs_sched *, int, char *);
extern void count_node_cpus(void);
extern int ctcpus(char *, int *);
extern void cvrt_fqn_to_name(char *, char *);
extern int failover_send_shutdown(int);
extern char *get_hostPart(char *);
extern int is_compose(int, int);
extern int is_compose_cmd(int, int, char **);
extern char *get_servername(unsigned int *);
extern void process_Areply(int);
extern void process_Dreply(int);
extern void process_DreplyTPP(int);
extern void process_request(int);
extern void process_dis_request(int);
extern int save_flush(void);
extern void save_setup(int);
extern int save_struct(char *, unsigned int);
extern int schedule_jobs(pbs_sched *);
extern int schedule_high(pbs_sched *);
extern void shutdown_nodes(void);
extern char *site_map_user(char *, char *);
extern char *site_map_resvuser(char *, char *);
extern void svr_disconnect(int);
extern void svr_disconnect_with_wait_option(int, int);
extern int svr_connect(pbs_net_t, unsigned int, void (*)(int), enum conn_type, int);
extern void svr_force_disconnect(int);
extern void svr_shutdown(int);
extern int svr_get_privilege(char *, char *);
extern int setup_nodes(void);
extern int setup_resc(int);
extern void update_job_node_rassn(job *, attribute *, enum batch_op);
extern void mark_node_down(char *, char *);
extern void mark_node_offline_by_mom(char *, char *);
extern void clear_node_offline_by_mom(char *, char *);
extern void mark_which_queues_have_nodes(void);
#ifndef DEBUG
extern void pbs_close_stdfiles(void);
#endif
extern int is_job_array(char *);
extern int get_queued_subjobs_ct(job *);
extern int parse_subjob_index(char *, char **, int *, int *, int *, int *);
extern int expand_resc_array(char *, int, int);
extern void resv_timer_init(void);
extern int validate_nodespec(char *);
extern long longto_kbsize(char *);
extern int is_vnode_up(char *);
extern char *convert_long_to_time(long);
extern int svr_chk_history_conf(void);
extern int update_svrlive(void);
extern void init_socket_licenses(char *);
extern void update_job_finish_comment(job *, int, char *);
extern void svr_saveorpurge_finjobhist(job *);
extern int recreate_exec_vnode(job *, char *, char *, char *, int);
extern void unset_extra_attributes(job *);
extern int node_delete_db(struct pbsnode *);
extern int pbsd_init(int);
extern int svr_chk_histjob(job *);
extern int chk_and_update_db_svrhost(void);
extern int apply_aoe_inchunk_rules(resource *, attribute *, void *, int);
extern int apply_select_inchunk_rules(resource *, attribute *, void *, int, int);
extern int svr_create_tmp_jobscript(job *, char *);
extern void unset_jobscript_max_size(void);
extern char *svr_load_jobscript(job *);
extern int direct_write_requested(job *);
extern void spool_filename(job *, char *, char *);
extern enum failover_state are_we_primary(void);
extern void license_more_nodes(void);
extern void reset_svr_sequence_window(void);
extern void reply_preempt_jobs_request(int, int, struct job *);
extern int copy_params_from_job(char *, resc_resv *);
extern int confirm_resv_locally(resc_resv *, struct batch_request *, char *);
extern int set_select_and_place(int, void *, attribute *);
extern int make_schedselect(attribute *, resource *, pbs_queue *, attribute *);
extern long long get_next_svr_sequence_id(void);
extern int compare_obj_hash(void *, int, void *);
extern void panic_stop_db();
extern void free_db_attr_list(pbs_db_attr_list_t *);
extern bool delete_pending_arrayjobs(struct batch_request *);

#ifdef _PROVISION_H
extern int find_prov_vnode_list(job *, exec_vnode_listtype *, char **);
#endif /* _PROVISION_H */

extern void *jobs_idx;

#ifdef _RESERVATION_H
extern int set_nodes(void *, int, char *, char **, char **, char **, int, int);
#endif /* _RESERVATION_H */

#ifdef _PBS_NODES_H
extern void tinsert2(const u_long, const u_long, mominfo_t *, struct tree **);
extern void *tdelete2(const u_long, const u_long, struct tree **);
extern void tfree2(struct tree **);
#ifdef _RESOURCE_H
extern int fix_indirect_resc_targets(struct pbsnode *, resource *, int, int);
#endif /* _RESOURCE_H */
#endif /* _PBS_NODES_H */

#ifdef _PBS_JOB_H
extern int assign_hosts(job *, char *, int);
extern void clear_exec_on_run_fail(job *);
extern void discard_job(job *, char *, int);
extern void post_rerun(struct work_task *);
extern void force_reque(job *);
extern void set_resc_assigned(void *, int, enum batch_op);
extern int is_ts_node(char *);
extern char *cnv_eh(job *);
extern char *find_ts_node(void);
extern void job_purge(job *);
extern void check_block(job *, char *);
extern void free_nodes(job *);
extern int job_route(job *);
extern void rel_resc(job *);
extern int remove_stagein(job *);
extern size_t check_for_cred(job *, char **);
extern void svr_mailowner(job *, int, int, char *);
extern void svr_mailowner_id(char *, job *, int, int, char *);
extern char *lastname(char *);
extern void chk_array_doneness(job *);
extern job *create_subjob(job *, char *, int *);
extern job *find_arrayparent(char *);
extern job *get_subjob_and_state(job *, int, char *, int *);
extern void update_sj_parent(job *, job *, char *, char, char);
extern void update_subjob_state_ct(job *);
extern char *subst_array_index(job *, char *);
#ifndef PBS_MOM
extern void svr_setjob_histinfo(job *, histjob_type);
extern void svr_histjob_update(job *, char, int);
extern char *form_attr_comment(const char *, const char *);
extern void complete_running(job *);
extern void am_jobs_add(job *);
extern int was_job_alteredmoved(job *);
extern void check_failed_attempts(job *);
#endif
#ifdef _QUEUE_H
extern int check_entity_ct_limit_max(job *, pbs_queue *);
extern int check_entity_ct_limit_queued(job *, pbs_queue *);
extern int check_entity_resc_limit_max(job *, pbs_queue *, attribute *);
extern int check_entity_resc_limit_queued(job *, pbs_queue *, attribute *);
extern int set_entity_ct_sum_max(job *, pbs_queue *, enum batch_op);
extern int set_entity_ct_sum_queued(job *, pbs_queue *, enum batch_op);
extern int set_entity_resc_sum_max(job *, pbs_queue *, attribute *, enum batch_op);
extern int set_entity_resc_sum_queued(job *, pbs_queue *, attribute *, enum batch_op);
extern int account_entity_limit_usages(job *, pbs_queue *, attribute *, enum batch_op, int);
extern void eval_chkpnt(job *pjob, attribute *queckp);
#endif /* _QUEUE_H */

#ifdef _BATCH_REQUEST_H
extern int svr_startjob(job *, struct batch_request *);
extern int svr_authorize_jobreq(struct batch_request *, job *);
extern int dup_br_for_subjob(struct batch_request *, job *, int (*)(struct batch_request *, job *));
extern void set_old_nodes(job *);
extern int send_job_exec_update_to_mom(job *, char *, int, struct batch_request *);
extern int free_sister_vnodes(job *, char *, char *, char *, int, struct batch_request *);
#ifdef _WORK_TASK_H
extern int send_job(job *, pbs_net_t, int, int, void (*)(struct work_task *), struct batch_request *);
extern int relay_to_mom(job *, struct batch_request *, void (*)(struct work_task *));
extern int relay_to_mom2(job *, struct batch_request *, void (*)(struct work_task *), struct work_task **);
extern int recreate_exec_vnode(job *, char *, char *, char *, int);
extern int send_job_exec_update_to_mom(job *, char *, int, struct batch_request *);
extern int free_sister_vnodes(job *, char *, char *, char *, int, struct batch_request *);
extern void indirect_target_check(struct work_task *);
extern void primary_handshake(struct work_task *);
extern void secondary_handshake(struct work_task *);
#endif /* _WORK_TASK_H */
#endif /* _BATCH_REQUEST_H */
#ifdef _TICKET_H
extern int write_cred(job *, char *, size_t);
extern int read_cred(job *, char **, size_t *);
extern int get_credential(char *, job *, int, char **, size_t *);
#endif /* _TICKET_H */
extern int local_move(job *, struct batch_request *);
extern int user_read_password(char *, char **, size_t *);

#endif /* _PBS_JOB_H */

#ifdef _BATCH_REQUEST_H
extern void req_quejob(struct batch_request *);
extern void req_jobcredential(struct batch_request *);
extern void req_usercredential(struct batch_request *);
extern void req_jobscript(struct batch_request *);
extern void req_commit(struct batch_request *);
extern void req_commit_now(struct batch_request *, job *);
extern void req_deletejob(struct batch_request *);
extern void req_holdjob(struct batch_request *);
extern void req_messagejob(struct batch_request *);
extern void req_py_spawn(struct batch_request *);
extern void req_relnodesjob(struct batch_request *);
extern void req_modifyjob(struct batch_request *);
extern void req_modifyReservation(struct batch_request *);
extern void req_orderjob(struct batch_request *);
extern void req_rescreserve(struct batch_request *);
extern void req_rescfree(struct batch_request *);
extern void req_shutdown(struct batch_request *);
extern void req_signaljob(struct batch_request *);
extern void req_mvjobfile(struct batch_request *);
extern void req_stat_node(struct batch_request *);
extern void req_track(struct batch_request *);
extern void req_stagein(struct batch_request *);
extern void req_resvSub(struct batch_request *);
extern void req_deleteReservation(struct batch_request *);
extern void req_reservationOccurrenceEnd(struct batch_request *);
extern void req_failover(struct batch_request *);
extern int put_failover(int, struct batch_request *);
extern void set_last_used_time_node(void *, int);

#endif /* _BATCH_REQUEST_H */

#ifdef _ATTRIBUTE_H
extern int check_que_enable(attribute *, void *, int);
extern int set_queue_type(attribute *, void *, int);
extern int chk_characteristic(struct pbsnode *pnode, int *pneed_todo);
extern int is_valid_str_resource(attribute *pattr, void *pobject, int actmode);
extern int setup_arrayjob_attrs(attribute *, void *, int);
extern int deflt_chunk_action(attribute *pattr, void *pobj, int mode);
extern int action_svr_iteration(attribute *pattr, void *pobj, int mode);
extern void update_node_rassn(attribute *, enum batch_op);
extern void update_job_node_rassn(job *, attribute *, enum batch_op);
extern int cvt_nodespec_to_select(char *, char **, size_t *, attribute *);
extern int is_valid_resource(attribute *pattr, void *pobject, int actmode);
extern int queuestart_action(attribute *pattr, void *pobject, int actmode);
extern int alter_eligibletime(attribute *pattr, void *pobject, int actmode);
extern int set_chunk_sum(attribute *pselectattr, attribute *pattr);
extern int update_resources_rel(job *, attribute *, enum batch_op);
extern int keepfiles_action(attribute *pattr, void *pobject, int actmode);
extern int removefiles_action(attribute *pattr, void *pobject, int actmode);

/* Functions below exposed as they are now accessed by the Python hooks */
extern void update_state_ct(attribute *, int *, attribute_def *attr_def);
extern void update_license_ct();

#ifdef _PBS_JOB_H
extern int job_set_wait(attribute *, void *, int);
#endif /* _PBS_JOB_H */
#ifdef _QUEUE_H
extern int chk_resc_limits(attribute *, pbs_queue *);
extern int set_resc_deflt(void *, int, pbs_queue *);
extern void queue_route(pbs_queue *);
extern int que_purge(pbs_queue *);
#endif /* _QUEUE_H */
#endif /* _ATTRIBUTE_H */

#ifdef PBS_MOM
extern void addrinsert(const unsigned long);
extern int addrfind(const unsigned long);
#endif /* PBS_MOM */

#ifdef PBS_NET_H
extern int svr_connect(pbs_net_t, unsigned int, void (*)(int), enum conn_type, int);
#endif /* PBS_NET_H */
#ifdef _WORK_TASK_H
extern void release_req(struct work_task *);
#ifdef _BATCH_REQUEST_H
extern int issue_Drequest(int, struct batch_request *, void (*)(), struct work_task **, int);
#endif /* _BATCH_REQUEST_H */
#endif /* _WORK_TASK_H */

#ifdef _RESERVATION_H
extern void is_resv_window_in_future(resc_resv *);
extern void resv_setResvState(resc_resv *, int, int);
extern void is_resv_window_in_future(resc_resv *);
extern int gen_task_EndResvWindow(resc_resv *);
extern int gen_future_deleteResv(resc_resv *, long);
extern int gen_deleteResv(resc_resv *, long);
extern int node_avail(spec_and_context *, int *, int *, int *, int *);
extern int node_avail_complex(spec_and_context *, int *, int *, int *, int *);
extern int node_reserve(spec_and_context *, pbs_resource_t);
extern void node_unreserve(pbs_resource_t);
extern int node_spec(struct spec_and_context *, int);
extern int notify_scheds_about_resv(int, resc_resv *);
extern char *create_resv_destination(resc_resv *presv);
#endif /* _RESERVATION_H */

#ifdef _LIST_LINK_H
/*
 * This structure is used to hold information for a runjob batch request
 * from a client (that is not the Scheduler) which is being forwarded to
 * the Scheduler for consideration.   Since the Scheduler will make many
 * requests to the Server before replying to this request, the normal
 * request/reply mechanism breaks down.
 *
 * The request currently may be in the following states:
 *	Pending - waiting for the next scheduling cycle
 *	Sent    - sent to the Scheduler
 * When the Scheduler deals with the request, it will use the Deferred
 * Scheduler Reply request;  the Server will look in the list for one with
 * a matching Job ID and on finding it, reply to the original runjob request
 * and remove the structure from the list.
 */
struct deferred_request {
	pbs_list_link dr_link;
	char dr_id[PBS_MAXSVRJOBID + 1];
	struct batch_request *dr_preq;
	int dr_sent; /* sent to Scheduler */
};

struct sched_deferred_request {
	pbs_list_link sdr_link;
	pbs_list_head sdr_deferred_req; /* list of deferred requests of the scheduler */
	pbs_sched *sdr_psched; /* Scheduler */
};

#endif /* _LIST_LINK_H */

/*
 * The following is used are req_stat.c and req_select.c
 * Also defined in status_job.c
 */
#ifdef STAT_CNTL
struct select_list {
	struct select_list *sl_next; /* ptr to next in list   */
	enum batch_op sl_op;	     /* comparison operator   */
	attribute_def *sl_def;	     /* ptr to attr definition, for at_comp */
	int sl_atindx;		     /* index into attribute_def, for type */
	attribute sl_attr;	     /* the attribute (value) */
};

/* used in req_stat_job */
struct stat_cntl {
	int sc_XXXX;
	int sc_type;
	int sc_XXXY;
	int sc_conn;
	pbs_queue *sc_pque;
	struct batch_request *sc_origrq;
	struct select_list *sc_select;
	void (*sc_post)(struct stat_cntl *);
	char sc_jobid[PBS_MAXSVRJOBID + 1];
};

extern int status_job(job *, struct batch_request *, svrattrl *, pbs_list_head *, int *, int);
extern int status_subjob(job *, struct batch_request *, svrattrl *, int, pbs_list_head *, int *, int);
extern int stat_to_mom(job *, struct stat_cntl *);

#endif /* STAT_CNTL */
#ifdef __cplusplus
}
#endif
#endif /* _SVRFUNC_H */
