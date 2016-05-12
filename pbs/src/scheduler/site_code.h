/*
 * site_code.h - Site additions to scheduler code
 */

#ifdef NAS
#define	SHARE_FILE	"shares"
#define SORTED_FILE	"sortedjobs"


extern int site_bump_topjobs(resource_resv* resv);
extern int site_check_cpu_share(server_info *, status *, resource_resv *);
extern time_t site_decode_time(const char *val);
extern int site_dup_shares(server_info *, server_info *);
extern sh_amt *site_dup_share_amts(sh_amt *oldp);
extern share_info *site_find_alloc_share(server_info *, char *);
extern void site_free_shares(server_info *);
extern double site_get_share(resource_resv *);
extern void site_init_shares(server_info *sinfo);
extern int site_is_queue_topjob_set_aside(resource_resv* resv);
extern int site_is_share_king(status *policy);
extern void site_list_shares(FILE *fp, server_info *, const char *pfx, int);
extern void site_list_jobs(server_info *sinfo, resource_resv **rarray);
extern int site_parse_shares(char *fname);
extern resource_resv* site_pick_next_job(resource_resv** resresv_arr);
extern void site_resort_jobs(resource_resv *);
extern void site_restore_users(void);
extern void site_save_users(void);
extern void site_set_job_share(resource_resv *resresv);
extern void site_set_NAS_pri(job_info *, time_t, long);
extern void site_set_node_share(node_info *ninfo, resource *res);
extern int site_set_share_head(server_info *sinfo);
extern void site_set_share_type(server_info *, resource_resv *);
extern int site_tidy_server(server_info *sinfo);
extern void site_update_on_end(server_info *, queue_info *, resource_resv *);
extern void site_update_on_run(server_info *, queue_info *, resource_resv *,
	nspec **);
extern void site_vnode_inherit(node_info **);
#if     NAS_COMPAT10_4
extern char *site_create_provvnode(nspec **ns, resource_resv *resresv);
extern char *site_combine_exec_prov_vnode(char *exec, char *prov);
#endif
extern int check_for_cycle_interrupt(int);

extern int num_topjobs_per_queues;

extern int do_soft_cycle_interrupt;
extern int do_hard_cycle_interrupt;
extern int consecutive_interrupted_cycles;
extern time_t interrupted_cycle_start_time;

#endif
