/*
 * Copyright (C) 1994-2016 Altair Engineering, Inc.
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

/**
 * @file    sort.c
 *
 * @brief
 * 		sort.c - This file will hold the compare functions used by qsort
 *		to sort the jobs
 *
 * Functions included are:
 * 	cmpres()
 * 	cmp_placement_sets()
 * 	cmp_nspec()
 * 	cmp_low_load()
 * 	cmp_sch_prio_dsc()
 * 	cmp_node_prio_dsc()
 * 	cmp_queue_prio_dsc()
 * 	cmp_queue_prio_asc()
 * 	cmp_time_left()
 * 	cmp_events()
 * 	cmp_job_walltime_asc()
 * 	cmp_job_walltime_dsc()
 * 	cmp_job_cput_asc()
 * 	cmp_job_cput_dsc()
 * 	cmp_job_mem_asc()
 * 	cmp_job_mem_dsc()
 * 	cmp_fairshare()
 * 	cmp_preempt_priority_dsc()
 * 	cmp_preempt_priority_asc()
 * 	cmp_preempt_stime_asc()
 * 	cmp_preemption()
 * 	multi_sort()
 * 	cmp_job_sort_formula()
 * 	multi_node_sort()
 * 	multi_nodepart_sort()
 * 	resresv_sort_cmp()
 * 	node_sort_cmp()
 * 	cmp_sort()
 * 	find_nodepart_amount()
 * 	find_node_amount()
 * 	find_resresv_amount()
 * 	cmp_node_host()
 * 	cmp_aoe()
 * 	cmp_job_preemption_time_asc()
 * 	cmp_starving_jobs()
 * 	sort_jobs()
 * 	swapfunc()
 * 	med3()
 * 	qsort()
 *
 */
#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <log.h>
#include "data_types.h"
#include "sort.h"
#include "resource_resv.h"
#include "misc.h"
#include "globals.h"
#include "fairshare.h"
#include "fifo.h"
#include "node_info.h"
#include "check.h"
#include "constant.h"
#include "server_info.h"
#include "resource.h"
#include "constant.h"

#ifdef NAS
#include "site_code.h"
#endif



/**
 * @brief
 *		compare two new numerical resource numbers for a descending sort
 *
 * @param[in]	r1	-	resource 1
 * @param[in]	r2	-	resource 2
 *
 * @return	int
 * @retval	-1	: if r1 < r2
 * @retval	0 	: if r1 == r2
 * @retval	1  	: if r1 > r2
 */
int
cmpres(sch_resource_t r1, sch_resource_t r2)
{
	if (r1 == SCHD_INFINITY && r2 == SCHD_INFINITY)
		return 0;
	if (r1 == SCHD_INFINITY)
		return -1;
	if (r2 == SCHD_INFINITY)
		return 1;
	if (r1 < r2)
		return -1;
	if (r1 == r2)
		return 0;

	return 1;
}

/**
 * @brief
 *		cmp_placement_sets - sort placement sets by
 *			total cpus
 *			total memory
 *			free cpus
 *			free memory
 *
 * @param[in]	v1	-	node partition 1
 * @param[in]	v2	-	node partition 2
 *
 * @return	int
 * @retval	-1	: if v1 < v2
 * @retval	0 	: if v1 == v2
 * @retval	1  	: if v1 > v2
 */
int
cmp_placement_sets(const void *v1, const void *v2)
{
	node_partition *np1, *np2;
	resource *ncpus1, *ncpus2;
	resource *mem1, *mem2;
	int rc = 0;


	if (v1 == NULL && v2 == NULL)
		return 0;

	if (v1 == NULL && v2 != NULL)
		return -1;

	if (v1 != NULL && v2 == NULL)
		return 1;

	np1 = *((node_partition **) v1);
	np2 = *((node_partition **) v2);

	ncpus1 = find_resource(np1->res, getallres(RES_NCPUS));
	ncpus2 = find_resource(np2->res, getallres(RES_NCPUS));

	if (ncpus1 != NULL && ncpus2 != NULL)
		rc = cmpres(ncpus1->avail, ncpus2->avail);

	if (!rc) {
		mem1 = find_resource(np1->res, getallres(RES_MEM));
		mem2 = find_resource(np2->res, getallres(RES_MEM));

		if (mem1 != NULL && mem2 != NULL)
			rc = cmpres(mem1->avail, mem2->avail);
	}

	if (!rc) {
		if (ncpus1 != NULL && ncpus2 != NULL)
			rc = cmpres(dynamic_avail(ncpus1), dynamic_avail(ncpus2));
	}


	if (!rc) {
		if (mem1 != NULL && mem2 != NULL)
			rc = cmpres(dynamic_avail(mem1), dynamic_avail(mem2));
	}

	return rc;

}

/**
 * @brief
 * 		cmp_nspec - sort nspec by sequence number
 *
 * @param[in]	v1	-	nspec 1
 * @param[in]	v2	-	nspec 2
 *
 * @return	int
 * @retval	-1	: if v1 < v2
 * @retval	0 	: if v1 == v2
 * @retval	1  	: if v1 > v2
 */
int
cmp_nspec(const void *v1, const void *v2)
{
	int s1, s2, ss1, ss2;
	if (v1 == NULL && v2 == NULL)
		return 0;

	if (v1 == NULL && v2 != NULL)
		return -1;

	if (v1 != NULL && v2 == NULL)
		return 1;

	s1 = (*(nspec**) v1)->seq_num;
	s2 = (*(nspec**) v2)->seq_num;
	ss1 = (*(nspec**) v1)->sub_seq_num;
	ss2 = (*(nspec**) v2)->sub_seq_num;

	if (s1 < s2)
		return -1;
	else if (s1 > s2)
		return 1;
	else {
		if (ss1 < ss2)
			return -1;
		else if (ss1 > ss2)
			return 1;
		else
			return 0;
	}
}



/**
 * @brief
 *		cmp_low_load - sort nodes ascending by load ave
 *
 * @param[in]	v1	-	node info 1
 * @param[in]	v2	-	node info 2
 *
 * @return	int
 * @retval	-1	: if v1 < v2
 * @retval	0 	: if v1 == v2
 * @retval	1  	: if v1 > v2
 */
