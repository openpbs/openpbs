/*
 *	The  first  version  of  this  code  was written in Algol 68 by Gregory
 *	Tseytin  (tseyting@acm.org)  who  later  translated  it  to   C.    The
 *	AVL_COUNT_DUPS  option  was  added  at  the  suggestion  of  Bill  Ross
 *	(bross@nas.nasa.gov), who also packaged the code for distribution.
 *
 *	Taken from NetBSD avltree-1.1.tar.gz.
 */
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

#ifndef _AVLTREE_H
#define _AVLTREE_H
#ifdef __cplusplus
extern "C" {
#endif

#define AVL_DEFAULTKEYLEN (4 * sizeof(int)) /* size of default key */

typedef void *AVL_RECPOS;

typedef struct {
	AVL_RECPOS recptr;
	unsigned int count;
	char key[AVL_DEFAULTKEYLEN];
	/* actually can be of any length */
} rectype;

typedef rectype AVL_IX_REC;

typedef struct {
	void *root;
	int keylength; /* zero for null-terminated strings */
	int flags;
} AVL_IX_DESC;

/*  return codes  */
#define AVL_IX_OK 1
#define AVL_IX_FAIL 0
#define AVL_EOIX -2

/* default behavior is no-dup-keys and case-sensitive search */
#define AVL_DUP_KEYS_OK 0x01 /* repeated key & rec cause an error message */
#define AVL_CASE_CMP 0x02    /* case insensitive search */

extern void avl_set_maxthreads(int n);
extern void *get_avl_tls(void);
extern void free_avl_tls(void);
extern int avl_create_index(AVL_IX_DESC *pix, int flags, int keylength);
extern void avl_destroy_index(AVL_IX_DESC *pix);
extern int avl_find_key(AVL_IX_REC *pe, AVL_IX_DESC *pix);
extern int avl_add_key(AVL_IX_REC *pe, AVL_IX_DESC *pix);
extern int avl_delete_key(AVL_IX_REC *pe, AVL_IX_DESC *pix);
extern void avl_first_key(AVL_IX_DESC *pix);
extern int avl_next_key(AVL_IX_REC *pe, AVL_IX_DESC *pix);

/* Added by Altair */
AVL_IX_REC *avlkey_create(AVL_IX_DESC *tree, void *key);

#ifdef __cplusplus
}
#endif
#endif /* _AVLTREE_H */
