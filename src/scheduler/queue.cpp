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


#include <stdio.h>
#include <stdlib.h>
#include <errno.h>

#include "constant.h"
#include "log.h"
#include "queue.h"


/**
 * @brief	Constructor for the data structure 'queue'
 *
 * @param	void
 *
 * @return queue *
 * @retval a newly allocated queue object
 * @retval NULL for malloc error
 */
ds_queue *
new_ds_queue(void)
{
	ds_queue *ret_obj;

	ret_obj = static_cast<ds_queue *>(malloc(sizeof(ds_queue)));
	if (ret_obj == NULL) {
		log_err(errno, __func__, MEM_ERR_MSG);
		return NULL;
	}

	ret_obj->min_size = QUEUE_DS_MIN_SIZE;
	ret_obj->content_arr = NULL;
	ret_obj->front = 0;
	ret_obj->rear = 0;
	ret_obj->q_size = 0;

	return ret_obj;
}

/**
 * @brief	Destructor for a queue object
 *
 * @param[in]	queue - the queue object to deallocate
 *
 * @return void
 */
void
free_ds_queue(ds_queue *queue)
{
	if (queue != NULL) {
		free(queue->content_arr);
		free(queue);
	}
}


/**
 * @brief	Enqueue an object into the queue
 *
 * @param[in]	queue - the queue to enqueue the object in
 * @param[in]	obj - the object to enqueue
 *
 * @return int
 * @retval 1 for Success
 * @retval 0 for Failure
 */
int
ds_enqueue(ds_queue *queue, void *obj)
{
	long curr_rear;
	long curr_qsize;

	if (queue == NULL || obj == NULL)
		return 0;

	curr_rear = queue->rear;
	curr_qsize = queue->q_size;

	if (curr_rear >= curr_qsize) {
		long new_qsize;
		void **realloc_ptr = NULL;

		/* Need to resize the queue */
		if (curr_qsize == 0) /* First enqueue operation */
			new_qsize = queue->min_size;
		else
			new_qsize = 2 * curr_qsize;

		realloc_ptr = static_cast<void **>(realloc(queue->content_arr, new_qsize * sizeof(void *)));
		if (realloc_ptr == NULL) {
			log_err(errno, __func__, MEM_ERR_MSG);
			return 0;
		}

		queue->content_arr = realloc_ptr;
		queue->q_size = new_qsize;
	}

	queue->content_arr[curr_rear] = obj;
	queue->rear = curr_rear + 1;

	return 1;
}

/**
 * @brief	Dequeue an object from the queue
 *
 * @param[in]	queue - the queue to use
 *
 * @return void *
 * @retval the first item in queue
 * @retval NULL for error/empty queue
 */
void *
ds_dequeue(ds_queue *queue)
{
	if (queue == NULL)
		return NULL;

	if (queue->front == queue->rear) { /* queue is empty */
		/* Reset front and rear pointers */
		queue->front = 0;
		queue->rear = 0;
		return NULL;
	}

	return queue->content_arr[queue->front++];
}

/**
 * @brief	Check if a queue is empty
 *
 * @param[in]	queue  - the queue to use
 *
 * @return int
 * @retval 1 if queue is empty
 * @retval 0 otherwise
 */
int
ds_queue_is_empty(ds_queue *queue)
{
	if (queue == NULL)
		return 1;
	if (queue->front == queue->rear) {
		/* Make sure front and rear pointers are set to 0 */
		queue->front = 0;
		queue->rear = 0;
		return 1;
	} else
		return 0;
}