int
cmp_low_load(const void *v1, const void *v2)
{
	if (v1 == NULL && v2 == NULL)
		return 0;

	if (v1 == NULL && v2 != NULL)
		return -1;

	if (v1 != NULL && v2 == NULL)
		return 1;

	if ((*(node_info **) v1)->loadave < (*(node_info **) v2)->loadave)
		return -1;
	else if ((*(node_info **) v1)->loadave > (*(node_info **) v2)->loadave)
		return 1;
	else
		return 0;
}

/**
 * @brief
 *		cmp_sch_prio_dsc - sort jobs decending by sch_priority
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	-1  : if j1 > j2
 */
int
cmp_sch_prio_dsc(const void *j1, const void *j2)
{
	if ((*(resource_resv **) j1)->sch_priority < (*(resource_resv **) j2)->sch_priority)
		return 1;
	else if ((*(resource_resv **) j1)->sch_priority > (*(resource_resv **) j2)->sch_priority)
		return -1;
	else
		return 0;
}

/**
 * @brief
 *		cmp_node_prio_dsc - sort nodes in decending priority
 *
 * @param[in]	n1	-	node_info 1
 * @param[in]	n2	-	node_info 2
 *
 * @return	int
 * @retval	1	: if n1 < n2
 * @retval	0 	: if n1 == n2
 * @retval	-1  : if n1 > n2
 */
int
cmp_node_prio_dsc(const void *n1, const void *n2)
{
	if ((*(node_info **) n1)->priority < (*(node_info **) n2)->priority)
		return 1;
	else if ((*(node_info **) n1)->priority > (*(node_info **) n2)->priority)
		return -1;
	else
		return 0;
}


/**
 * @brief
 *      cmp_queue_prio_dsc - sort queues in decending priority
 *
 * @param[in]	q1	-	queue_info 1
 * @param[in]	q2	-	queue_info 2
 *
 * @return	int
 * @retval	1	: if q1 < q2
 * @retval	0 	: if q1 == q2
 * @retval	-1  : if q1 > q2
 */
int
cmp_queue_prio_dsc(const void *q1, const void *q2)
{
	if ((*(queue_info **) q1)->priority < (*(queue_info **) q2)->priority)
		return 1;
	else if ((*(queue_info **) q1)->priority > (*(queue_info **) q2)->priority)
		return -1;
	else
		return 0;
}

/**
 * @brief
 * 		cmp_queue_prio_asc - sort queues by ascending priority
 *
 * @param[in]	q1	-	queue_info 1
 * @param[in]	q2	-	queue_info 2
 *
 * @return	int
 * @retval	-1	: if q1 < q2
 * @retval	0 	: if q1 == q2
 * @retval	1  : if q1 > q2
 */
int
cmp_queue_prio_asc(const void *q1, const void *q2)
{
	if ((*(queue_info **) q1)->priority < (*(queue_info **) q2)->priority)
		return -1;
	else if ((*(queue_info **) q1)->priority > (*(queue_info **) q2)->priority)
		return 1;
	else
		return -1;
}

/**
 * @brief
 *      cmp_time_left - sort jobs by time remaining to run - descending
 *		 sort any job w/o walltime to the end
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	-1  : if j1 > j2
 */
int
cmp_time_left(const void *j1, const void *j2)
{
	int t1, t2;

	t1 = calc_time_left((*(resource_resv**) j1));
	t2 = calc_time_left((*(resource_resv**) j2));

	if (t1 >= 0 && t2 < 0)
		return -1;

	if (t2 >= 0 && t1 < 0)
		return 1;

	if (t1 < t2)
		return 1;
	if (t1 == t2)
		return 0;
	else
		return -1;
}


/**
 * @brief
 *		cmp_events - sort jobs/resvs into a timeline of the next even to
 *		happen: running jobs ending, advanced reservations starting
 *		or ending
 *
 * @param[in]	v1	-	resource_resv 1
 * @param[in]	v2	-	resource_resv 2
 *
 * @return	int
 * @retval	-1	: if v1 < v2
 * @retval	0 	: if v1 == v2
 * @retval	1  	: if v1 > v2
 */
int
cmp_events(const void *v1, const void *v2)
{
	resource_resv *r1, *r2;
	time_t t1, t2;
	int run1, run2;			/* are r1 and r2 in runnable states? */
	int end_event1 = 0, end_event2 = 0;	/* are r1 and r2 end events? */

	r1 = *((resource_resv **) v1);
	r2 = *((resource_resv **) v2);

	if (r1->start != UNSPECIFIED && r2->start ==UNSPECIFIED)
		return -1;

	if (r1->start == UNSPECIFIED && r2->start ==UNSPECIFIED)
		return 0;

	if (r1->start == UNSPECIFIED && r2->start !=UNSPECIFIED)
		return 1;

	run1 = in_runnable_state(r1);
	run2 = in_runnable_state(r2);


	if (r1->start >= r1->server->server_time && run1)
		t1 = r1->start;
	else {
		end_event1 = 1;
		t1 = r1->end;
	}

	if (r2->start >= r2->server->server_time && run2)
		t2 = r2->start;
	else {
		end_event2 = 1;
		t2 = r2->end;
	}

	if (t1 < t2)
		return -1;
	else if (t1 == t2) {
		/* if event times are equal, this means that events which consume
		 * resources and release resources happen at the same time.  We need to
		 * make sure events which release resources come first, so the events
		 * which consume them, can indeed do that.
		 */
		if (end_event1)
			return -1;
		else if (end_event2)
			return 1;
		else
			return 0;
	}
	else
		return 1;
}


/**
 * @brief
 *      cmp_job_walltime_asc - sort jobs by requested walltime
 *		in ascending order.
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	-1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	1  : if j1 > j2
 */
