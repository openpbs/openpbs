/*
 **	'application' avltree stuff
 */

/*
 *	The  first  version  of  this  code  was written in Algol 68 by Gregory
 *	Tseytin  (tseyting@acm.org)  who  later  translated  it  to   C.    The
 *	AVL_COUNT_DUPS  option  was  added  at  the  suggestion  of  Bill  Ross
 *	(bross@nas.nasa.gov), who also packaged the code for distribution.
 *
 *	Taken from NetBSD avltree-1.1.tar.gz.
 */
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
#ifndef _AVLTREE_H
#define _AVLTREE_H
#ifdef  __cplusplus
extern "C" {
#endif

#define AVL_DEFAULTKEYLEN (4 * sizeof(int))	/* size of default key */

typedef void		*AVL_RECPOS;

typedef struct {
	AVL_RECPOS	recptr;
	unsigned int	count;
	char		key[AVL_DEFAULTKEYLEN];
	/* actually can be of any length */
} rectype;

typedef rectype		AVL_IX_REC;


typedef struct {
	void		*root;
	int		keylength; /* zero for null-terminated strings */
	int		dup_keys;
} AVL_IX_DESC;

/*  return codes  */
#define AVL_IX_OK	1
#define AVL_IX_FAIL	0
#define AVL_EOIX	(-2)

/*  'dup' args of avl_create_index()  */
#define AVL_NO_DUP_KEYS	0	/* repeated key causes an error message */
#define AVL_DUP_KEYS_OK	1	/* repeated key & rec cause an error message */
#define AVL_COUNT_DUPS	2	/* complete dups allowed, count repetitions */

extern void *get_avl_tls(void);
extern void	avl_create_index(AVL_IX_DESC *pix, int dup, int keylength);
extern void	avl_destroy_index(AVL_IX_DESC *pix);
extern int	avl_find_key(AVL_IX_REC *pe, AVL_IX_DESC *pix);
extern int	avl_locate_key(AVL_IX_REC *pe, AVL_IX_DESC *pix);
extern int	avl_add_key(AVL_IX_REC *pe, AVL_IX_DESC *pix);
extern int	avl_delete_key(AVL_IX_REC *pe, AVL_IX_DESC *pix);
extern void	avl_first_key(AVL_IX_DESC *pix);
extern void	avl_last_key(AVL_IX_DESC *pix);
extern int	avl_next_key(AVL_IX_REC *pe, AVL_IX_DESC *pix);
extern int	avl_prev_key(AVL_IX_REC *pe, AVL_IX_DESC *pix);
extern int	avl_find_exact(AVL_IX_REC *pe, AVL_IX_DESC *pix);

/* Added by Altair */
int tree_add_del(AVL_IX_DESC *root, void *key, void *data, int op);
void *find_tree(AVL_IX_DESC *root, void *key);
AVL_IX_DESC *create_tree(int dups, int keylen);
AVL_IX_REC *avlkey_create(AVL_IX_DESC *tree, void *key);

/* Operation types for addition/deletion from AVL tree */
#define TREE_OP_ADD	0
#define TREE_OP_DEL	1


#ifdef  __cplusplus
}
#endif
#endif  /* _AVLTREE_H */

