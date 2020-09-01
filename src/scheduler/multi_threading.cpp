/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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


#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <unistd.h>
#include <pthread.h>
#include <errno.h>
#include <signal.h>

#include "log.h"
#include "pbs_idx.h"

#include "constant.hpp"
#include "misc.hpp"
#include "data_types.hpp"
#include "globals.hpp"
#include "node_info.hpp"
#include "queue.hpp"
#include "fifo.hpp"
#include "resource_resv.hpp"
#include "multi_threading.hpp"


/**
 * @brief	initialize a mutex attr object
 *
 * @param[out]	attr - the attr object to initialize
 *
 * @return int
 * @retval 1 for Success
 * @retval 0 for Error
 */
int
init_mutex_attr_recursive(pthread_mutexattr_t *attr)
{
	if (pthread_mutexattr_init(attr) != 0) {
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SCHED, LOG_ERR, __func__,
				"pthread_mutexattr_init failed");
		return 0;
	}

	if (pthread_mutexattr_settype(attr,
#if defined (linux)
			PTHREAD_MUTEX_RECURSIVE_NP
#else
			PTHREAD_MUTEX_RECURSIVE
#endif
	)) {
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SCHED, LOG_ERR, __func__,
				"pthread_mutexattr_settype failed");
		return 0;
	}

	return 1;
}

/**
 * @brief	create the thread id key & set it for the main thread
 *
 * @param	void
 *
 * @return	void
 */
static void
create_id_key(void)
{
	int *mainid;

	mainid = static_cast<int *>(malloc(sizeof(int)));
	if (mainid == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return;
	}
	*mainid = 0;

	pthread_key_create(&th_id_key, free);
	pthread_setspecific(th_id_key, (void *) mainid);
}

/**
 * @brief	convenience function to kill worker threads
 *
 * @param	void
 *
 * @return	void
 */
void
kill_threads(void)
{
	int i;

	log_event(PBSEVENT_DEBUG, PBS_EVENTCLASS_REQUEST, LOG_DEBUG,
				"", "Killing worker threads");

	threads_die = 1;
	pthread_mutex_lock(&work_lock);
	pthread_cond_broadcast(&work_cond);
	pthread_mutex_unlock(&work_lock);

	/* Wait until all threads to finish */
	for (i = 0; i < num_threads; i++) {
		pthread_join(threads[i], NULL);
	}
	pthread_mutex_destroy(&work_lock);
	pthread_cond_destroy(&work_cond);
	pthread_mutex_destroy(&result_lock);
	pthread_cond_destroy(&result_cond);
	pthread_mutex_destroy(&general_lock);
	free(threads);
	free_ds_queue(work_queue);
	free_ds_queue(result_queue);
	threads = NULL;
	num_threads = 0;
	work_queue = NULL;
	result_queue = NULL;
}

/**
 * @brief	initialize multi-threading
 *
 * @param[in]	nthreads - number of threads to create, or -1 to use default
 *
 * @return	int
 * @retval	1 for success
 * @retval	0 for malloc error
 */
int
init_multi_threading(int nthreads)
{
	int i;
	int num_cores;
	pthread_mutexattr_t attr;

	/* Kill any existing worker threads */
	if (num_threads > 1)
		kill_threads();

	threads_die = 0;
	if (pthread_cond_init(&work_cond, NULL) != 0) {
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SCHED, LOG_ERR, __func__,
				"pthread_cond_init failed");
		return 0;
	}
	if (pthread_cond_init(&result_cond, NULL) != 0) {
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SCHED, LOG_ERR, __func__,
				"pthread_cond_init failed");
		return 0;
	}


	if (init_mutex_attr_recursive(&attr) == 0)
		return 0;

	pthread_mutex_init(&work_lock, &attr);
	pthread_mutex_init(&result_lock, &attr);
	pthread_mutex_init(&general_lock, &attr);

	num_cores = sysconf(_SC_NPROCESSORS_ONLN);
	if (nthreads < 1 && num_cores > 2)
		/* Create as many threads as half the number of cores */
		num_threads = num_cores / 2;
	else
		num_threads = nthreads;

	if (num_threads <= 1) {
		num_threads = 1;
		return 1; /* main thread will act as the only worker thread */
	}

	log_eventf(PBSEVENT_DEBUG, PBS_EVENTCLASS_REQUEST, LOG_DEBUG,
			"", "Launching %d worker threads", num_threads);

	threads = static_cast<pthread_t *>(malloc(num_threads * sizeof(pthread_t)));
	if (threads == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return 0;
	}

	/* Create task and result queues */
	work_queue = new_ds_queue();
	if (work_queue == NULL) {
		free(threads);
		return 0;
	}
	result_queue = new_ds_queue();
	if (result_queue == NULL) {
		free(threads);
		free_ds_queue(work_queue);
		work_queue = NULL;
		return 0;
	}

	pthread_once(&key_once, create_id_key);
	for (i = 0; i < num_threads; i++) {
		int *thid;

		thid = static_cast<int *>(malloc(sizeof(int)));
		if (thid == NULL) {
			free(threads);
			free_ds_queue(work_queue);
			free_ds_queue(result_queue);
			work_queue = NULL;
			result_queue = NULL;
			log_err(errno, __func__, MEM_ERR_MSG);
			return 0;
		}
		*thid = i + 1;
		pthread_create(&(threads[i]), NULL, &worker, (void *) thid);
	}

	return 1;
}

