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

#ifndef _PROVISION_H
#define _PROVISION_H
#ifdef __cplusplus
extern "C" {
#endif

/*
 * provision.h - header file for maintaining provisioning related definitions
 *
 * These are linked into the server structure.  Entries are added or
 * updated upon the receipt of Track Provision Requests and are used to
 * satisfy Locate Provision requests.
 *
 * The main data is kept in the form of the track batch request so
 * that copying is easy.
 *
 * Other required header files:
 *	"server_limits.h"
 */

#ifdef WIN32
typedef HANDLE prov_pid;
#else
typedef pid_t prov_pid;
#endif /* WIN32 */

extern void prov_track_save(void);

/* Provisioning functions and structures*/
/**
 * @brief
 *
 */

struct prov_vnode_info {
	pbs_list_link al_link;
	char *pvnfo_vnode;
	char *pvnfo_aoe_req;
	char pvnfo_jobid[PBS_MAXSVRJOBID + 1]; /* job id */
	struct work_task *ptask_defer;
	struct work_task *ptask_timed;
};

/**
 * @brief
 *
 */

struct prov_tracking {
	time_t pvtk_mtime; /* time this entry modified */
	prov_pid pvtk_pid;
	char *pvtk_vnode;
	char *pvtk_aoe_req;
	struct prov_vnode_info *prov_vnode_info;
};

typedef char (*exec_vnode_listtype)[PBS_MAXHOSTNAME + 1]; /* typedef to pointer to an array*/

extern int check_and_enqueue_provisioning(job *, int *);

extern void do_provisioning(struct work_task *wtask);

#ifdef __cplusplus
}
#endif
#endif /* _PROVISION_H */
