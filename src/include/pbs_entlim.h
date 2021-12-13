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

#ifndef _PBS_ENTLIM_H
#define _PBS_ENTLIM_H
#ifdef __cplusplus
extern "C" {
#endif

/* PBS Limits on Entities */

#include "pbs_idx.h"

#define PBS_MAX_RESC_NAME 1024

#define ENCODE_ENTITY_MAX 100

enum lim_keytypes {
	LIM_USER,
	LIM_GROUP,
	LIM_PROJECT,
	LIM_OVERALL
};

#define PBS_GENERIC_ENTITY "PBS_GENERIC"
#define PBS_ALL_ENTITY "PBS_ALL"
#define ETLIM_INVALIDCHAR "/[]\";:|<>+,?*"

/* Flags used for account_entity_limit_usages() */
#define ETLIM_ACC_CT 1 << 0	/* flag for set_entity_ct_sum_ */
#define ETLIM_ACC_RES 1 << 1	/* flag for set_entity_resc_sum_ */
#define ETLIM_ACC_QUEUED 1 << 2 /* flag for set_entity_-_sum_max */
#define ETLIM_ACC_MAX 1 << 3	/* flag for set_entity_-_sum_queued */

#define ETLIM_ACC_CT_QUEUED (ETLIM_ACC_CT | ETLIM_ACC_QUEUED)	/* set_entity_ct_sum_queued */
#define ETLIM_ACC_CT_MAX (ETLIM_ACC_CT | ETLIM_ACC_MAX)		/* set_entity_ct_sum_max */
#define ETLIM_ACC_RES_QUEUED (ETLIM_ACC_RES | ETLIM_ACC_QUEUED) /* set_entity_resc_sum_queued */
#define ETLIM_ACC_RES_MAX (ETLIM_ACC_RES | ETLIM_ACC_MAX)	/* set_entity_resc_sum_max */

#define ETLIM_ACC_ALL_RES (ETLIM_ACC_QUEUED | ETLIM_ACC_MAX | ETLIM_ACC_RES)		/* set_entity_resc_sum_* */
#define ETLIM_ACC_ALL_CT (ETLIM_ACC_QUEUED | ETLIM_ACC_MAX | ETLIM_ACC_CT)		/* set_entity_ct_sum_* */
#define ETLIM_ACC_ALL_MAX (ETLIM_ACC_CT | ETLIM_ACC_RES | ETLIM_ACC_MAX)		/* set_entity_*_sum_max */
#define ETLIM_ACC_ALL_QUEUED (ETLIM_ACC_CT | ETLIM_ACC_RES | ETLIM_ACC_QUEUED)		/* set_entity_*_sum_queued */
#define ETLIM_ACC_ALL (ETLIM_ACC_CT | ETLIM_ACC_RES | ETLIM_ACC_QUEUED | ETLIM_ACC_MAX) /* for all 4 set_entity_* */

void *entlim_initialize_ctx(void);

/* get data record from an entry based on a key string */
void *entlim_get(const char *keystr, void *ctx);

/* add a record including key and data, based on a key string */
int entlim_add(const char *entity, const void *recptr, void *ctx);

/* replace a record including key and data, based on a key string */
int entlim_replace(const char *entity, void *recptr, void *ctx, void free_leaf(void *));

/* delete a record based on a key string */
int entlim_delete(const char *entity, void *ctx, void free_leaf(void *));

/* free the entire data context and all associated data and keys */
/* the function "free_leaf" is used to free the data record      */
int entlim_free_ctx(void *ctx, void free_leaf(void *));

/* walk the records returning a key object for the next entry found */
void *entlim_get_next(void *ctx, void **key);

/* entlim_parse - parse a comma separated set of "entity limit strings */
int entlim_parse(char *str, char *resc, void *ctx,
		 int (*addfunc)(void *ctx, enum lim_keytypes kt, char *fulent,
				char *entname, char *resc, char *value));
char *parse_comma_string_r(char **start);
char *entlim_mk_runkey(enum lim_keytypes kt, const char *entity);
char *entlim_mk_reskey(enum lim_keytypes kt, const char *entity, const char *resc);
int entlim_resc_from_key(char *key, char *rtnresc, size_t ln);
int entlim_entity_from_key(char *key, char *rtnname, size_t ln);

#ifdef __cplusplus
}
#endif
#endif /* _PBS_ENTLIM_H */
