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

#ifndef SRC_SCHEDULER_QUEUE_H_
#define SRC_SCHEDULER_QUEUE_H_

#ifdef __cplusplus
extern "C" {
#endif



#define QUEUE_DS_MIN_SIZE 512	/* Minimum size of the queue data structure */

typedef struct ds_queue ds_queue;

struct ds_queue {
	int min_size;
	long front;
	long rear;
	long q_size;
	void **content_arr;
};

ds_queue *new_ds_queue(void);
void free_ds_queue(ds_queue *queue);
int ds_enqueue(ds_queue *queue, void *obj);
void *ds_dequeue(ds_queue *queue);
int ds_queue_is_empty(ds_queue *queue);

#ifdef __cplusplus
}
#endif

#endif /* SRC_SCHEDULER_QUEUE_H_ */