int
cmp_job_walltime_asc(const void *j1, const void *j2)
{
	resource_req *req1, *req2;

	req1 = find_resource_req((*(resource_resv**) j1)->resreq, getallres(RES_WALLTIME));
	req2 = find_resource_req((*(resource_resv**) j2)->resreq, getallres(RES_WALLTIME));

	if (req1 != NULL && req2 != NULL) {
		if (req1->amount < req2->amount)
			return -1;
		else if (req1->amount == req2->amount)
			return 0;
		else
			return 1;
	}
	else
		return 0;
}

/**
 * @brief
 *      cmp_job_walltime_dsc - sort jobs by requested walltime
 *		in ascending order.
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	-1  : if j1 > j2
 */
int
cmp_job_walltime_dsc(const void *j1, const void *j2)
{
	resource_req *req1, *req2;

	req1 = find_resource_req((*(resource_resv**) j1)->resreq, getallres(RES_WALLTIME));
	req2 = find_resource_req((*(resource_resv**) j2)->resreq, getallres(RES_WALLTIME));

	if (req1 != NULL && req2 != NULL) {
		if (req1->amount < req2->amount)
			return 1;
		else if (req1->amount == req2->amount)
			return 0;
		else
			return -1;
	}
	else
		return 0;
}

/**
 * @brief
 *      cmp_job_cput_asc - sort jobs by requested cput time in ascending order.
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	-1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	1  : if j1 > j2
 */
int
cmp_job_cput_asc(const void *j1, const void *j2)
{
	resource_req *req1, *req2;

	req1 = find_resource_req((*(resource_resv**) j1)->resreq, getallres(RES_CPUT));
	req2 = find_resource_req((*(resource_resv**) j2)->resreq, getallres(RES_CPUT));

	if (req1 != NULL && req2 != NULL) {
		if (req1->amount < req2->amount)
			return -1;
		else if (req1->amount == req2->amount)
			return 0;
		else
			return 1;
	}
	else
		return 0;
}

/**
 * @brief
 *      cmp_job_cput_dsc - sort jobs by requested cput time in descending order.
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	-1  : if j1 > j2
 */
int
cmp_job_cput_dsc(const void *j1, const void *j2)
{
	resource_req *req1, *req2;

	req1 = find_resource_req((*(resource_resv**) j1)->resreq, getallres(RES_CPUT));
	req2 = find_resource_req((*(resource_resv**) j2)->resreq, getallres(RES_CPUT));

	if (req1 != NULL && req2 != NULL) {
		if (req1->amount < req2->amount)
			return 1;
		else if (req1->amount == req2->amount)
			return 0;
		else
			return -1;
	}
	else
		return 0;
}

/**
 * @brief
 *      cmp_job_mem_asc - sort jobs by requested mem time in ascending order.
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	-1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	1  	: if j1 > j2
 */
int
cmp_job_mem_asc(const void *j1, const void *j2)
{
	resource_req *req1, *req2;

	req1 = find_resource_req((*(resource_resv**) j1)->resreq, getallres(RES_MEM));
	req2 = find_resource_req((*(resource_resv**) j2)->resreq, getallres(RES_MEM));

	if (req1 != NULL && req2 != NULL) {
		if (req1->amount < req2->amount)
			return -1;
		else if (req1->amount == req2->amount)
			return 0;
		else
			return 1;
	}
	else
		return 0;
}

/**
 * @brief
 *      cmp_job_mem_dsc - sort jobs by requested mem time in descending order.
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	-1  	: if j1 > j2
 */
int
cmp_job_mem_dsc(const void *j1, const void *j2)
{
	resource_req *req1, *req2;

	req1 = find_resource_req((*(resource_resv**) j1)->resreq, getallres(RES_MEM));
	req2 = find_resource_req((*(resource_resv**) j2)->resreq, getallres(RES_MEM));

	if (req1 != NULL && req2 != NULL) {
		if (req1->amount < req2->amount)
			return 1;
		else if (req1->amount == req2->amount)
			return 0;
		else
			return -1;
	}
	else
		return 0;
}

/**
 * @brief
 *		cmp_fair_share - compare on fair share percentage only.
 *			 This is for strict priority.
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	-1  : if j1 > j2
 */
int
cmp_fairshare(const void *j1, const void *j2)
{
	resource_resv *r1 = *(resource_resv**)j1;
	resource_resv *r2 = *(resource_resv**)j2;
	if (r1->job != NULL && r1->job->ginfo != NULL &&
		r2->job != NULL && r2->job->ginfo != NULL)
		return compare_path(r1->job->ginfo->gpath , r2->job->ginfo->gpath);

	return 0;
}

/**
 * @brief
 *		cmp_preempt_priority_dsc - used to sort high priority preempting jobs
 *				by descending preemption priority first.
 *				followed by the normal job_sort_key sort
 *				The final sort is to stabilize qsort() by
 *				sorting on the order we query the jobs from
 *				the server.
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	-1  : if j1 > j2
 */
int
cmp_preempt_priority_dsc(const void *j1, const void *j2)
{
	int cmp;
	resource_resv *r1;
	resource_resv *r2;

	r1 = (*(resource_resv **) j1);
	r2 = (*(resource_resv **) j2);

	if (r1->job->preempt < r2->job->preempt)
		return 1;
	else if (r1->job->preempt > r2->job->preempt)
		return -1;
	else {
		cmp = cmp_job_sort_formula(&r1, &r2);
		if (cmp != 0)
			return cmp;

		cmp = multi_sort(r1, r2);
		if (cmp == 0) {
			if (r1->rank < r2->rank)
				return -1;
			else if (r1->rank > r2->rank)
				return 1;
		}
	}

	return 0;
}

/**
 * @brief
 *		cmp_preempt_priority_asc - used to sort jobs in ascending preemption
 *				   priority
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	-1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	1  : if j1 > j2
 */
int
cmp_preempt_priority_asc(const void *j1, const void *j2)
{
	if ((*(resource_resv **) j1)->job->preempt < (*(resource_resv **) j2)->job->preempt)
		return -1;
	else if ((*(resource_resv **) j1)->job->preempt > (*(resource_resv **) j2)->job->preempt)
		return 1;
	else {
		if ((*(resource_resv **) j1)->rank < (*(resource_resv **) j2)->rank)
			return -1;
		else if ((*(resource_resv **) j1)->rank > (*(resource_resv **) j2)->rank)
			return 1;
	}

	return 0;
}

