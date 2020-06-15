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

#include "pbs_idx.h"
#include "avltree.h"
#include <stddef.h>
#include <stdlib.h>
#include <string.h>

/* iteration context structure, opaque to application */
typedef struct _iter_ctx {
	AVL_IX_DESC *idx; /* pointer to idx */
	AVL_IX_REC *pkey; /* pointer to key used while iteration */
} iter_ctx;

/**
 * @brief
 *	get tls (create if needed) for index methods
 *
 * @return void *
 * @retval !NULL - success
 * @retval NULL  - failure
 *
 */
void *
pbs_idx_get_tls(void)
{
	return get_avl_tls();
}

/**
 * @brief
 *	Create an empty index
 *
 * @param[in] - dups   - Whether duplicates are allowed or not in index
 * @param[in] - keylen - length of key in index (can be 0 for default size)
 *
 * @return void *
 * @retval !NULL - success
 * @retval NULL  - failure
 *
 */
void *
pbs_idx_create(int dups, int keylen)
{
	void *idx = NULL;

	idx = malloc(sizeof(AVL_IX_DESC));
	if (idx == NULL)
		return NULL;

	if (avl_create_index(idx, dups, keylen)) {
		free(idx);
		return NULL;
	}

	return idx;
}

/**
 * @brief
 *	destroy index
 *
 * @param[in] - idx - pointer to index
 *
 * @return void
 *
 */
void
pbs_idx_destroy(void *idx)
{
	if (idx != NULL) {
		avl_destroy_index(idx);
		free(idx);
		idx = NULL;
	}
}

/**
 * @brief
 *	add entry in index
 *
 * @param[in] - idx  - pointer to index
 * @param[in] - key  - key of entry
 * @param[in] - data - data of entry
 *
 * @return int
 * @retval PBS_IDX_ERR_OK   - success
 * @retval PBS_IDX_ERR_FAIL - failure
 *
 */
int
pbs_idx_insert(void *idx, void *key, void *data)
{
	AVL_IX_REC *pkey;

	if (idx == NULL || key == NULL)
		return PBS_IDX_ERR_FAIL;

	pkey = avlkey_create(idx, key);
	if (pkey == NULL)
		return PBS_IDX_ERR_FAIL;

	pkey->recptr = data;
	if (avl_add_key(pkey, idx) != AVL_IX_OK) {
		free(pkey);
		return PBS_IDX_ERR_FAIL;
	}
	free(pkey);
	return PBS_IDX_ERR_OK;
}

/**
 * @brief
 *	delete entry from index
 *
 * @param[in] - idx - pointer to index
 * @param[in] - key - key of entry
 *
 * @return int
 * @retval PBS_IDX_ERR_OK   - success
 * @retval PBS_IDX_ERR_FAIL - failure
 *
 */
int
pbs_idx_delete(void *idx, void *key)
{
	AVL_IX_REC *pkey;

	if (idx == NULL || key == NULL)
		return PBS_IDX_ERR_FAIL;

	pkey = avlkey_create(idx, key);
	if (pkey == NULL)
		return PBS_IDX_ERR_FAIL;

	pkey->recptr = NULL;
	avl_delete_key(pkey, idx);
	free(pkey);
	return PBS_IDX_ERR_OK;
}

/**
 * @brief
 *	delete exact entry from index using given context
 *
 * @param[in] - ctx - pointer to context used while
 *                    deleting exact entry in index
 *
 * @return int
 * @retval PBS_IDX_ERR_OK   - success
 * @retval PBS_IDX_ERR_FAIL - failure
 *
 */
int
pbs_idx_delete_byctx(void *ctx)
{
	iter_ctx *pctx = (iter_ctx *) ctx;

	if (pctx == NULL || pctx->idx == NULL || pctx->pkey == NULL)
		return PBS_IDX_ERR_FAIL;

	avl_delete_key(pctx->pkey, pctx->idx);
	return PBS_IDX_ERR_OK;
}

/**
 * @brief
 *	find entry in index
 *	and optinally set context for iteration on index
 *
 * @param[in]     - idx  - pointer to index
 * @param[in]     - key  - key of entry for finding entry in index
 * @param[in/out] - data - data of entry
 * @param[in/out] - ctx  - context to be set for iteration
 *                         can be NULL, if caller doesn't want
 *                         iteration context back
 *
 * @return int
 * @retval PBS_IDX_ERR_OK   - success
 * @retval PBS_IDX_ERR_FAIL - failure
 *
 * @note
 * 	ctx should be free'd after use, using pbs_idx_free_ctx()
 *
 */
