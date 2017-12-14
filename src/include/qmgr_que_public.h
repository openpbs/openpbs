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
#ifndef	_QMGR_QUE_PUBLIC_H
#define	_QMGR_QUE_PUBLIC_H
/*
 *	This is a list of public queue attributes
 *
 *	FORMAT:
 *		attr1,
 * 		attr2,	<--- important the last has a comma after it
 *
 * 	This file will be used for the initialization of an array
 *
 */

ATTR_aclgren,
ATTR_aclgroup,
ATTR_aclhten,
ATTR_aclhost,
ATTR_acluren,
ATTR_acluser,
ATTR_chkptmin,
ATTR_enable,
ATTR_fromroute,
ATTR_killdelay,
ATTR_maxarraysize,
ATTR_maxque,
ATTR_maxgrprun,
ATTR_maxrun,
ATTR_maxuserrun,
ATTR_maxuserres,
ATTR_maxgroupres,
ATTR_maxgrprunsoft,
ATTR_maxuserrunsoft,
ATTR_maxuserressoft,
ATTR_maxgroupressoft,
ATTR_NodeGroupKey,
ATTR_p,
ATTR_qtype,
ATTR_rescavail,
ATTR_rescdflt,
ATTR_rescmax,
ATTR_rescmin,
ATTR_rndzretry,
ATTR_routedest,
ATTR_altrouter,
ATTR_routeheld,
ATTR_routewait,
ATTR_routeretry,
ATTR_routelife,
ATTR_rsvexpdt,
ATTR_rsvsync,
ATTR_start,
ATTR_ReqCredEnable,
ATTR_ReqCred,
ATTR_DefaultChunk,
ATTR_max_run,
ATTR_max_run_soft,
ATTR_max_run_res,
ATTR_max_run_res_soft,
ATTR_max_queued,
ATTR_max_queued_res,
ATTR_queued_jobs_threshold,
ATTR_queued_jobs_threshold_res,
ATTR_backfill_depth,
ATTR_comment,
#ifdef NAS
/* localmod 046 */
ATTR_maxstarve,
/* localmod 034 */
ATTR_maxborrow,
#endif
#endif	/* _QMGR_QUE_PUBLIC_H */
