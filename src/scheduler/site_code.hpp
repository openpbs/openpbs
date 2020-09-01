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

/*
 * site_code.h - Site additions to scheduler code
 */

#ifdef NAS
#define	SHARE_FILE	"shares"
#define SORTED_FILE	"sortedjobs"

extern int site_bump_topjobs(resource_resv* resv, double delta);
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
extern resource_resv* site_find_runnable_res(resource_resv** resresv_arr);
extern void site_resort_jobs(resource_resv *);
extern void site_restore_users(void);
extern void site_save_users(void);
extern void site_set_job_share(resource_resv *resresv);
extern void site_set_NAS_pri(job_info *, time_t, long);
extern void site_set_node_share(node_info *ninfo, schd_resource *res);
extern int site_set_share_head(server_info *sinfo);
extern void site_set_share_type(server_info *, resource_resv *);
extern int site_should_backfill_with_job(status *policy, server_info *sinfo, resource_resv *resresv, int ntj, int nqtj, schd_error *err);
extern int site_tidy_server(server_info *sinfo);
extern void site_update_on_end(server_info *, queue_info *, resource_resv *);
extern void site_update_on_run(server_info *, queue_info *, resource_resv *,
	int flag, nspec **);
extern void site_vnode_inherit(node_info **);
extern int check_for_cycle_interrupt(int);

extern int num_topjobs_per_queues;

extern int do_soft_cycle_interrupt;
extern int do_hard_cycle_interrupt;
extern int consecutive_interrupted_cycles;
extern time_t interrupted_cycle_start_time;

#endif