int
pbs_idx_find(void *idx, void *key, void **data, void **ctx)
{
	AVL_IX_REC *pkey;
	int rc = AVL_IX_FAIL;

	if (idx == NULL || key == NULL || data == NULL)
		return PBS_IDX_ERR_FAIL;

	if (ctx != NULL)
		*ctx = NULL;

	*data = NULL;

	pkey = avlkey_create(idx, key);
	if (pkey == NULL)
		return PBS_IDX_ERR_FAIL;

	rc = avl_find_key(pkey, idx);
	if (rc == AVL_IX_OK) {
		*data = pkey->recptr;
		if (ctx != NULL) {
			iter_ctx *pctx = (iter_ctx *) malloc(sizeof(iter_ctx));
			if (pctx == NULL) {
				free(pkey);
				return PBS_IDX_ERR_FAIL;
			}
			pctx->idx = idx;
			pctx->pkey = pkey;
			*ctx = (void *) pctx;

			return PBS_IDX_ERR_OK;
		}
	}

	free(pkey);
	return rc == AVL_IX_OK ? PBS_IDX_ERR_OK : PBS_IDX_ERR_FAIL;
}

/**
 * @brief
 *	get first entry in index
 *	and optinally set context for iteration on index
 *
 * @param[in]     - idx  - pointer to index
 * @param[in/out] - ctx  - context to be set for iteration
 * @param[in/out] - data - data of first entry
 * @param[in/out] - key  - key of first entry, can be NULL, if
 *                         caller doesn't want access to key
 *
 * @return int
 * @retval PBS_IDX_ERR_OK   - success
 * @retval PBS_IDX_ERR_FAIL - failure
 *
 * @note
 * 	ctx should be free'd after use, using pbs_idx_free_ctx()
 *
 */
int
pbs_idx_first(void *idx, void **ctx, void **data, void **key)
{
	iter_ctx *pctx;

	if (idx == NULL || ctx == NULL || data == NULL)
		return PBS_IDX_ERR_FAIL;

	*ctx = NULL;
	*data = NULL;
	if (key)
		*key = NULL;

	pctx = (iter_ctx *) malloc(sizeof(iter_ctx));
	if (pctx == NULL)
		return PBS_IDX_ERR_FAIL;
	pctx->idx = idx;
	pctx->pkey = avlkey_create(idx, NULL);
	if (pctx->pkey == NULL) {
		free(pctx);
		return PBS_IDX_ERR_FAIL;
	}

	avl_first_key(pctx->idx);
	if (avl_next_key(pctx->pkey, pctx->idx) != AVL_IX_OK) {
		free(pctx->pkey);
		free(pctx);
		return PBS_IDX_ERR_FAIL;
	}

	*ctx = pctx;
	*data = pctx->pkey->recptr;
	if (key)
		*key = &pctx->pkey->key;
	return PBS_IDX_ERR_OK;
}

/**
 * @brief
 *	get next entry in index based on given context
 *
 * @param[in]     - ctx  - pointer to context for iteration
 * @param[in/out] - data - data of next entry
 * @param[in/out] - key  - key of next entry, can be NULL, if
 *                         caller doesn't want access to key
 *
 * @return int
 * @retval PBS_IDX_ERR_OK   - success
 * @retval PBS_IDX_ERR_FAIL - failure
 *
 */
int
pbs_idx_next(void *ctx, void **data, void **key)
{
	iter_ctx *pctx = (iter_ctx *) ctx;

	if (data == NULL || pctx == NULL || pctx->idx == NULL || pctx->pkey == NULL)
		return PBS_IDX_ERR_FAIL;

	*data = NULL;
	if (key)
		*key = NULL;

	if (avl_next_key(pctx->pkey, pctx->idx) != AVL_IX_OK)
		return PBS_IDX_ERR_FAIL;
	*data = pctx->pkey->recptr;
	if (key)
		*key = &pctx->pkey->key;
	return PBS_IDX_ERR_OK;
}

/**
 * @brief
 *	free given iteration context
 *
 * @param[in] - ctx - pointer to context for iteration
 *
 * @return void
 *
 */
void
pbs_idx_free_ctx(void *ctx)
{
	if (ctx != NULL) {
		iter_ctx *pctx = (iter_ctx *) ctx;
		free(pctx->pkey);
		free(ctx);
		ctx = NULL;
	}
}
