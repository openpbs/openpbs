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

#ifndef	_PBS_LICENSE_H
#define	_PBS_LICENSE_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <limits.h>
#include "work_task.h"
/* Node license types */

#define ND_LIC_TYPE_locked	'l'
#define ND_LIC_TYPE_cloud	'c'
#define ND_LIC_locked_str	"l"
#define ND_LIC_cloud_str	"c"

typedef struct {
	long licenses_min;		/* minimum no.of licenses to be kept handy 		*/
	long licenses_max;		/* maximum licenses that can be used			*/
	long licenses_linger_time;	/* time for which unused licenses can be kept		*/
	long licenses_checked_out;	/* licenses that are  checked out			*/
	long licenses_checkout_time;	/* time at which licenses were checked out		*/
	long licenses_total_needed;	/* licenses needed to license all nodes in the complex	*/
	int expiry_warning_email_yday;	/* expiry warning email sent on this day of the year	*/
} pbs_licensing_control;

typedef struct {
	int lu_max_hr;		/* max number of licenses used in the hour  */
	int lu_max_day;		/* max number of licenses used in the day   */
	int lu_max_month;	/* max number of licenses used in the month */
	int lu_max_forever;	/* max number of licenses used so far	    */
	int lu_day;		/* which day of month			    */
	int lu_month;		/* which month				    */
} pbs_licenses_high_use;

typedef struct {
	long licenses_global;		/* licenses available at pbs_license_info   */
	long licenses_local;		/* licenses that are checked out but unused */
	long licenses_used;		/* licenses in use			    */
	pbs_licenses_high_use licenses_high_use;

} pbs_license_counts;

enum node_topology_type {
	tt_hwloc,
	tt_Cray,
	tt_Win
};
typedef enum node_topology_type ntt_t;


extern pbs_list_head unlicensed_nodes_list;

#define PBS_MIN_LICENSING_LICENSES	0
#define PBS_MAX_LICENSING_LICENSES	INT_MAX
#define PBS_LIC_LINGER_TIME		31536000 /* keep extra licenses 1 year by default */
#define PBS_LICENSE_LOCATION		\
	 (pbs_licensing_location ?	\
	  pbs_licensing_location : "null" )

extern void unset_signature(void *, char *);
extern int release_node_lic(void *);

extern void license_nodes();
extern void init_licensing(struct work_task *ptask);
extern void reset_license_counters(pbs_license_counts *);
extern void remove_from_unlicensed_node_list(struct pbsnode *pnode);

/* Licensing-related variables */
extern char *pbs_licensing_location;
extern pbs_licensing_control licensing_control;
extern pbs_license_counts license_counts;
#ifdef	__cplusplus
}
#endif
#endif	/* _PBS_LICENSE_H */
