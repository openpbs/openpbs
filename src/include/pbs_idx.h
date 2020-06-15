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

#ifndef _PBS_IDX_H
#define _PBS_IDX_H
#ifdef __cplusplus
extern "C" {
#endif

#define PBS_IDX_DUPS_NOT_OK 0 /* duplicate key not allowed in index */
#define PBS_IDX_DUPS_OK     1 /* duplicate key allowed in index */

#define PBS_IDX_ERR_OK    0 /* index op succeed */
#define PBS_IDX_ERR_FAIL -1 /* index op failed */

extern void *pbs_idx_get_tls(void);
extern void *pbs_idx_create(int dups, int keylen);
extern void pbs_idx_destroy(void *idx);
extern int pbs_idx_insert(void *idx, void *key, void *data);
extern int pbs_idx_delete(void *idx, void *key);
extern int pbs_idx_delete_byctx(void *ctx);
extern int pbs_idx_find(void *idx, void *key, void **data, void **ctx);
extern int pbs_idx_first(void *idx, void **ctx, void **data, void **key);
extern int pbs_idx_next(void *ctx, void **data, void **key);
extern void pbs_idx_free_ctx(void *ctx);

#ifdef __cplusplus
}
#endif
#endif /* _PBS_IDX_H */