/**
 * @brief	Main pthread routine for worker threads
 *
 * @param[in]	tid  - thread id of the thread
 *
 * @return void
 */
void *
worker(void *tid)
{
	th_task_info *work = NULL;
	sigset_t set;
	int ntid;
	char buf[1024];

	pthread_setspecific(th_id_key, tid);
	ntid = *(int *)tid;

	/* Block HUPs, if we ever unblock this, we'll need to modify 'restart()' to handle MT */
	sigemptyset(&set);
	sigaddset(&set, SIGHUP);

	if (pthread_sigmask(SIG_BLOCK, &set, NULL) != 0) {
		log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SCHED, LOG_ERR, __func__,
				"pthread_sigmask failed");
		pthread_exit(NULL);
	}

	while (!threads_die) {
		/* Get the next work task from work queue */
		pthread_mutex_lock(&work_lock);
		while (ds_queue_is_empty(work_queue) && !threads_die) {
			pthread_cond_wait(&work_cond, &work_lock);
		}
		work = static_cast<th_task_info *>(ds_dequeue(work_queue));
		pthread_mutex_unlock(&work_lock);

		/* find out what task we need to do */
		if (work != NULL) {
			switch (work->task_type) {
			case TS_IS_ND_ELIGIBLE:
				snprintf(buf, sizeof(buf), "Thread %d calling check_node_eligibility_chunk()", ntid);
				log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SCHED, LOG_DEBUG, __func__, buf);
				check_node_eligibility_chunk((th_data_nd_eligible *) work->thread_data);
				break;
			case TS_DUP_ND_INFO:
				snprintf(buf, sizeof(buf), "Thread %d calling dup_node_info_chunk()", ntid);
				log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SCHED, LOG_DEBUG, __func__, buf);
				dup_node_info_chunk((th_data_dup_nd_info *) work->thread_data);
				break;
			case TS_QUERY_ND_INFO:
				snprintf(buf, sizeof(buf), "Thread %d calling query_node_info_chunk()", ntid);
				log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SCHED, LOG_DEBUG, __func__, buf);
				query_node_info_chunk((th_data_query_ninfo *) work->thread_data);
				break;
			case TS_FREE_ND_INFO:
				snprintf(buf, sizeof(buf), "Thread %d calling free_node_info_chunk()", ntid);
				log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SCHED, LOG_DEBUG, __func__, buf);
				free_node_info_chunk((th_data_free_ninfo *) work->thread_data);
				break;
			case TS_DUP_RESRESV:
				snprintf(buf, sizeof(buf), "Thread %d calling dup_resource_resv_array_chunk()", ntid);
				log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SCHED, LOG_DEBUG, __func__, buf);
				dup_resource_resv_array_chunk((th_data_dup_resresv *) work->thread_data);
				break;
			case TS_QUERY_JOB_INFO:
				snprintf(buf, sizeof(buf), "Thread %d calling query_jobs_chunk()", ntid);
				log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SCHED, LOG_DEBUG, __func__, buf);
				query_jobs_chunk((th_data_query_jinfo *) work->thread_data);
				break;
			case TS_FREE_RESRESV:
				snprintf(buf, sizeof(buf), "Thread %d calling free_resource_resv_array_chunk()", ntid);
				log_event(PBSEVENT_DEBUG3, PBS_EVENTCLASS_SCHED, LOG_DEBUG, __func__, buf);
				free_resource_resv_array_chunk((th_data_free_resresv *) work->thread_data);
				break;
			default:
				log_event(PBSEVENT_ERROR, PBS_EVENTCLASS_SCHED, LOG_ERR, __func__,
						"Invalid task type passed to worker thread");
			}

			/* Post results */
			pthread_mutex_lock(&result_lock);
			ds_enqueue(result_queue, (void *) work);
			pthread_cond_signal(&result_cond);
			pthread_mutex_unlock(&result_lock);
		}
	}

	pthread_exit(NULL);
}

/**
 * @brief	Convenience function to queue up work for worker threads
 *
 * @param[in]	task - the task to queue up
 *
 * @return void
 */
void
queue_work_for_threads(th_task_info *task)
{
	pthread_mutex_lock(&work_lock);
	ds_enqueue(work_queue, (void *) task);
	pthread_cond_signal(&work_cond);
	pthread_mutex_unlock(&work_lock);
}
