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

#ifndef _PBS_IDX_H
#define _PBS_IDX_H
#ifdef __cplusplus
extern "C" {
#endif

#include <stdbool.h>

#define PBS_IDX_DUPS_OK     0x01 /* duplicate key allowed in index */
#define PBS_IDX_ICASE_CMP   0x02 /* set case-insensitive compare */

#define PBS_IDX_RET_OK    0 /* index op succeed */
#define PBS_IDX_RET_FAIL -1 /* index op failed */

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
extern void *pbs_idx_create(int dups, int keylen);

/**
 * @brief
 *	destroy index
 *
 * @param[in] - idx - pointer to index
 *
 * @return void
 *
 */
extern void pbs_idx_destroy(void *idx);

/**
 * @brief
 *	add entry in index
 *
 * @param[in] - idx  - pointer to index
 * @param[in] - key  - key of entry
 * @param[in] - data - data of entry
 *
 * @return int
 * @retval PBS_IDX_RET_OK   - success
 * @retval PBS_IDX_RET_FAIL - failure
 *
 */
extern int pbs_idx_insert(void *idx, void *key, void *data);

/**
 * @brief
 *	delete entry from index
 *
 * @param[in] - idx - pointer to index
 * @param[in] - key - key of entry
 *
 * @return int
 * @retval PBS_IDX_RET_OK   - success
 * @retval PBS_IDX_RET_FAIL - failure
 *
 */
extern int pbs_idx_delete(void *idx, void *key);

/**
 * @brief
 *	delete exact entry from index using given context
 *
 * @param[in] - ctx - pointer to context used while
 *                    deleting exact entry in index
 *
 * @return int
 * @retval PBS_IDX_RET_OK   - success
 * @retval PBS_IDX_RET_FAIL - failure
 *
 */
extern int pbs_idx_delete_byctx(void *ctx);

/**
 * @brief
 *	find or iterate entry in index
 *
 * @param[in]     - idx  - pointer to index
 * @param[in/out] - key  - key of the entry
 *                         if *key is NULL then this routine will
 *                         return the first entry in index
 * @param[in/out] - data - data of the entry
 * @param[in/out] - ctx  - context to be set for iteration
 *                         can be NULL, if caller doesn't want
 *                         iteration context
 *                         if *ctx is not NULL, then this routine
 *                         will return next entry in index
 *
 * @return int
 * @retval PBS_IDX_RET_OK   - success
 * @retval PBS_IDX_RET_FAIL - failure
 *
 * @note
 * 	ctx should be free'd after use, using pbs_idx_free_ctx()
 *
 */
extern int pbs_idx_find(void *idx, void **key, void **data, void **ctx);

/**
 * @brief
 *	free given iteration context
 *
 * @param[in] - ctx - pointer to context for iteration
 *
 * @return void
 *
 */
extern void pbs_idx_free_ctx(void *ctx);

/**
 * @brief check whether idx is empty and has no key associated with it
 * 
 * @param[in] idx - pointer to avl index
 * 
 * @return int
 * @retval 1 - idx is empty
 * @retval 0 - idx is not empty
 */
extern bool pbs_idx_is_empty(void *idx);

#ifdef __cplusplus
}
#endif
#endif /* _PBS_IDX_H */
