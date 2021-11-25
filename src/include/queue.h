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

#ifndef _QUEUE_H
#define _QUEUE_H
#ifdef __cplusplus
extern "C" {
#endif

#include "attribute.h"
#include "server_limits.h"

#define QTYPE_Unset 0
#define QTYPE_Execution 1
#define QTYPE_RoutePush 2
#define QTYPE_RoutePull 3

/*
 * Attributes, including the various resource-lists are maintained in an
 * array in a "decoded or parsed" form for quick access to the value.
 *
 * The following enum defines the index into the array.
 */

enum queueattr {
#include "queue_attr_enum.h"
#include "site_que_attr_enum.h"
	QA_ATR_LAST /* WARNING: Must be the highest valued enum */
};

extern void *que_attr_idx;
extern attribute_def que_attr_def[];

/* at last we come to the queue definition itself	*/

struct pbs_queue {
	pbs_list_link qu_link; /* forward/backward links */
	pbs_list_head qu_jobs; /* jobs in this queue */
	resc_resv *qu_resvp;   /* != NULL if que established */
	/* to support a reservation */
	int qu_nseldft;		   /* number of elm in qu_seldft */
	key_value_pair *qu_seldft; /* defaults for job -l select */

	char qs_hash[DIGEST_LENGTH];
	struct queuefix {
		int qu_type;			    /* queue type: exec, route */
		char qu_name[PBS_MAXQUEUENAME + 1]; /* queue name */
	} qu_qs;

	int qu_numjobs;			 /* current numb jobs in queue */
	int qu_njstate[PBS_NUMJOBSTATE]; /* # of jobs per state */

	/* the queue attributes */

	attribute qu_attr[QA_ATR_LAST];
	short newobj;
};
typedef struct pbs_queue pbs_queue;

extern void *queues_idx;

extern pbs_queue *find_queuebyname(char *);
#ifdef NAS /* localmod 075 */
extern pbs_queue *find_resvqueuebyname(char *);
#endif /* localmod 075 */
extern pbs_queue *get_dfltque(void);
extern pbs_queue *que_alloc(char *);
extern pbs_queue *que_recov_db(char *, pbs_queue *);
extern void que_free(pbs_queue *);
extern int que_save_db(pbs_queue *);

#define QUE_SAVE_FULL 0
#define QUE_SAVE_NEW 1

attribute *get_qattr(const pbs_queue *pq, int attr_idx);
char *get_qattr_str(const pbs_queue *pq, int attr_idx);
struct array_strings *get_qattr_arst(const pbs_queue *pq, int attr_idx);
pbs_list_head get_qattr_list(const pbs_queue *pq, int attr_idx);
long get_qattr_long(const pbs_queue *pq, int attr_idx);
int set_qattr_generic(pbs_queue *pq, int attr_idx, char *val, char *rscn, enum batch_op op);
int set_qattr_str_slim(pbs_queue *pq, int attr_idx, char *val, char *rscn);
int set_qattr_l_slim(pbs_queue *pq, int attr_idx, long val, enum batch_op op);
int set_qattr_b_slim(pbs_queue *pq, int attr_idx, long val, enum batch_op op);
int set_qattr_c_slim(pbs_queue *pq, int attr_idx, char val, enum batch_op op);
int is_qattr_set(const pbs_queue *pq, int attr_idx);
void free_qattr(pbs_queue *pq, int attr_idx);

#ifdef __cplusplus
}
#endif
#endif /* _QUEUE_H */