/**
 * @brief
 *      cmp_preempt_stime_asc - used to soft jobs in ascending preemption
 *                              priority and start time
 *
 * @param[in]	j1	-	resource_resv 1
 * @param[in]	j2	-	resource_resv 2
 *
 * @return	int
 * @retval	-1	: if j1 < j2
 * @retval	0 	: if j1 == j2
 * @retval	1   : if j1 > j2
 */
int
cmp_preempt_stime_asc(const void *j1, const void *j2)
{
	if ((*(resource_resv **) j1)->job->preempt < (*(resource_resv **) j2)->job->preempt)
		return -1;
	else if ((*(resource_resv **) j1)->job->preempt > (*(resource_resv **) j2)->job->preempt)
		return 1;
	else {
		/* sort by start time */
		if ((*(resource_resv **) j1)->job->stime > (*(resource_resv **) j2)->job->stime)
			return -1;
		if ((*(resource_resv **) j1)->job->stime < (*(resource_resv **) j2)->job->stime)
			return 1;
	}

	return 0;
}

/**
 * @brief
 *  	cmp_premeption  - compare first by preemption priority and then
 *                   		if the job had been preempted, the order preempted.
 *
 * @param[in]	r1	-	resource_resv 1
 * @param[in]	r2	-	resource_resv 2
 *
 * @return	int
 * @retval	1	: if r1 < r2
 * @retval	0 	: if r1 == r2
 * @retval	-1  : if r1 > r2
 */
int
cmp_preemption(resource_resv *r1, resource_resv *r2)
{
	if (r1 != NULL && r2 == NULL)
		return -1;

	if (r1 == NULL && r2 == NULL)
		return 0;

	if (r1 == NULL && r2 != NULL)
		return 1;

	/* error, allow some other sort key to take over */
	if (r1->job == NULL || r2->job ==NULL)
		return 0;

	if (r1->job->preempt < r2->job->preempt)
		return 1;
	else if (r1->job->preempt > r2->job->preempt)
		return -1;

	return 0;
}

/* multi keyed sorting
 * call compare function to sort for the first key
 * if the two keys are equal, call the compare funciton for the second key
 * repeat for all keys
 */


/**
 * @brief
 * 		multi_sort - a multi keyed sorting compare function for jobs
 *
 * @param[in] r1 - job to compare
 * @param[in] r2 - job to compare
 *
 * @return int
 * @retval -1, 0, 1 : standard qsort() cmp
 */
int
multi_sort(resource_resv *r1, resource_resv *r2)
{
	int ret = 0;
	int i;

	for (i = 0; i <= MAX_SORTS && ret == 0 && cstat.sort_by[i].res_name != NULL; i++)
		ret = resresv_sort_cmp(r1, r2, &cstat.sort_by[i]);

	return ret;
}

/**
 * @brief
 * 		cmp_job_sort_formula - used to sort jobs based on their evaluated
 *				      job_sort_formula value (in DESC order)
 * @param[in] r1 - job to compare
 * @param[in] r2 - job to compare
 *
 * @return int
 * @retval -1, 0, 1 : standard qsort() cmp
 */
int
cmp_job_sort_formula(const void *j1, const void *j2)
{
	resource_resv *r1 = *(resource_resv**)j1;
	resource_resv *r2 = *(resource_resv**)j2;

	if (r1->job->formula_value < r2->job->formula_value)
	    return 1;
	if (r1->job->formula_value > r2->job->formula_value)
	    return -1;
	return 0;
}

/**
 * @brief
 *		multi_node_sort - a multi keyed sorting compare function for nodes
 *
 * @param[in] vp1 - the node/parts to compare
 * @param[in] vp2 - the node/parts to compare
 *
 * @return int
 *	@retval -1, 0, 1 - standard qsort() cmp
 */
int
multi_node_sort(const void *n1, const void *n2)
{
	int ret = 0;
	int i;

	for (i = 0; i <= MAX_SORTS && ret == 0 && cstat.node_sort[i].res_name != NULL; i++)
		ret = node_sort_cmp(n1, n2, &cstat.node_sort[i], SOBJ_NODE);

	return ret;
}


/**
 * @brief
 * 		qsort() compare function for multi-resource node partition sorting
 *
 * @param[in] n1 - the node/parts to compare
 * @param[in] n2 - the node/parts to compare
 *
 * @return int
 *	@retval -1, 0, 1 - standard qsort() cmp
 */
int
multi_nodepart_sort(const void *n1, const void *n2)
{
	int ret = 0;
	int i;

	for (i = 0; i <= MAX_SORTS && ret == 0 && cstat.node_sort[i].res_name != NULL; i++)
		ret = node_sort_cmp(n1, n2, &cstat.node_sort[i], SOBJ_PARTITION);
	return ret;
}

/**
 * @brief
 * 		compares two jobs using a sort defined by a sort_info
 *		This is used downstream by qsort()
 *
 * @param[in] r1	-	first job to compare
 * @param[in] r2 	-	second job to compare
 * @param[in] si 	- 	sort_info describing how to sort the jobs
 * 
 * @returns -1, 0, 1 : standard qsort()) cmp
 *
 */
int
resresv_sort_cmp(resource_resv *r1, resource_resv *r2, struct sort_info *si)
{
	sch_resource_t v1, v2;

	if (r1 != NULL && r2 == NULL)
		return -1;

	if (r1 == NULL && r2 == NULL)
		return 0;

	if (r1 == NULL && r2 != NULL)
		return 1;
	
	if(si == NULL)
		return 0;
	
	v1 = find_resresv_amount(r1, si->res_name, si->def);
	v2 = find_resresv_amount(r2, si->res_name, si->def);

	if (v1 == v2)
		return 0;

	if (si->order == ASC) {
		if (v1 < v2)
			return -1;
		else
			return 1;
	}
	else {
		if (v1 < v2)
			return 1;
		else
			return -1;
	}
}

