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
#ifndef	_GRUNT_H
#define	_GRUNT_H
#ifdef	__cplusplus
extern "C" {
#endif
/* structure used by grunt syntax parser located in libpbs.h */
typedef struct key_value_pair {
	char *kv_keyw;
	char *kv_val;
} key_value_pair;

#define KVP_SIZE 50
#define MPIPROCS   "mpiprocs"
#define OMPTHREADS "ompthreads"

extern struct resc_sum *svr_resc_sum;
#ifdef NAS /* localmod 082 */
extern int parse_chunk(char *str, int extra, int *nchk, int *nl, struct key_value_pair **kv, int *dflt);
extern int parse_chunk_r(char *str, int extra, int *nchk, int *pnelem, int *nkve, struct key_value_pair **pkv, int *dflt);
#else
extern int parse_chunk(char *str, int *nchk, int *nl, struct key_value_pair **kv, int *dflt);
extern int parse_chunk_r(char *str, int *nchk, int *pnelem, int *nkve, struct key_value_pair **pkv, int *dflt);
#endif /* localmod 082 */
extern int parse_node_resc(char *str, char **nodep, int *nl, struct key_value_pair **kv);
extern int parse_node_resc_r(char *str, char **nodep, int *pnelem, int *nlkv, struct key_value_pair **kv);
extern char *parse_plus_spec(char *selstr, int *rc);
extern char *parse_plus_spec_r(char *selstr, char **last, int *hp);

#ifdef	__cplusplus
}
#endif
#endif  /* _GRUNT_H */
