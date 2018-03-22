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
#ifndef	_PBS_LICENSE_H
#define	_PBS_LICENSE_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <limits.h>

struct license_block {
	int  lb_trial;		/* non_zero if trial license */
	int  lb_glob_floating;	/* number of floating licenses avail globally */
	int  lb_aval_floating;	/* number of floating licenses avail locally  */
	int  lb_used_floating;	/* number of floating licenses used           */
	int  lb_high_used_floating; /*  highest number of floating licenses used at any given time */
	int  lb_do_task;	/* set to 1 if doing return_licenses() tasks  */
};

struct license_used {
	int  lu_max_hr;		/* max number of floating used in the hour  */
	int  lu_max_day;	/* max number of floating used in the day   */
	int  lu_max_month;	/* max number of floating used in the month */
	int  lu_max_forever;	/* running max number for ever 		    */
	int  lu_day;		/* which day of month recording		    */
	int  lu_month;		/* which month recording		    */
};

enum  fl_feature_type {
	FL_FEATURE_float,
	FL_FEATURE_LAST		/* must be last one, used to define array sz */
};

#define  PBS_MIN_LICENSING_LICENSES  0
#define  PBS_MAX_LICENSING_LICENSES  INT_MAX
#define  PBS_LIC_LINGER_TIME 	31536000 /* keep extra licenses 1 year by default */
#define  PBS_LICENSE_LOCATION				\
	(pbs_conf.pbs_license_file_location ?		\
	 pbs_conf.pbs_license_file_location :		\
	 (pbs_licensing_license_location ?		\
	  pbs_licensing_license_location : "null" ))

enum licensing_backend {
	LIC_SERVER,	/* reachable license server (to license CPUs) */
	LIC_SOCKETS,	/* nonzero number of sockets (to license nodes) */
	LIC_NODES,	/* nonzero number of nodes (to license nodes) */
	LIC_TRIAL,	/* nonzero number of trial license (to license CPUs) */
	LIC_UNKNOWN  /* used to hold the value of previous lb */
};

extern struct license_block licenses;
extern struct attribute *pbs_float_lic;
extern void   init_fl_license_attrs(struct license_block *);
extern int    check_license(struct license_block *);
extern void   log_licenses(struct license_used *pu);
extern void   init_licensing(void);
extern int    status_licensing(void);
extern int    checkin_licensing(void);
extern void   close_licensing(void);
extern int    pbs_get_licenses(int);
extern int    count_needed_flic(int);
extern void   relicense_nodes_floating(int);
extern void   update_FLic_attr(void);
extern char   *pbs_license_location(void);
extern void   init_socket_licenses(char *);
extern int    sockets_available(void);
extern int    sockets_total(void);
extern int    sockets_consume(int);
extern void   sockets_release(int);
extern void   sockets_reset(void);
extern void   inspect_license_path(void);
extern int    licstate_is_up(enum licensing_backend);
extern void   licstate_down(void);
extern void   licstate_unconfigured(enum licensing_backend);

/* Licensing-related variables */
extern int    ext_license_server;
extern char   *pbs_licensing_license_location;
extern long   pbs_min_licenses;
extern long   pbs_max_licenses;
extern int    pbs_licensing_linger;
extern int    ping_license_server;	/* returns 0 if last manual  */
/* ping to license server is ok; otherwise, returns 1 for not ok. */
extern enum   licensing_backend prev_lb;
extern enum   licensing_backend last_valid_attempt;
#ifdef	__cplusplus
}
#endif
#endif	/* _PBS_LICENSE_H */