/**
 * @brief
 * 		compares either two nodes or node_partitions based on a resource,
 *              Ascending/Descending, and what part of the resource to use (total, unused, etc)
 *
 * @param[in] vp1 		- the node/parts to compare
 * @param[in] vp2 		- the node/parts to compare
 * @param[in] si 		- sort info describing how to sort nodes
 * @param[in] obj_type 	- node or node_partition
 *
 * @return int
 * @retval -1, 0, 1 : standard qsort() cmp
 */
int
node_sort_cmp(const void *vp1, const void *vp2, struct sort_info *si, enum sort_obj_type obj_type)
{
	sch_resource_t v1, v2;
	node_info **n1 = NULL;
	node_info **n2 = NULL;
	node_partition **np1 = NULL;
	node_partition **np2 = NULL;
	int rank1, rank2;

	if (vp1 != NULL && vp2 == NULL)
		return -1;

	if (vp1 == NULL && vp2 == NULL)
		return 0;

	if (vp1 == NULL && vp2 != NULL)
		return 1;

	if (si == NULL)
		return 0;

	switch(obj_type)
	{
		case SOBJ_NODE:
			n1 = (node_info **) vp1;
			n2 = (node_info **) vp2;
			v1 = find_node_amount(*n1, si->res_name, si->def, si->res_type);
			v2 = find_node_amount(*n2, si->res_name, si->def, si->res_type);
			rank1 = (*n1)->rank;
			rank2 = (*n2)->rank;
			break;
		case SOBJ_PARTITION:
			np1 = (node_partition **) vp1;
			np2 = (node_partition **) vp2;
			v1 = find_nodepart_amount(*np1, si->res_name, si->def, si->res_type);
			v2 = find_nodepart_amount(*np2, si->res_name, si->def, si->res_type);
			rank1 = (*np1)->rank;
			rank2 = (*np2)->rank;
			break;
		default:
			return 0;
			break;
	}

	if (v1 == v2)
		return 0;

	if (si->order == ASC) {
		if (v1 < v2)
			return -1;
		else if (v1 > v2)
			return 1;
		else {
			if (rank1 < rank2)
				return -1;
			else
				return 1;
		}
	} else {
		if (v1 < v2)
			return 1;
		else if (v1 > v2)
			return -1;
		else {
			if (rank1 < rank2)
				return 1;
			else
				return -1;
		}
	}
}

/**
 * @brief
 * 		entrypoint into job sort used by qsort
 *		
 *		1. Sort all preemption priority jobs in the front
 *		2. Sort all preempted jobs in ascending order of their preemption time
 *		3. Sort all starving jobs after the high priority jobs
 *		4. Sort jobs according to their fairshare usage.
 *		5. sort by unique rank to stabilize the sort
 *
 * @param[in]	v1	-	resource_resv 1
 * @param[in]	v2	-	resource_resv 2
 *
 * @return	-1,0,1 : based on sorting function.
 */
int
cmp_sort(const void *v1, const void *v2)
{
	int cmp;
	resource_resv *r1;
	resource_resv *r2;

	r1 = *((resource_resv **) v1);
	r2 = *((resource_resv **) v2);

	if (r1 != NULL && r2 == NULL)
		return -1;

	if (r1 == NULL && r2 == NULL)
		return 0;

	if (r1 == NULL && r2 != NULL)
		return 1;

	if (in_runnable_state(r1) && !in_runnable_state(r2))
		return -1;
	else if (in_runnable_state(r2) && !in_runnable_state(r1))
		return 1;
	/* both jobs are runnable */
	else {
		/* sort based on preemption */
		cmp = cmp_preemption(r1, r2);
		if (cmp != 0)
			return cmp;

		cmp = cmp_job_preemption_time_asc(&r1, &r2);
		if (cmp != 0)
			return cmp;

		if (r1->is_job && r1->server->policy->help_starving_jobs) {
			cmp = cmp_starving_jobs(&r1, &r2);
			if (cmp != 0)
				return cmp;
		}

		/* sort on the basis of job sort formula */
		cmp = cmp_job_sort_formula(&r1, &r2);
		if (cmp != 0)
			return cmp;

		if (r1->server->policy->fair_share) {
			cmp = cmp_fairshare(&r1, &r2);
			if (cmp != 0)
				return cmp;
		}

		/* normal resource based sort */
		cmp = multi_sort(r1, r2);
		if (cmp != 0)
			return cmp;

		/* stabilize the sort */
		else {
			if (r1->qtime < r2->qtime)
				return -1;
			else if (r1->qtime > r2->qtime)
				return 1;
			else if ((r1->job != NULL) && (r2->job != NULL)) {
				if (r1->job->job_id < r2->job->job_id)
					return -1;
				else if (r1->job->job_id > r2->job->job_id)
					return 1;
			else
				return 0;
		}
			else {
				return 0;
			}
		}
	}
}
/**
 * @brief
 * 		return resource values based on res_type for node partition
 * 
 * @param[in] np 		- node partition
 * @param[in] res 		- resource name
 * @param[in] def 		- resource definition of res
 * @param[in] res_type 	- type of resource value to use
 *
 * @note
 * 		special case sorting "resource" SORT_PRIORITY is not meaningful for
 *       node partitions.  0 will always be returned
 *
 * @return	sch_resource_t
 */
sch_resource_t
find_nodepart_amount(node_partition *np, char *res, resdef *def,
	enum resource_fields res_type) 
{
	resource *nres;

	if (def != NULL)
		nres = find_resource(np->res, def);
	else
		nres = find_resource_by_str(np->res, res);

	if (nres != NULL) {
		if (res_type == RF_AVAIL)
			return nres->avail;
		else if (res_type == RF_ASSN)
			return nres->assigned;
		else if (res_type == RF_UNUSED)
			return nres->avail - nres->assigned;
		else/* error */
			return 0;
	}


	return 0;
}

/**
 * @brief
 * 		return resource values based on res_type for a node
 *
 * @param[in] ninfo 	- node
 * @param[in] res 		- resource name or special case
 * @param[in] def 		- resource definition of res
 * @param[in] res_type 	- type of resource value to use
 *  *
 * @return sch_resource_t
 * @retval	0	: error
 */
