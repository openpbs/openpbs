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

#ifndef _HOOK_FUNC_H
#define _HOOK_FUNC_H
#ifdef __cplusplus
extern "C" {
#endif

#include "work_task.h"
#include "job.h"
#include "hook.h"

/*
 * hook_func.h - structure definitions for hook objects
 *
 * Include Files Required:
 *	<sys/types.h>
 *	"list_link.h"
 *	"batch_request.h"
 *	"pbs_ifl.h"
 */

#define MOM_HOOK_ACTION_NONE 0
#define MOM_HOOK_ACTION_SEND_ATTRS 0x01
#define MOM_HOOK_ACTION_SEND_SCRIPT 0x02
#define MOM_HOOK_ACTION_DELETE 0x04
#define MOM_HOOK_ACTION_SEND_RESCDEF 0x08
#define MOM_HOOK_ACTION_DELETE_RESCDEF 0x10
#define MOM_HOOK_ACTION_SEND_CONFIG 0x20

/* MOM_HOOK_ACTION_SEND_RESCDEF is really not part of this */
#define MOM_HOOK_SEND_ACTIONS (MOM_HOOK_ACTION_SEND_ATTRS | MOM_HOOK_ACTION_SEND_SCRIPT | MOM_HOOK_ACTION_SEND_CONFIG)

struct mom_hook_action {
	char hookname[PBS_HOOK_NAME_SIZE];
	unsigned int action;
	unsigned int reply_expected; /* reply expected from mom for sent out actions */
	int do_delete_action_first;  /* force order between delete and send actions */
	long long int tid;	     /* transaction id to group actions under */
};

/* Return values to sync_mom_hookfilesTPP() function */
enum sync_hookfiles_result {
	SYNC_HOOKFILES_NONE,
	SYNC_HOOKFILES_SUCCESS_ALL,
	SYNC_HOOKFILES_SUCCESS_PARTIAL,
	SYNC_HOOKFILES_FAIL
};

typedef struct mom_hook_action mom_hook_action_t;

extern int add_mom_hook_action(mom_hook_action_t ***,
			       int *, char *, unsigned int, int, long long int);

extern int delete_mom_hook_action(mom_hook_action_t **, int,
				  char *, unsigned int);

extern mom_hook_action_t *find_mom_hook_action(mom_hook_action_t **,
					       int, char *);

extern void add_pending_mom_hook_action(void *minfo, char *, unsigned int);

extern void delete_pending_mom_hook_action(void *minfo, char *, unsigned int);

extern void add_pending_mom_allhooks_action(void *minfo, unsigned int);

extern int has_pending_mom_action_delete(char *);

extern void hook_track_save(void *, int);
extern void hook_track_recov(void);
extern int mc_sync_mom_hookfiles(void);
extern void uc_delete_mom_hooks(void *);
extern int sync_mom_hookfiles_count(void *);
extern void next_sync_mom_hookfiles(void);
extern void send_rescdef(int);
extern unsigned long get_hook_rescdef_checksum(void);
extern void mark_mom_hooks_seen(void);
extern int mom_hooks_seen_count(void);
extern void hook_action_tid_set(long long int);
extern long long int hook_action_tid_get(void);
extern void set_srv_pwr_prov_attribute(void);
extern void fprint_svrattrl_list(FILE *, char *, pbs_list_head *);

#ifdef _BATCH_REQUEST_H
extern int status_hook(hook *, struct batch_request *, pbs_list_head *, char *, size_t);
extern void mgr_hook_import(struct batch_request *);
extern void mgr_hook_export(struct batch_request *);
extern void mgr_hook_set(struct batch_request *);
extern void mgr_hook_unset(struct batch_request *);
extern void mgr_hook_create(struct batch_request *);
extern void mgr_hook_delete(struct batch_request *);
extern void req_stat_hook(struct batch_request *);

/* Hook script processing */
extern int server_process_hooks(int rq_type, char *rq_user, char *rq_host, hook *phook,
				int hook_event, job *pjob, hook_input_param_t *req_ptr,
				char *hook_msg, int msg_len, void (*pyinter_func)(void),
				int *num_run, int *event_initialized);
extern int process_hooks(struct batch_request *, char *, size_t, void (*)(void));
extern int recreate_request(struct batch_request *);

/* Server periodic hook call-back */
extern void run_periodic_hook(struct work_task *ptask);

extern int get_server_hook_results(char *input_file, int *accept_flag, int *reject_flag,
				   char *reject_msg, int reject_msg_size, job *pjob, hook *phook, hook_output_param_t *hook_output);
#endif

#ifdef __cplusplus
}
#endif
#endif /* _HOOK_FUNC_H */
