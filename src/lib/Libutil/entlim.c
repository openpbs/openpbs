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
#include <pbs_config.h>

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "pbs_entlim.h"

/* entlim iteration context structure, opaque to caller */
typedef struct _entlim_ctx {
	void *idx;
	void *idx_ctx;
} entlim_ctx;

/**
 * @brief
 * 	entlim_initialize_ctx - initialize the data context structure
 */
void *
entlim_initialize_ctx(void)
{
	entlim_ctx *pctx = malloc(sizeof(entlim_ctx));
	if (pctx == NULL)
		return NULL;
	pctx->idx_ctx = NULL;
	pctx->idx = pbs_idx_create(0, 0);
	if (pctx->idx == NULL) {
		free(pctx);
		return NULL;
	}
	return (void *)pctx;
}

/**
 * @brief
 * 	entlim_get - get record whose key is built from the given key-string
 *
 * @param[in] keystr - key string whose key is to be built
 * @param[in] ctx - pointer to context
 *
 * @return	void text
 * @retval	key		success
 * @retval	NULL		error
 *
 */

void *
entlim_get(const char *keystr, void *ctx)
{
	void *rtn;

	if (pbs_idx_find(((entlim_ctx *)ctx)->idx, (void **)&keystr, &rtn, NULL) == PBS_IDX_RET_OK)
		return rtn;
	return NULL;
}

/**
 * @brief
 * 	entlim_add - add a record with a key based on the key-string
 *
 * @param[in] keystr - key string whose key is to be built
 * @param[in] recptr - pointer to record
 * @param[in] ctx - pointer to context
 *
 * @return	int
 * @retval	0	success, record added
 * @retval	-1	add failed
 */
int
entlim_add(const char *keystr, const void *recptr, void *ctx)
{
	if (pbs_idx_insert(((entlim_ctx *)ctx)->idx, (void *)keystr, (void *)recptr) == PBS_IDX_RET_OK)
		return 0;
	return -1;
}

/**
 * @brief
 * 	entlim_replace - replace a record with a key based on the key-string
 *	if the record already exists, if not then this becomes equivalent
 *	to entlim_add().
 *
 * @param[in] keystr - key string whose key is to be built
 * @param[in] recptr - pointer to record
 * @param[in] ctx - pointer to context
 * @param[in] free_leaf() - function called to delete data record when removing
 *			    exiting record.
 *
 * @return	int
 * @retval	0	success, record replace/added
 * @retval	-1	change failed
 */
int
entlim_replace(const char *keystr, void *recptr, void *ctx, void fr_leaf(void *))
{
	void *olddata;
	entlim_ctx *pctx = (entlim_ctx *)ctx;

	if (pbs_idx_insert(pctx->idx, (void *)keystr, recptr) == PBS_IDX_RET_OK)
		return 0;
	else {
		if (pbs_idx_find(pctx->idx, (void **)&keystr, &olddata, NULL) == PBS_IDX_RET_OK) {
			if (pbs_idx_delete(pctx->idx, (void *)keystr) == PBS_IDX_RET_OK) {
				fr_leaf(olddata);
				if (pbs_idx_insert(pctx->idx, (void *)keystr, recptr) == PBS_IDX_RET_OK)
					return 0;
			}
		}
	}
	return -1;
}

/**
 * @brief
 * 	entlim_delete - delete record with a key based on the keystr
 *
 * @param[in] keystr - key string whose key is to be built
 * @param[in] recptr - pointer to record
 * @param[in] ctx - pointer to context
 * @param[in] free_leaf() - function to free the data structure associated
 *			    with the key.
 *
 * @return	int
 * @retval	0	delete success
 * @retval	-1	delete failed
 */
int
entlim_delete(const char *keystr, void *ctx, void free_leaf(void *))
{
	void *prec;

	if (pbs_idx_find(((entlim_ctx *)ctx)->idx, (void **)&keystr, &prec, NULL) == PBS_IDX_RET_OK) {
		if (pbs_idx_delete(((entlim_ctx *)ctx)->idx, (void *)keystr) == PBS_IDX_RET_OK) {
			free_leaf(prec);
			return 0;
		}
	}
	return -1;
}

/**
 * @brief
 * 	entlim_get_next - walk the objects returning the next entry.
 *	If called with a NULL key, it allocates a key and returns
 *	the first entry; otherwise it returns the next entry.
 *
 * @param[in] keystr - key string whose key is to be built
 * @param[in] ctx - pointer to context
 *
 * @return	structure handle
 * @retval	key info		success
 * @retval	NULL			error
 *		Returns NULL following the last entry or when no entry found
 *		The key needs to be freed by the caller when all is said and done.
 */
void *
entlim_get_next(void *ctx, void **key)
{

	entlim_ctx *pctx = (entlim_ctx *)ctx;
	void *data;

	if (pctx == NULL || pctx->idx == NULL)
		return NULL;

	if (key != NULL && *key != NULL) {
		if (pctx->idx_ctx == NULL)
			return NULL;
	} else {
		if (pctx->idx_ctx != NULL)
			pbs_idx_free_ctx(pctx->idx_ctx);
		pctx->idx_ctx = NULL;
	}

	if (pbs_idx_find(pctx->idx, key, &data, &pctx->idx_ctx) == PBS_IDX_RET_OK)
			return data;

	pbs_idx_free_ctx(pctx->idx_ctx);
	pctx->idx_ctx = NULL;
	*key = NULL;
	return NULL;
}