sch_resource_t
find_node_amount(node_info *ninfo, char *res, resdef *def,
	enum resource_fields res_type)
{
	/* def is NULL on special case sort keys */
	if(def != NULL) {
		resource*nres;
		nres = find_resource(ninfo->res, def);

		if (nres != NULL) {
			if(nres -> indirect_res != NULL)
				nres = nres -> indirect_res;
			if (res_type == RF_AVAIL)
				return nres->avail;
			else if (res_type == RF_ASSN)
				return nres->assigned;
			else if (res_type == RF_UNUSED)
				return nres->avail - nres->assigned;
			else /* error */
				return 0;
		}

	} else if (!strcmp(res, SORT_PRIORITY))
		return ninfo->priority;

	return 0;
}

/**
 * @brief
 * 		find resource or special case sorting values for jobs
 * 
 * @param[in] resresv 	- the job
 * @param[in] res 		- the resource/special case name
 * @param[in] def 		- the resource definition of res (NULL for special case)
 * 
 * @return	sch_resource_t
 * @retval	0	: on error
 */
sch_resource_t
find_resresv_amount(resource_resv *resresv, char *res, resdef *def)
{
	/* def is NULL on special case sort keys */
	if( def != NULL) {
		resource_req *req;

		req = find_resource_req(resresv->resreq, def);

		if (req != NULL)
			return req->amount;
	}

	if (!strcmp(res, SORT_JOB_PRIORITY))
#ifdef NAS /* localmod 045 */
		return(sch_resource_t) resresv->job->NAS_pri;
#else
		return(sch_resource_t) resresv->job->priority;
#endif /* localmod 045 */		
	else if (!strcmp(res, SORT_FAIR_SHARE) && resresv->job->ginfo != NULL)
		return(sch_resource_t) resresv->job->ginfo->percentage;
	else if (!strcmp(res, SORT_PREEMPT))
		return(sch_resource_t) resresv->job->preempt;
#ifdef NAS
		/* localmod 034 */
	else if (!strcmp(res, SORT_ALLOC))
		return(sch_resource_t) (100.0 * site_get_share(resresv));
		/* localmod 039 */
	else if (!strcmp(res, SORT_QPRI) && resresv->job->queue != NULL)
		return(sch_resource_t) resresv->job->queue->priority;
		/* localmod 040 */
	else if (!strcmp(res, SORT_NODECT)) {
		/* return the node count - dpr */
		int ndct = resresv->job->nodect;
		return(sch_resource_t) ndct;
	}
#endif
	return 0;
}

/**
 * @brief
 * 	 	sort nodes by resources_available.host
 *
 * @param[in]	v1	-	node_info 1
 * @param[in]	v2	-	node_info 2
 *
 * @return int
 * @retval -1, 0, 1 - standard qsort() cmp
*/
int
cmp_node_host(const void *v1, const void *v2)
{
	resource *res1;
	resource *res2;
	node_info **n1;
	node_info **n2;
	int rc = 0;

	n1 = (node_info **) v1;
	n2 = (node_info **) v2;

	res1 = find_resource((*n1)->res, getallres(RES_HOST));
	res2 = find_resource((*n2)->res, getallres(RES_HOST));

	if (res1 != NULL && res2 != NULL)
		rc = strcmp(res1->orig_str_avail, res2->orig_str_avail);

	/* if the host is the same and we have a node_sort_key, preserve the sort */
	if (rc == 0 && cstat.node_sort[0].res_name != NULL)
		return multi_node_sort(v1, v2);

	return rc;
}

/**
 * @brief
 *		Sorting function used with 'avoid_provision' policy
 *
 * @par Functionality:
 *		This function compares two nodes and determines the order by comparing
 *		the AOE instantiated on them with AOE requested by job (or reservation).
 *		If order cannot be determined then node_sort_key is used.
 *
 * @param[in]	v1		-	pointer to const void
 * @param[in]	v2		-	pointer to const void
 *
 * @return	int
 * @retval	 -1 : v1 has precendence
 * @retval	  0 : v1 and v2 both have equal precedence
 * @retval	  1 : v2 has precendence
 *
 * @par Side Effects:
 *		Unknown
 *
 * @par MT-safe: No
 *
 */
int
cmp_aoe(const void *v1, const void *v2)
{
	node_info **n1;
	node_info **n2;
	int v1rank = 0, v2rank = 0; /* to reduce strcmp() calls */
	int ret;

	n1 = (node_info **) v1;
	n2 = (node_info **) v2;

	/* Between nodes, one with aoe and other without aoe, one with aoe
	 * comes first.
	 */

	if ((*n1)->current_aoe) {
		if (strcmp((*n1)->current_aoe, cmp_aoename) == 0)
			v1rank = 1;
		else
			v1rank = -1;
	}

	if ((*n2)->current_aoe) {
		if (strcmp((*n2)->current_aoe, cmp_aoename) == 0)
			v2rank = 1;
		else
			v2rank = -1;
	}

	ret = v2rank - v1rank;

	if (ret == 0)
		return multi_node_sort(v1, v2);

	return ret;
}

/**
 * @brief
 * 		A function which sorts the jobs according to the time they are
 *        preempted (in ascending order)
 *
 * @param[in] j1 - job to compare.
 * @param[in] j2 - job to compare.
 *
 * @return	int
 * @retval 	-1 : If j1 was preempted before j2.
 * @retval  0  : If both were preempted at the same time
 * @retval  1  : if j2 was preempted before j1.
 */
