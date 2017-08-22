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

/*
 * The purpose of this file is to share information between different parts
 * of PBS.
 * An example would be to share a constant between the server and the scheduler
 */


/* Formula special case constants */

#define FORMULA_FSPERC 		"fairshare_perc"
#define FORMULA_FSPERC_DEP	"fair_share_perc"
#define FORMULA_TREE_USAGE	"fairshare_tree_usage"
#define FORMULA_FSFACTOR	"fairshare_factor"
#define FORMULA_QUEUE_PRIO 	"queue_priority"
#define FORMULA_JOB_PRIO 	"job_priority"
#define FORMULA_ELIGIBLE_TIME 	"eligible_time"
#define FORMULA_ACCRUE_TYPE 	"accrue_type"

/* Well known file to store job sorting formula */
#define FORMULA_ATTR_PATH "server_priv/sched_formula"
#define FORMULA_ATTR_PATH_SCHED "sched_priv/sched_formula"

/* Constant to check preempt_targets for NONE */
#define TARGET_NONE "NONE"

/* Constants for qstat's comment field */

/* comment buffer can hold max 255 chars */
#define COMMENT_BUF_SIZE	256
/* buffer takes only 255 chars, minus 34 chars for timespec, hence the remaining.
 * sacrificing 3 chars for ...
 */
#define MAXCOMMENTSCOPE COMMENT_BUF_SIZE-1-34
#define MAXCOMMENTLEN  	COMMENT_BUF_SIZE-1-37
/* comment line has 3 spaces each at beginning and at end. hence, for qstat -s
 * 74 chars can be displayed and for qstat -sw 114 chars can be displayed.
 */
#define COMMENTLENSCOPE_SHORT 74
#define COMMENTLENSCOPE_WIDE  114
/* if comment string is longer than length of the scope then ... is appended.
 * this reduces the actual display length by 3
 */
#define COMMENTLEN_SHORT 71
#define COMMENTLEN_WIDE  111

/* number of digits to print after the decimal point for floats */
#define FLOAT_NUM_DIGITS 4

/* the size (in bytes) of a word.  All resources are kept in kilobytes
 * internally in the server.  If any specification is in words, it will be
 * converted into kilobytes with this constant
 */
#define SIZEOF_WORD 8

/* Default scheduler name */
#define PBS_DFLT_SCHED_NAME "default"
#define SC_DAEMON "scheduler"

/* scheduler-attribute values (state) */
#define SC_DOWN	"down"
#define SC_IDLE "idle"
#define SC_SCHEDULING "scheduling"

#define MAX_INT_LEN 10

