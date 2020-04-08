/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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
#ifndef	_PBS_LICENSE_H
#define	_PBS_LICENSE_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <limits.h>

/* Node license types */

#define ND_LIC_TYPE_locked	'l'
#define ND_LIC_TYPE_cloud	'c'
#define ND_LIC_locked_str	"l"
#define ND_LIC_cloud_str	"c"

struct license_used {
	int lu_max_hr;		/* max number of licenses used in the hour  */
	int lu_max_day;		/* max number of licenses used in the day   */
	int lu_max_month;	/* max number of licenses used in the month */
	int lu_max_forever;	/* running max number for ever 		    */
	int lu_day;		/* which day of month recording		    */
	int lu_month;		/* which month recording		    */
};

enum node_topology_type {
	tt_hwloc,
	tt_Cray,
	tt_Win
};
typedef enum node_topology_type ntt_t;

#define PBS_MIN_LICENSING_LICENSES  0
#define PBS_MAX_LICENSING_LICENSES  INT_MAX
#define PBS_LIC_LINGER_TIME 	31536000 /* keep extra licenses 1 year by default */
#define PBS_LICENSE_LOCATION				\
	 (pbs_licensing_license_location ?		\
	  pbs_licensing_license_location : "null" )

extern void log_licenses(struct license_used *pu);
extern int  checkin_licensing(void);
extern void close_licensing(void);
extern char *pbs_license_location(void);
extern void licstate_down(void);
extern int check_sign(void *, void *);
extern void process_topology_info(void *, char *, ntt_t );
extern void unset_signature(void *, char *);
extern int release_node_lic(void *);
extern void update_license_highuse();
extern int consume_licenses(int);
extern void release_licenses(int num);

extern void license_nodes();
/* Licensing-related variables */
extern char *pbs_licensing_license_location;
extern long pbs_min_licenses;
extern long pbs_max_licenses;
extern int  pbs_licensing_linger;
extern int  ping_license_server;	/* returns 0 if last manual  */
/* ping to license server is ok; otherwise, returns 1 for not ok. */
#ifdef	__cplusplus
}
#endif
#endif	/* _PBS_LICENSE_H */