/**
 * @brief
 * 	entlim_free_ctx - free the data structure including all keys and records
 *
 * @param[in] ctx - pointer to context
 * @param[in] free_leaf() - function called to delete data record when removing
 *                          exiting record.
 *
 * @return      int
 * @retval      0       success, record freed
 * @retval      -1      freeing failed
 */

int
entlim_free_ctx(void *ctx, void free_leaf(void *))
{
	void *leaf;
	entlim_ctx *pctx = (entlim_ctx *)ctx;

	if (pctx->idx_ctx != NULL)
		pbs_idx_free_ctx(pctx->idx_ctx);
	pctx->idx_ctx = NULL;
	while (pbs_idx_find(pctx->idx, NULL, &leaf, &pctx->idx_ctx) == PBS_IDX_RET_OK) {
		free_leaf(leaf);
	}
	pbs_idx_free_ctx(pctx->idx_ctx);
	pbs_idx_destroy(pctx->idx);
	free(pctx);
	return 0;
}

/**
 * @brief
 * 	entlim_mk_keystr - make a key string from the key type, entity and resc
 *
 * @param[in] kt - enum for key token
 * @param[in] entity - entity name
 * @param[in] resc - resource name
 *
 * @return	strinf
 * @retval	ptr to key string in the heap -
 *
 * @par	WARNING - it is up to you to free it
 */
static char *
entlim_mk_keystr(enum lim_keytypes kt, const char *entity, const char *resc)
{
	size_t keylen;
	char  *pkey;
	char   ktyl;

	if (kt == LIM_USER)
		ktyl = 'u';
	else if (kt == LIM_GROUP)
		ktyl = 'g';
	else if (kt == LIM_PROJECT)
		ktyl = 'p';
	else if (kt == LIM_OVERALL)
		ktyl = 'o';
	else
		return NULL; 	/* invalid entity key type */

	keylen = 2 + strlen(entity);
	if (resc)
		keylen += 1 + strlen(resc);
	pkey = malloc(keylen+1);

	if (pkey) {
		if (resc)
			sprintf(pkey, "%c:%s;%s", ktyl, entity, resc);
		else
			sprintf(pkey, "%c:%s", ktyl, entity);
	}
	return (pkey);
}

/**
 * @brief
 * 	entlim_mk_runkey - make a key for a entity run (number of jobs) limit
 *
 * @param[in] kt - enum for key token
 * @param[in] entity - entity name
 *
 * @return      strinf
 * @retval      ptr to key string in the heap -
 *
 * @par WARNING - it is up to you to free it
 */
char *
entlim_mk_runkey(enum lim_keytypes kt, const char *entity)
{
	return entlim_mk_keystr(kt, entity, NULL);
}

/**
 * @brief
 * 	entlim_mk_reskey - make a key for a entity resource usage limit
 *
 * @param[in] kt - enum for key token
 * @param[in] entity - entity name
 *
 * @return      strinf
 * @retval      ptr to key string in the heap -
 *
 * @par WARNING - it is up to you to free it
 */
char *
entlim_mk_reskey(enum lim_keytypes kt, const char *entity, const char *resc)
{
	return entlim_mk_keystr(kt, entity, resc);
}


/**
 * @brief
 * 	entlim_entity_from_key - obtain the entity name from a key
 *
 * @param[in] key - pointer to key info
 * @param[in] rtnname - a buffer large enought to hold the max entity name +1
 * @param[in] ln      - the size of that buffer
 *
 * @return	int
 * @retval	0	entity name found and returned
 * @retval	-1	entity name would not fit
 */
int
entlim_entity_from_key(char *key, char *rtnname, size_t ln)
{
	char *pc;
	int   sz = 0;

	pc = key + 2;
	while (*pc && (*pc != ';')) {
		++sz;
		++pc;
	}
	if ((size_t)sz < ln) {
		(void)strncpy(rtnname, key + 2, sz);
		*(rtnname+sz) = '\0';
		return 0;
	}
	return -1;
}

/**
 * @brief
 * 	entlim_resc_from_key - obtain the resource name from a key if it
 *	includes one.
 *
 * @param[in] key - pointer to key info
 * @param[in] rtnname - a buffer large enought to hold the max entity name +1
 * @param[in] ln      - the size of that buffer
 *
 * @return      int
 * @retval      0 	resource name found and returned
 * @retval      -1	resource name would not fit
 * @retval	+1	no resource name found
 *
 */
int
entlim_resc_from_key(char *key, char *rtnresc, size_t ln)
{
	char *pc;

	pc = strchr(key, (int)';');
	if (pc) {
		if (strlen(++pc) < ln) {
			strcpy(rtnresc, pc);
			return 0;
		} else
			return -1;
	} else {
		*rtnresc = '\0';
		return 1;
	}
}
