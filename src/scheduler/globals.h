/*
 * Copyright (C) 1994-2017 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
 * 
 * Use of Altair’s trademarks, including but not limited to "PBS™", 
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
 * trademark licensing policies.
 *
 */
#ifndef	_GLOBALS_H
#define	_GLOBALS_H
#ifdef	__cplusplus
extern "C" {
#endif

#include "data_types.h"

/* resources to check */
extern const struct rescheck res_to_check[];

/* information about sorting */
extern const struct sort_conv sort_convert[];

/* used to convert string into enum in parsing */
extern const struct enum_conv smp_cluster_info[];
extern const struct enum_conv prempt_prio_info[];

/* info to get from mom */
extern const char *res_to_get[];

/* programs to run to replaced specific resources_assigned values */
extern const char *res_assn[];

extern struct config conf;
extern struct status cstat;

extern const int num_resget;

/* Variables from pbs_sched code */
extern int pbs_rm_port;
extern int got_sigpipe;

/* static indexes into allres */
const struct enum_conv resind[RES_HIGH+1];

extern resdef **allres;
extern resdef **consres;
extern resdef **boolres;

/**
 * @brief
 * It is used as a placeholder to store aoe name. This aoe name will be
 * used by sorting routine to compare with vnode's current aoe.
 */
extern char *cmp_aoename;

#ifdef	__cplusplus
}
#endif
#endif	/* _GLOBALS_H */