int
cmp_job_preemption_time_asc(const void *j1, const void *j2)
{
	resource_resv *r1;
	resource_resv *r2;

	r1 = *((resource_resv **) j1);
	r2 = *((resource_resv **) j2);

	if (r1 == NULL && r2 == NULL)
		return 0;

	if (r1 != NULL && r2 == NULL)
		return -1;

	if (r1 == NULL && r2 != NULL)
		return 1;

	if (r1->job == NULL || r2->job ==NULL)
		return 0;

	/* If one job is preempted and second is not then preempted job gets priority
	 * If both jobs are preempted, one which is preempted first gets priority
	 */
	if (r1->job->time_preempted == UNSPECIFIED &&
		r2->job->time_preempted ==UNSPECIFIED)
		return 0;
	else if (r1->job->time_preempted != UNSPECIFIED &&
		r2->job->time_preempted ==UNSPECIFIED)
		return -1;
	else if (r1->job->time_preempted == UNSPECIFIED &&
		r2->job->time_preempted !=UNSPECIFIED)
		return 1;

	if (r1->job->time_preempted < r2->job->time_preempted)
		return -1;
	else if (r1->job->time_preempted > r2->job->time_preempted)
		return 1;
	return 0;
}

/**
 * @brief
 * 		cmp_starving_jobs - compare based on eligible_time
 *
 * @param[in] j1 - job to compare.
 * @param[in] j2 - job to compare.
 *
 * @return	int
 * @retval -1 : If j1 was starving and j2 is not.
 * @retval  0 : If both are either starving or not starving.
 * @retval  1 : if j2 was starving and j1 is not.
 */
int
cmp_starving_jobs(const void *j1, const void *j2)
{
	resource_resv *r1 = *(resource_resv**)j1;
	resource_resv *r2 = *(resource_resv**)j2;

	if (r1 == NULL && r2 == NULL)
		return 0;

	if (r1 != NULL && r2 == NULL)
		return -1;

	if (r1 == NULL && r2 != NULL)
		return 1;

	if (r1->job == NULL || r2->job ==NULL)
		return 0;

	if (!r1->job->is_starving && !r2->job->is_starving)
		return 0;
	else if (!r1->job->is_starving  && r2->job->is_starving)
		return 1;
	else if (r1->job->is_starving && !r2->job->is_starving)
		return -1;

	if (r1->sch_priority > r2->sch_priority)
		return -1;
	if (r1->sch_priority < r2->sch_priority)
		return 1;
	return 0;
}

/**
 * @brief
 * 		sort_jobs - This function sorts all jobs according to their preemption
 *      priority, preempted time and fairshare.
 *		sort_jobs is called whenever we need to sort jobs on the basis of
 *		various policies set in scheduler.
 * @param[in]		policy	-	Policy structure to decide whether to sort for fairshare or
 *                     			not. If yes, then according should it be according to
 *                     			by_queue or round_robin.
 * @param[in,out]	sinfo 	- 	Server info struct which contains all the jobs that needs
 *                        		sorting.
 * @return	void
 */
void
sort_jobs(status *policy, server_info *sinfo)
{
	int i = 0;
	int job_index = 0;
	int index = 0;
	int count = 0;

	/** sort jobs in such a way that Higher Priority jobs come on top
	 * followed by preempted jobs and then starving jobs and normal jobs
	 */
	if (policy->fair_share) {
		/** sort per queue basis and then use these jobs (combined from all the queues)
		 * to select the next job.
		 */
		if (policy->by_queue || policy->round_robin) {
			/* cycle through queues and sort them on the basis of preemption priority,
			 * preempted jobs, starving jobs and fairshare usage
			 */
			for (; i < sinfo->num_queues; i++) {
				if (sinfo->queues[i]->sc.total > 0) {
					qsort(sinfo->queues[i]->jobs, sinfo->queues[i]->sc.total,
						sizeof(resource_resv*), cmp_sort);
				}
			}
			for (count = 0; count != sinfo->num_queues; count++) {
				for (index = 0; index < sinfo->queues[count]->sc.total; index++) {
					sinfo->jobs[job_index] = sinfo->queues[count]->jobs[index];
					job_index++;
				}
			}
			sinfo->jobs[job_index] = NULL;
		}
		/** Sort on entire complex **/
		else if (!policy->by_queue && !policy->round_robin) {
			qsort(sinfo->jobs, count_array((void**)sinfo->jobs),
				sizeof(resource_resv *), cmp_sort);
		}
	}
	else if (policy->by_queue) {
		for (i = 0; i < sinfo->num_queues; i++) {
			qsort(sinfo->queues[i]->jobs, count_array((void**)sinfo->queues[i]->jobs),
				sizeof(resource_resv *), cmp_sort);
		}
		qsort(sinfo->jobs, count_array((void**)sinfo->jobs), sizeof(resource_resv*), cmp_sort);
	}
	else if (policy->round_robin) {
		if (sinfo -> queue_list != NULL) {
			int queue_list_size = count_array((void**)sinfo->queue_list);
			int i,j;
			for (i = 0; i < queue_list_size; i++)
			{
				int queue_index_size = count_array((void **)sinfo->queue_list[i]);
				for (j = 0; j < queue_index_size; j++)
				{
				    qsort(sinfo->queue_list[i][j]->jobs, count_array((void**)sinfo->queue_list[i][j]->jobs),
					    sizeof(resource_resv *), cmp_sort);
				}
			}

		}
	}
	else
		qsort(sinfo->jobs, count_array((void**)sinfo->jobs), sizeof(resource_resv*), cmp_sort);
}

/*
 * the following code is compiled if built on a Sun system as there seems
 * to be a problem with Sun's qsort.
 */

#ifdef sun

/*-
 * Copyright (c) 1992, 1993
 *	The Regents of the University of California.  All rights reserved.
 *
 * Redistribution and use in source and binary forms, with or without
 * modification, are permitted provided that the following conditions
 * are met:
 * 1. Redistributions of source code must retain the above copyright
 *    notice, this list of conditions and the following disclaimer.
 * 2. Redistributions in binary form must reproduce the above copyright
 *    notice, this list of conditions and the following disclaimer in the
 *    documentation and/or other materials provided with the distribution.
 * 3. All advertising materials mentioning features or use of this software
 *    must display the following acknowledgement:
 *	This product includes software developed by the University of
 *	California, Berkeley and its contributors.
 * 4. Neither the name of the University nor the names of its contributors
 *    may be used to endorse or promote products derived from this software
 *    without specific prior written permission.
 *
 * THIS SOFTWARE IS PROVIDED BY THE REGENTS AND CONTRIBUTORS ``AS IS'' AND
 * ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
 * IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
 * ARE DISCLAIMED.  IN NO EVENT SHALL THE REGENTS OR CONTRIBUTORS BE LIABLE
 * FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
 * DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
 * OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
 * HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
 * LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
 * OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
 * SUCH DAMAGE.
 */

