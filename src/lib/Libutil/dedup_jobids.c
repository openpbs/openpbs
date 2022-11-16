/*
 * Copyright (C) 2003-2022 Altair Engineering, Inc. All rights reserved.
 * Copyright notice does not imply publication.
 *
 * ALTAIR ENGINEERING INC. Proprietary and Confidential. Contains Trade Secret
 * Information. Not for use or disclosure outside of Licensee's organization.
 * The software and information contained herein may only be used internally and
 * is provided on a non-exclusive, non-transferable basis. License may not
 * sublicense, sell, lend, assign, rent, distribute, publicly display or
 * publicly perform the software or other information provided herein,
 * nor is Licensee permitted to decompile, reverse engineer, or
 * disassemble the software. Usage of the software and other information
 * provided by Altair(or its resellers) is only as explicitly stated in the
 * applicable end user license agreement between Altair and Licensee.
 * In the absence of such agreement, the Altair standard end user
 * license agreement terms shall govern.
 */

/* C functions module to remove duplicates in jobids list */

#include "job.h"
#include "range.h"
#include "dedup_jobids.h"
#include "pbs_idx.h"

/**
 * @brief is_array_job - determines if the job id indicates an array job
 *
 * @param[in]   id - Job Id.
 *
 * @return  Job Type
 * @retval  IS_ARRAY_NO  - A regular job
 * @retval  IS_ARRAY_ArrayJob  - A ArrayJob
 * @retval  IS_ARRAY_Single  - A single subjob
 * @retval  IS_ARRAY_Range  - A range of subjobs
 */
int
is_array_job(char *id)
{
	char *pc;

	if ((pc = strchr(id, (int) '[')) == NULL)
		return IS_ARRAY_NO; /* not an ArrayJob nor a subjob (range) */
	if (*++pc == ']')
		return IS_ARRAY_ArrayJob; /* an ArrayJob */

	/* know it is either a single subjob or an range there of */
	while (isdigit((int) *pc))
		++pc;
	if ((*pc == '-') || (*pc == ','))
		return IS_ARRAY_Range; /* a range of subjobs */
	else
		return IS_ARRAY_Single;
}

/**
 * @brief Allocate memory for new job range
 *
 * @return array_job_range_list*
 * @retval new range object
 */
array_job_range_list *
new_job_range(void)
{
	array_job_range_list *new_range;
	new_range = (array_job_range_list *) malloc(sizeof(array_job_range_list));
	if (new_range == NULL)
		return NULL;
	new_range->range = NULL;
	new_range->next = NULL;
	return new_range;
}

/**
 * @brief Helper function to split sub jobid from its range
 * @example
 *  1. For jobid "0[1-5].hostname"
 *      outjobid = "0.hostname" , sub_job_range = "1-5" 
 *  2. For jobid "0[1-5]"
 *      outjobid = "0" , sub_job_range = "1-5" 
 *
 * @param[in]  jobid
 * @param[out] array_jobid
 * @param[out] sub_job_range
 *
 * @return int
 * @retval 0 for Success
 * @retval 1 for Failure
 *
 * @par NOTE: out_jobid will contain jobid without sub job range.
 */
int
split_sub_jobid(char *jobid, char **out_jobid, char **sub_job_range)
{
	char *range = NULL, *hostname, *array_jobid;
	char *pc = NULL, save;

	/* subjobid */
	pc = strchr(jobid, (int) '[');
	save = *pc;
	*pc = '\0';
	array_jobid = strdup(jobid);
	*pc = save;

	/* range */
	range = ++pc;
	pc = strchr(range, (int) ']');
	save = *pc;
	*pc = '\0';
	*sub_job_range = strdup(range);
	*pc = save;

	/* hostname */
	pc = strchr(jobid, (int) '.');
	if (pc == NULL) {
		*out_jobid = array_jobid;
		return 0;
	}
	hostname = strdup(++pc);
	/* one extra for the '.' */
	*out_jobid = (char *) malloc(strlen(array_jobid) + strlen(hostname) + 2);
	if (*out_jobid == NULL)
		return 1;
	sprintf(*out_jobid, "%s.%s", array_jobid, hostname);
	free(array_jobid);
	free(hostname);

	return 0;
}

/**
 * @brief Remove duplicate jobids from jobids list
 *
 * @param [in,out] jobids list of jobids
 * @param [in,out] numjids total count of jobids
 * @param [in,out] malloc_track to track the memory allocated
 * 
 * @return int
 * @retval 0  for Success
 * @retval -1 for Failure
 */
