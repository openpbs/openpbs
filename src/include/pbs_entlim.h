/*
 * Copyright (C) 1994-2017 Altair Engineering, Inc.
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

#ifndef	_PBS_ENTLIM_H
#define	_PBS_ENTLIM_H
#ifdef	__cplusplus
extern "C" {
#endif
/* PBS Limits on Entities */

#ifndef AVL_DEFAULTKEYLEN
#include "avltree.h"
#endif

#define pbs_entlim_key_t AVL_IX_REC

#define PBS_MAX_RESC_NAME 1024

#define ENCODE_ENTITY_MAX 100

enum lim_keytypes {
	LIM_USER,
	LIM_GROUP,
	LIM_PROJECT,
	LIM_OVERALL
};

#define PBS_GENERIC_ENTITY "PBS_GENERIC"
#define PBS_ALL_ENTITY     "PBS_ALL"

#define ETLIM_INVALIDCHAR	"/[]\";:|<>+,?*"

void	*entlim_initialize_ctx(void);

/* get data record from an entry based on a key string */
void	*entlim_get(const char *keystr, void *ctx);

/* add a record including key and data, based on a key string */
int	 entlim_add(const char *entity, const void *recptr, void *ctx);

/* replace a record including key and data, based on a key string */
int
entlim_replace(const char *entity, void *recptr, void *ctx,
	void free_leaf(void *));

/* delete a record based on a key string */
int	 entlim_delete(const char *entity, void *ctx, void free_leaf(void *));

/* free the entire data context and all associated data and keys */
/* the function "free_leaf" is used to free the data record      */
int	 entlim_free_ctx(void *ctx, void free_leaf(void *));

/* walk the records returning a key object for the next entry found   */
/* if called with "key" set to NULL, the first key object is returned */
pbs_entlim_key_t *entlim_get_next(pbs_entlim_key_t *key, void *ctx);

/* pbs_entlim_free_key - free the key structure	*/
/*	for now a simple free()			*/
#define pbs_entlim_free_key(key) free(key)

/* get_keystr_from_key - return the key string from the key struture */
#define get_keystr_from_key(pkey) ((char *)(pkey->key))

/* entlim_parse - parse a comma separated set of "entity limit strings */
int
entlim_parse(char *str, char *resc, void *ctx,
	int (*addfunc)(void *ctx, enum lim_keytypes kt, char *fulent,
	char *entname, char *resc, char *value));
char *parse_comma_string_r(char **start);
char *entlim_mk_runkey(enum lim_keytypes kt, const char *entity);

char *entlim_mk_reskey(enum lim_keytypes kt, const char *entity, const char *resc);

int entlim_resc_from_key(pbs_entlim_key_t *, char *rtnresc, size_t ln);

int entlim_entity_from_key(pbs_entlim_key_t *, char *rtnname, size_t ln);
#ifdef	__cplusplus
}
#endif
#endif	/* _PBS_ENTLIM_H */
