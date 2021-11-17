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

struct rm_attribute {
	char *a_qualifier;
	char *a_value;
};

/*
 ** The config structure is used to save a name to be used as a key
 ** for searching and a value or function call to provide an "answer"
 ** for the name in question.
 */
typedef char *(*confunc)(struct rm_attribute *);
struct config {
	char *c_name;
	union {
		confunc c_func;
		char *c_value;
	} c_u;
};

#define RM_NPARM 20 /* max number of parameters for child */

#define RM_CMD_CLOSE 1
#define RM_CMD_REQUEST 2
#define RM_CMD_CONFIG 3
#define RM_CMD_SHUTDOWN 4

#define RM_RSP_OK 100
#define RM_RSP_ERROR 999

#define UPDATE_MOM_STATE 1

/*
 ** Macros for fast min/max.
 */
#ifndef MIN
#define MIN(a, b) (((a) < (b)) ? (a) : (b))
#endif
#ifndef MAX
#define MAX(a, b) (((a) > (b)) ? (a) : (b))
#endif

extern char *arch(struct rm_attribute *);
extern char *physmem(struct rm_attribute *);