int
dedup_jobids(char **jobids, int *numjids, char *malloc_track)
{
	void *index = NULL;
	void *non_array_jobs_idx = NULL;
	void *array_jobs_idx = NULL;
	int uni_jobids = 0;	  /* counter for unique jobids */
	int uni_array_jobids = 0; /* counter for unique array jobids */
	int i = 0, j = 0, rc = 0, dup = 0, ret = 0, is_job_array = 0;
	char **array_jobid_list = NULL;
	char *array_job_range = NULL, *array_jobid = NULL, *hostname = NULL;
	char temp_range[256] = {
		'\0',
	};
	range *r1 = NULL, *r2 = NULL, *r3 = NULL;
	array_job_range_list **srange_list = NULL, *srange = NULL, *new_srange = NULL;
	int original_numjids = *numjids;
	
	if (jobids == NULL || numjids == NULL)
		return -1;

	array_jobid_list = calloc((*numjids + 1), sizeof(char *));
	if (array_jobid_list == NULL)
		return -1;

	srange_list = calloc((*numjids), sizeof(array_job_range_list *));
	if (array_jobid_list == NULL)
		return -1;

	non_array_jobs_idx = pbs_idx_create(0, 0);
	array_jobs_idx = pbs_idx_create(0, 0);

	for (i = 0, j = 0; i < *numjids; i++) {
		is_job_array = is_array_job(jobids[i]);
		if (is_job_array == IS_ARRAY_ArrayJob ||
				is_job_array == IS_ARRAY_Single ||
				is_job_array == IS_ARRAY_Range) {
			dup = 0;
			if (split_sub_jobid(jobids[i], &array_jobid, &array_job_range) != 0) {
				ret = -1;
				goto err;
			}
			new_srange = new_job_range();
			if (new_srange == NULL) {
				ret = -1;
				goto err;
			}
			new_srange->range = array_job_range;
			srange_list[i] = new_srange;
			if (pbs_idx_find(array_jobs_idx, (void **) &array_jobid,
					 (void **) &srange,
					 NULL) == PBS_IDX_RET_OK) {
				/* found duplicate, update the range */
				dup = 1;
				new_srange->next = srange;
				srange = new_srange;
				/* Delete existing value */
				if (pbs_idx_delete(array_jobs_idx,
						   array_jobid) != PBS_IDX_RET_OK) {
					ret = -1;
					goto err;
				}
			} else
				srange = new_srange;
			if (pbs_idx_insert(array_jobs_idx, array_jobid, srange) !=
			    PBS_IDX_RET_OK) {
				ret = -1;
				goto err;
			}
			if (!dup) {
				array_jobid_list[j] = array_jobid;
				j++;
				uni_array_jobids++;
			} else
				free(array_jobid);
		} else if (non_array_jobs_idx) { /* For Normal jobs */
			rc = pbs_idx_find(non_array_jobs_idx, (void **) &jobids[i],
					  (void **) &index, NULL);
			if (rc == PBS_IDX_RET_OK)
				continue;
			rc = pbs_idx_insert(non_array_jobs_idx, jobids[i], NULL);
			if (rc == PBS_IDX_RET_OK) {
				jobids[uni_jobids] = jobids[i];
				uni_jobids++; /* counter for non array jobs */
			}
		}
	}
	array_jobid_list[j] = NULL;

	/*
	If the same jobids present with different ranges then
	join their ranges, to avoid the overlaping / duplicates
	of subjobids.
	*/
	for (i = 0; array_jobid_list[i] != NULL; i++, uni_jobids++) {
		if (pbs_idx_find(array_jobs_idx, (void **) &array_jobid_list[i],
				 (void **) &srange, NULL) == PBS_IDX_RET_OK) {
			memset(temp_range, '\0', sizeof(temp_range));
			for (; srange; srange = (array_job_range_list *) srange->next) {
				if (strlen(temp_range) == 0) {
					strncpy(temp_range, srange->range,
						sizeof(temp_range) - 1);
					continue;
				}
				r1 = range_parse(temp_range);
				r2 = range_parse(srange->range);
				r3 = range_join(r1, r2);
				strncpy(temp_range, range_to_str(r3),
					sizeof(temp_range) - 1);
			}
		}
		/* one for '[', one for ']' and one for '.' */
		jobids[uni_jobids] = (char *) malloc(strlen(array_jobid_list[i]) + strlen(temp_range) + 4);
		if (jobids[uni_jobids] == NULL) {
			ret = -1;
			goto err;
		}
		malloc_track[uni_jobids] = 1;
		hostname = strchr(array_jobid_list[i], (int) '.');
		if (hostname == NULL)
			sprintf(jobids[uni_jobids], "%s[%s]", array_jobid_list[i],
				temp_range);
		else {
			*hostname = '\0';
			sprintf(jobids[uni_jobids], "%s[%s].%s",
				array_jobid_list[i], temp_range, ++hostname);
		}
	}
	*numjids = uni_jobids;
	ret = 0;
err:
	free_string_array(array_jobid_list);
	for (i = 0; i < original_numjids; i++) {
		if (srange_list[i]) {
			if (srange_list[i]->range)
				free(srange_list[i]->range);
			free(srange_list[i]);
		}
	}
	free(srange_list);
	pbs_idx_destroy(non_array_jobs_idx);
	pbs_idx_destroy(array_jobs_idx);
	free_range_list(r1);
	free_range_list(r2);
	free_range_list(r3);

	return ret;
}
