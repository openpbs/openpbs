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
#ifndef	_QMGR_SVR_PUBLIC_H
#define	_QMGR_SVR_PUBLIC_H

/*
 *	This is a list of public server attributes
 *
 *	FORMAT:
 *		attr1,
 * 		attr2,	<--- important the last has a comma after it
 *
 * 	This file will be used for the initialization of an array
 *
 */

ATTR_aclhten,
ATTR_aclhost,
ATTR_aclhostmomsen,
ATTR_acluren,
ATTR_acluser,
ATTR_aclroot,
ATTR_comment,
ATTR_defnode,
ATTR_dfltque,
ATTR_locsvrs,
ATTR_logevents,
ATTR_managers,
ATTR_mailfrom,
ATTR_maxrun,
ATTR_maxuserrun,
ATTR_maxgrprun,
ATTR_maxuserres,
ATTR_maxgroupres,
ATTR_maxgrprunsoft,
ATTR_maxuserrunsoft,
ATTR_maxuserressoft,
ATTR_maxgroupressoft,
ATTR_maxarraysize,
ATTR_nodepack,
ATTR_operators,
ATTR_PNames,
ATTR_queryother,
ATTR_rescavail,
ATTR_resccost,
ATTR_rescdflt,
ATTR_rescmax,
ATTR_schediteration,
ATTR_scheduling,
ATTR_syscost,
ATTR_FlatUID,
ATTR_aclResvgren,
ATTR_aclResvgroup,
ATTR_aclResvhten,
ATTR_aclResvhost,
ATTR_aclResvuren,
ATTR_aclResvuser,
ATTR_ResvEnable,
ATTR_nodefailrq,
ATTR_ReqCredEnable,
ATTR_ReqCred,
ATTR_NodeGroupEnable,
ATTR_NodeGroupKey,
ATTR_ssignon_enable,
ATTR_DefaultChunk,
ATTR_dfltqdelargs,
ATTR_dfltqsubargs,
ATTR_PNames,
ATTR_sandbox,
ATTR_rpp_retry,
ATTR_rpp_highwater,
ATTR_license_location,
ATTR_pbs_license_info,
ATTR_license_min,
ATTR_license_max,
ATTR_license_linger,
ATTR_license_count,
ATTR_job_sort_formula,
ATTR_EligibleTimeEnable,
ATTR_resv_retry_init,
ATTR_resv_retry_cutoff,
ATTR_JobHistoryEnable,
ATTR_JobHistoryDuration,
ATTR_max_run,
ATTR_max_run_soft,
ATTR_max_run_res,
ATTR_max_run_res_soft,
ATTR_max_queued,
ATTR_max_queued_res,
ATTR_queued_jobs_threshold,
ATTR_queued_jobs_threshold_res,
ATTR_max_concurrent_prov,
ATTR_resv_post_processing,
ATTR_backfill_depth,
ATTR_job_requeue_timeout,
ATTR_jobscript_max_size,
ATTR_python_restart_max_hooks,
ATTR_python_restart_max_objects,
ATTR_python_restart_min_interval,
ATTR_show_hidden_attribs,
ATTR_python_sync_mom_hookfiles_timeout,
ATTR_rpp_max_pkt_check,
ATTR_max_job_sequence_id,
#endif	/* _QMGR_SVR_PUBLIC_H */