#if defined(LIBC_SCCS) && !defined(lint)
#if 0
static char sccsid[] = "@(#)qsort.c	8.1 (Berkeley) 6/4/93";
#endif
static const char rcsid[] =
	"$FreeBSD: src/lib/libc/stdlib/qsort.c,v 1.8 1999/08/28 00:01:35 peter Exp $";
#endif /* LIBC_SCCS and not lint */

#include <stdlib.h>

typedef int		 cmp_t(const void *, const void *);
static char	*med3(char *, char *, char *, cmp_t *);
static void	 swapfunc(char *, char *, int, int);

#define min(a, b)	(a) < (b) ? a : b

/*
 * Qsort routine from Bentley & McIlroy's "Engineering a Sort Function".
 */
#define swapcode(TYPE, parmi, parmj, n) { 		\
	long i = (n) / sizeof (TYPE); 			\
	register TYPE *pi = (TYPE *) (parmi); 		\
	register TYPE *pj = (TYPE *) (parmj); 		\
	do { 						\
		register TYPE	t = *pi;		\
		*pi++ = *pj;				\
		*pj++ = t;				\
        } while (--i > 0);				\
}

#define SWAPINIT(a, es) swaptype = ((char *)a - (char *)0) % sizeof(long) || \
	es % sizeof(long) ? 2 : es == sizeof(long)? 0 : 1;
/**
 * @brief
 * 		swap the value between a and b.
 *
 * @param[in,out]	a		-	value 1 to be swapped
 * @param[in,out]	b		-	value 2 to be swapped
 * @param[in]		n		-	size in bytes
 * @param[in]		type	-	type of object
 */
static void
swapfunc(char *a, char *b, int n, int swaptype)
{
	if (swaptype <= 1)
		swapcode(long, a, b, n)
		else
			swapcode(char, a, b, n)
		}

#define swap(a, b)					\
	if (swaptype == 0) {				\
		long t = *(long *)(a);			\
		*(long *)(a) = *(long *)(b);		\
		*(long *)(b) = t;			\
	} else						\
		swapfunc(a, b, es, swaptype)

#define vecswap(a, b, n) 	if ((n) > 0) swapfunc(a, b, n, swaptype)
/**
 * @brief
 * 		compare a,b,c using the cmp function.
 *
 * @param[in]	a	-	object 1
 * @param[in]	b	-	object 2
 * @param[in]	c	-	object 3
 * @param[in]	cmp	-	compare function.
 *
 * @return	result from cmp function
 */
static char *
med3(char *a, char *b, char *c, cmp_t *cmp)
{
	return cmp(a, b) < 0 ?
		(cmp(b, c) < 0 ? b : (cmp(a, c) < 0 ? c : a))
		:(cmp(b, c) > 0 ? b : (cmp(a, c) < 0 ? a : c));
}
/**
 * @brief
 * 		qsort function
 *
 * @param[in,out]	a	-	array to be sorted
 * @param[in]		n	-	total size of the array
 * @param[in]		es	-	size of a single object
 * @param[in]		cmp	-	compare function.
 */
void
qsort(void *a, size_t n, size_t es, cmp_t *cmp)
{
	char *pa, *pb, *pc, *pd, *pl, *pm, *pn;
	int d, r, swaptype, swap_cnt;

	loop:	SWAPINIT(a, es);
	swap_cnt = 0;
	if (n < 7) {
		for (pm = (char *)a + es; pm < (char *)a + n * es; pm += es)
			for (pl = pm; pl > (char *)a && cmp(pl - es, pl) > 0;
				pl -= es)
					swap(pl, pl - es);
		return;
	}
	pm = (char *)a + (n / 2) * es;
	if (n > 7) {
		pl = a;
		pn = (char *)a + (n - 1) * es;
		if (n > 40) {
			d = (n / 8) * es;
			pl = med3(pl, pl + d, pl + 2 * d, cmp);
			pm = med3(pm - d, pm, pm + d, cmp);
			pn = med3(pn - 2 * d, pn - d, pn, cmp);
		}
		pm = med3(pl, pm, pn, cmp);
	}
	swap(a, pm);
	pa = pb = (char *)a + es;

	pc = pd = (char *)a + (n - 1) * es;
	for (;;) {
		while (pb <= pc && (r = cmp(pb, a)) <= 0) {
			if (r == 0) {
				swap_cnt = 1;
				swap(pa, pb);
				pa += es;
			}
			pb += es;
		}
		while (pb <= pc && (r = cmp(pc, a)) >= 0) {
			if (r == 0) {
				swap_cnt = 1;
				swap(pc, pd);
				pd -= es;
			}
			pc -= es;
		}
		if (pb > pc)
			break;
		swap(pb, pc);
		swap_cnt = 1;
		pb += es;
		pc -= es;
	}
	if (swap_cnt == 0) {  /* Switch to insertion sort */
		for (pm = (char *)a + es; pm < (char *)a + n * es; pm += es)
			for (pl = pm; pl > (char *)a && cmp(pl - es, pl) > 0;
				pl -= es)
					swap(pl, pl - es);
		return;
	}

	pn = (char *)a + n * es;
	r = min(pa - (char *)a, pb - pa);
	vecswap(a, pb - r, r);
	r = min(pd - pc, pn - pd - es);
	vecswap(pb, pn - r, r);
	if ((r = pb - pa) > es)
		qsort(a, r / es, es, cmp);
	if ((r = pd - pc) > es) {
		/* Iterate rather than recurse to save stack space */
		a = pn - r;
		n = r / es;
		goto loop;
	}
	/*		qsort(pn - r, r / es, es, cmp);*/
}
#endif /* sun */

