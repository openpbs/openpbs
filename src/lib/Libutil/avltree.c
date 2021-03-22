/*
 **  avltree - AVL index routines by Gregory Tseytin.
 **
 **
 **    Copyright (c) 2000 Gregory Tseytin <tseyting@acm.org>
 **      All rights reserved.
 **
 **    Redistribution and use in source and binary forms, with or without
 **    modification, are permitted provided that the following conditions
 **    are met:
 **    1. Redistributions of source code must retain the above copyright
 **       notice, this list of conditions and the following disclaimer as
 **       the first lines of this file unmodified.
 **    2. Redistributions in binary form must reproduce the above copyright
 **       notice, this list of conditions and the following disclaimer in the
 **       documentation and/or other materials provided with the distribution.
 **
 **    THIS SOFTWARE IS PROVIDED BY Gregory Tseytin ``AS IS'' AND ANY EXPRESS OR
 **    IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED WARRANTIES
 **    OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE.
 **    IN NO EVENT SHALL Gregory Tseytin BE LIABLE FOR ANY DIRECT, INDIRECT,
 **    INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES (INCLUDING, BUT
 **    NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES; LOSS OF USE,
 **    DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND ON ANY
 **    THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
 **    (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF
 **    THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
 **
 **
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

#include "avltree.h"
#include <limits.h>
#include <pthread.h>
#include <stddef.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/*
 **	'inner' avl stuff
 */
/* way3.h */

typedef char way3; /* -1, 0, 1 */

#define way3stop  ((way3) 0)
#define way3left  ((way3) -1)
#define way3right ((way3) 1)

#define way3sum(x, y) ((x) + (y)) /* assume x!=y */

#define way3opp(x) (-(x))

/* node.h */

typedef struct _node {
	struct _node *ptr[2]; /* left, right */
	way3 balance, *trace;
	rectype data;
} node;

#define stepway(n, x) (((n)->ptr)[way3ix(x)])
#define stepopp(n, x) (((n)->ptr)[way3ix(way3opp(x))])

/* tree.h */

#define SRF_FINDEQUAL 1
#define SRF_FINDLESS  2
#define SRF_FINDGREAT 4
#define SRF_SETMARK   8
#define SRF_FROMMARK  16

#define avltree_init(x) (*(x) = NULL)

typedef struct {
	short __tind; /* index of this thread */
	int __ix_keylength;
	int __ix_flags;    /* set from AVL_IX_DESC */
	int __rec_keylength; /* set from actual key */
	int __node_overhead;

	node **__t;
	node *__r;
	node *__s;
	way3 __wayhand;
} avl_tls_t;

static pthread_once_t avl_init_once = PTHREAD_ONCE_INIT;
static pthread_key_t avl_tls_key;
pthread_mutex_t tind_lock;

#define MAX_AVLKEY_LEN 100

/**
 * Set max_threads to 2 by default since mom, server etc have basically 2 threads
 * If caller has > 2 threads, e.g. pbs_comm, it must first call avl_set_maxthreads()
 */
static int max_threads = 2; 

/**
 * @brief set the max threads that the application uses, before any calls to avltree
 * 
 */
void 
avl_set_maxthreads(int n)
{
	max_threads = n;
}

/**
 * @brief
 *	initializes avl tls by creating a key.
 *
 */
void
avl_init_func(void)
{
	if (pthread_key_create(&avl_tls_key, NULL) != 0) {
		fprintf(stderr, "avl tls key creation failed\n");
	}

	if (pthread_mutex_init(&tind_lock, NULL) != 0) {
		fprintf(stderr, "avl mutex init failed\n");
		return;
	}
}

/**
 * @brief
 *	return an unique thread index for each new thread
 *
 */
static short
get_thread_index(void)
{
	static short tind = -1;
	short retval;
	
	pthread_mutex_lock(&tind_lock);
	retval = ++tind;
	pthread_mutex_unlock(&tind_lock);
	return retval;
}

/**
 * @brief
 *	retrieves and returns the avl tls by checking key initialization
 *	setting  value in tls and adding the key to list.
 *
 * @return 	structure handle
 * @retval	pointer to avl tree info (tls)
 */
void *
get_avl_tls(void)
{
	avl_tls_t *p_avl_tls = NULL;

	pthread_once(&avl_init_once, avl_init_func);

	if ((p_avl_tls = (avl_tls_t *) pthread_getspecific(avl_tls_key)) == NULL) {
		p_avl_tls = (avl_tls_t *) calloc(1, sizeof(avl_tls_t));
		if (!p_avl_tls) {
			fprintf(stderr, "Out of memory creating avl_tls\n");
			return NULL;
		}
		p_avl_tls->__tind = get_thread_index();
		p_avl_tls->__node_overhead = sizeof(node) - AVL_DEFAULTKEYLEN;
		pthread_setspecific(avl_tls_key, (void *) p_avl_tls);
	}
	return p_avl_tls;
}


/**
 * @brief
 *	Free the thread local storage used for avltree for this thread
 */
void
free_avl_tls(void)
{
	avl_tls_t *p_avl_tls = NULL;

	pthread_once(&avl_init_once, avl_init_func);

	if ((p_avl_tls = (avl_tls_t *) pthread_getspecific(avl_tls_key))) 
		free(p_avl_tls);
}

#define tind             (((avl_tls_t *) get_avl_tls())->__tind)
#define ix_keylength  (((avl_tls_t *) get_avl_tls())->__ix_keylength)
#define ix_flags   (((avl_tls_t *) get_avl_tls())->__ix_flags)
#define rec_keylength (((avl_tls_t *) get_avl_tls())->__rec_keylength)
#define node_overhead (((avl_tls_t *) get_avl_tls())->__node_overhead)
#define avl_t	      (((avl_tls_t *) get_avl_tls())->__t)
#define avl_r	      (((avl_tls_t *) get_avl_tls())->__r)
#define avl_s	      (((avl_tls_t *) get_avl_tls())->__s)
#define avl_wayhand   (((avl_tls_t *) get_avl_tls())->__wayhand)

/******************************************************************************
 WAY3
 ******************************************************************************/
static way3
makeway3(int n)
{
	return n > 0 ? way3right : n < 0 ? way3left : way3stop;
}

static way3
way3opp2(way3 x, way3 y)
{
	return x == y ? way3opp(x) : way3stop;
}

/*****************************************************************************/

/**
 * @brief
 *	frees node n of type (node*).
 */
static void
freenode(node *n)
{
	if (n)
		free(n->trace);
	free(n);
}

/**
 * @brief
 *	compares two records r1 and r2
 *
 * @param[in] r1 - record1
 * @param[in] r2 - record2
 *
 * @return	int
 * @retval	matched string count	success
 * @retval	keylength		if dup keys
 *
 */
static int
compkey(rectype *r1, rectype *r2)
{
	int n;
	if (ix_keylength)
		n = memcmp(r1->key, r2->key, ix_keylength);
	else {
		if (ix_flags & AVL_CASE_CMP)
			n = strcasecmp(r1->key, r2->key);
		else
			n = strcmp(r1->key, r2->key);
	}

	if (n || !(ix_flags & AVL_DUP_KEYS_OK))
		return n;
	return memcmp(&(r1->recptr), &(r2->recptr), sizeof(AVL_RECPOS));
}

/**
 * @brief
 *	copy data of one record  to another
 *
 * @param[in] r1 - key1
 * @param[in] r2 - key2
 *
 * @return	Void
 */
static void
copydata(rectype *r1, rectype *r2)
{
	r1->recptr = r2->recptr;
	r1->count = r2->count;
	if (ix_keylength)
		memcpy(r1->key, r2->key, ix_keylength);
	else
		strcpy(r1->key, r2->key);
}

/**
 * @brief
 *	allocate  memory for new node.
 *
 * @return	structure handle
 * @retval	pointer to node key	success
 * @retval	NULL			error
 */
static node *
allocnode()
{
	int size = (ix_keylength ? ix_keylength : rec_keylength);
	node *n = (node *) malloc(size + node_overhead);
	if (n == NULL) {
		fprintf(stderr, "avltrees: out of memory\n");
		return NULL;
	}
	if (ix_flags & AVL_DUP_KEYS_OK)
		n->data.count = 1;

	n->trace = calloc(max_threads, sizeof(way3));
	if (n->trace == NULL) {
		fprintf(stderr, "avltrees: out of memory\n");
		return NULL;
	}
	return n;
}

/******************************************************************************
 NODE
 ******************************************************************************/
/**
 * @brief
 *	swap the given pointers .
 *
 * @param[in] ptrptr - pointer to pointer to root node
 * @param[in] new - new pointer
 *
 * @return	structure handle
 * @retval	pointer to old node	success
 *
 */
static node *
swapptr(node **ptrptr, node *new)
{
	node *old = *ptrptr;
	*ptrptr = new;
	return old;
}

static int
way3ix(way3 x) /* assume x != 0 */
{
	return x == way3right ? 1 : 0;
}

/******************************************************************************
 TREE
 ******************************************************************************/

typedef int bool;

/**
 * @brief
 *	restructure the tree inorder to maintain balance of tree whenever insertion or deletion of node happens
 *
 * @param[in]	op_del - value indicating insertion(0)/deletion(1) of node
 *
 * @return	int
 * @retval	0	delete node
 * @retval	1	insert node
 *
 */
static bool
restruct(bool op_del)
{
	way3 n = avl_r->balance, c;
	node *p;
	bool g = n == way3stop ? op_del : n == avl_wayhand;
	if (g)
		p = avl_r;
	else {
		p = stepopp(avl_r, avl_wayhand);
		stepopp(avl_r, avl_wayhand) = swapptr(&stepway(p, avl_wayhand), avl_r);
		c = p->balance;
		avl_s->balance = way3opp2(c, avl_wayhand);
		avl_r->balance = way3opp2(c, way3opp(avl_wayhand));
		p->balance = way3stop;
	}
	stepway(avl_s, avl_wayhand) = swapptr(&stepopp(p, avl_wayhand), avl_s);
	*avl_t = p;
	return g;
}

/**
 * @brief
 *	search the avl tree for given record.
 *
 * @param[in] tt - pointer to root of tree
 * @param[in] key - record to be searched
 * @param[in] searchflags- search flag indicating equal,greater
 *
 * @return	structure handle
 * @retval	pointer to the key (found)	success
 * @retval	NULL				error
 *
 */
static rectype *
avltree_search(node **tt, rectype *key, unsigned short searchflags)
{
	node *p, *q, *pp;
	way3 aa, waydir, wayopp;

	if (!(~searchflags & (SRF_FINDGREAT | SRF_FINDLESS)))
		return NULL;
	if (!(searchflags & (SRF_FINDGREAT | SRF_FINDEQUAL | SRF_FINDLESS)))
		return NULL;
	waydir = searchflags & SRF_FINDGREAT ? way3right : searchflags & SRF_FINDLESS ? way3left : way3stop;
	wayopp = way3opp(waydir);
	p = q = NULL;
	while ((pp = *tt) != NULL) {
		aa = searchflags & SRF_FROMMARK ? pp->trace[tind] : makeway3(compkey(key, &(pp->data)));
		if (searchflags & SRF_SETMARK)
			pp->trace[tind] = aa;
		if (aa == way3stop) {
			if (searchflags & SRF_FINDEQUAL)
				return &(pp->data);
			if ((q = stepway(pp, waydir)) == NULL)
				break;
			if (searchflags & SRF_SETMARK)
				pp->trace[tind] = waydir;
			while (1) {
				if ((pp = stepway(q, wayopp)) == NULL) {
					if (searchflags & SRF_SETMARK)
						q->trace[tind] = way3stop;
					return &(q->data);
				}
				if (searchflags & SRF_SETMARK)
					q->trace[tind] = wayopp;
				q = pp;
			}
		}
		/* remember the point where we can change direction to waydir */
		if (aa == wayopp)
			p = pp;
		tt = &stepway(pp, aa);
	}
	if (p == NULL || !(searchflags & (SRF_FINDLESS | SRF_FINDGREAT)))
		return NULL;
	if (searchflags & SRF_SETMARK)
		p->trace[tind] = way3stop;
	return &(p->data);
}

/**
 * @brief
 *	return the address of first node.
 *
 * @param[out] tt - pointer to root node of tree.
 *
 * @erturn	Void
 */
static void
avltree_first(node **tt)
{
	node *pp;
	while ((pp = *tt) != NULL) {
		pp->trace[tind] = way3left;
		tt = &stepway(pp, way3left);
	}
}

/**
 * @brief
 *	insert the given record into the tree pointed by tt.
 *
 * @param[in] tt - address of root
 * @param[in] key - record to be inserted
 *
 * @return	structure handle
 * @retval	pointer to key inserted		success
 * @retval	NULL				error
 *
 */
static rectype *
avltree_insert(node **tt, rectype *key)
{
	way3 aa, b;
	node *p, *q, *pp;

	avl_t = tt;
	p = *tt;
	while ((pp = *tt) != NULL) {
		aa = makeway3(compkey(key, &(pp->data)));
		if (aa == way3stop) {
			return NULL;
		}
		if (pp->balance != way3stop)
			avl_t = tt; /* t-> the last disbalanced node */
		pp->trace[tind] = aa;
		tt = &stepway(pp, aa);
	}
	*tt = q = allocnode();
	q->balance = q->trace[tind] = way3stop;
	stepway(q, way3left) = stepway(q, way3right) = NULL;
	key->count = 1;
	copydata(&(q->data), key);
	/* balancing */
	avl_s = *avl_t;
	avl_wayhand = avl_s->trace[tind];
	if (avl_wayhand != way3stop) {
		avl_r = stepway(avl_s, avl_wayhand);
		for (p = avl_r; p != NULL; p = stepway(p, b))
			b = p->balance = p->trace[tind];
		b = avl_s->balance;
		if (b != avl_wayhand)
			avl_s->balance = way3sum(avl_wayhand, b);
		else if (restruct(0))
			avl_s->balance = avl_r->balance = way3stop;
	}
	return &(q->data);
}

/**
 * @brief
 *      delete the given record  from  the tree.
 *
 * @param[in] tt - address of root node
 * @param[in] key - record to be deleted
 *
 * @return      structure handle
 * @retval      deleted key			success
 * @retval      NULL                            error
 *
 */
static rectype *
avltree_delete(node **tt, rectype *key, unsigned short searchflags)
{
	way3 aa, aaa, b, bb;
	node *p, *q, *pp, *p1;
	node **t1, **tt1, **qq1, **rr = tt;

	avl_t = t1 = tt1 = qq1 = tt;
	p = *tt;
	q = NULL;
	aaa = way3stop;

	while ((pp = *tt) != NULL) {
		aa = aaa != way3stop ? aaa : searchflags & SRF_FROMMARK ? pp->trace[tind] : makeway3(compkey(key, &(pp->data)));
		b = pp->balance;
		if (aa == way3stop) {
			qq1 = tt;
			q = pp;
			rr = t1;
			aa = b != way3stop ? b : way3left;
			aaa = way3opp(aa); /* will move opposite to aa */
		}
		avl_t = t1;
		if (b == way3stop || (b != aa && stepopp(pp, aa)->balance == way3stop))
			t1 = tt;
		tt1 = tt;
		tt = &stepway(pp, aa);
		pp->trace[tind] = aa;
	}
	if (aaa == way3stop)
		return NULL;
	copydata(key, &(q->data));
	p = *tt1;
	*tt1 = p1 = stepopp(p, p->trace[tind]);
	if (p != q) {
		*qq1 = p;
		memcpy(p->ptr, q->ptr, sizeof(p->ptr));
		p->balance = q->balance;
		avl_wayhand = p->trace[tind] = q->trace[tind];
		if (avl_t == &stepway(q, avl_wayhand))
			avl_t = &stepway(p, avl_wayhand);
	}
	while ((avl_s = *avl_t) != p1) {
		avl_wayhand = way3opp(avl_s->trace[tind]);
		b = avl_s->balance;
		if (b != avl_wayhand) {
			avl_s->balance = way3sum(avl_wayhand, b);
		} else {
			avl_r = stepway(avl_s, avl_wayhand);
			if (restruct(1)) {
				if ((bb = avl_r->balance) != way3stop)
					avl_s->balance = way3stop;
				avl_r->balance = way3sum(way3opp(avl_wayhand), bb);
			}
		}
		avl_t = &stepopp(avl_s, avl_wayhand);
	}
	while ((p = *rr) != NULL) {
		/* adjusting trace */
		aa = makeway3(compkey(&(q->data), &(p->data)));
		p->trace[tind] = aa;
		rr = &stepway(p, aa);
	}
	freenode(q);
	return key;
}

/**
 * @brief
 *	clear or free all the nodes
 *
 * @param[in] tt - pointer to root
 *
 * @return	Void
 *
 */
static void
avltree_clear(node **tt)
{
	long nodecount = 0L;
	node *p = *tt, *q = NULL, *x, **xx;

	if (p != NULL) {
		while (1) {
			if ((x = stepway(p, way3left)) != NULL ||
			    (x = stepway(p, way3right)) != NULL) {
				stepway(p, way3left) = q;
				q = p;
				p = x;
				continue;
			}
			freenode(p);
			nodecount++;
			if (q == NULL)
				break;
			if (*(xx = &stepway(q, way3right)) == p)
				*xx = NULL;
			p = q;
			q = *(xx = &stepway(p, way3left));
			*xx = NULL;
		}
		*tt = NULL;
	}
}

/******************************************************************************
 'PLUS' interface style
 ******************************************************************************/

/**
 * @brief
 *	create index for the tree.
 *
 * @param[in] pix - record
 * @param[in] flags - 0x01 - dups allowed, 0x02 - case insensitive search
 * @param[in] keylength - key length
 *
 * @return	error code
 * @retval	1	error
 * @retval	0	success
 *
 */
int
avl_create_index(AVL_IX_DESC *pix, int flags, int keylength)
{
	if (keylength < 0) {
		fprintf(stderr, "create_index 'keylength'=%d: programming error\n", keylength);
		return 1;
	}
	pix->root = NULL;
	pix->keylength = keylength;
	pix->flags = flags;

	return 0;
}

/**
 * @brief
 *	destroy the avl tree pointed by pix.
 *
 * @param[in] pix - pointer to head of tree
 *
 * @return	Void
 */
void
avl_destroy_index(AVL_IX_DESC *pix)
{
	if (!pix)
		return;

	ix_keylength = pix->keylength;
	avltree_clear((node **) &(pix->root));
	pix->root = NULL;
}

/**
 * @brief
 *	finds a record in tree and copy its index.
 *
 * @param[in] pe - key
 * @param[in] pix - pointer to tree
 *
 * @return	int
 * @retval      AVL_IX_OK(1)    success
 * @retval      AVL_IX_FAIL(0)  error
 *
 */
int
avl_find_key(AVL_IX_REC *pe, AVL_IX_DESC *pix)
{
	rectype *ptr;

	ix_keylength = pix->keylength;
	ix_flags = pix->flags;

	memset((void *) &(pe->recptr), 0, sizeof(AVL_RECPOS));
	ptr = avltree_search((node **) &(pix->root), pe,
			     SRF_FINDEQUAL | SRF_SETMARK | SRF_FINDGREAT);
	if (ptr == NULL)
		return AVL_IX_FAIL;

	pe->recptr = ptr->recptr;
	pe->count = ptr->count;
	if (compkey(pe, ptr))
		return AVL_IX_FAIL;
	return AVL_IX_OK;
}

/**
 * @brief
 *	add a key to the tree
 *
 * @param[in] pe - record to be added
 * @param[in] pix - pointer to root of tree
 *
 * @return	int
 * @retval      AVL_IX_OK(1)    success
 * @retval      AVL_IX_FAIL(0)  error
 *
 */
int
avl_add_key(AVL_IX_REC *pe, AVL_IX_DESC *pix)
{
	ix_keylength = pix->keylength;
	ix_flags = pix->flags;
	if (ix_keylength == 0)
		rec_keylength = strlen(pe->key) + 1;
	if (avltree_insert((node **) &(pix->root), pe) == NULL)
		return AVL_IX_FAIL;
	return AVL_IX_OK;
}

/**
 * @brief
 *	delete the given record from the tree
 *
 * @param[in] pe - index of record to be deleted
 * @param[in] pix - pointer to the root of tree
 *
 * @return	int
 * @retval	AVL_IX_OK(1)	success
 * @retval	AVL_IX_FAIL(0)	error
 *
 */
int
avl_delete_key(AVL_IX_REC *pe, AVL_IX_DESC *pix)
{
	rectype *ptr;

	ix_keylength = pix->keylength;
	ix_flags = pix->flags;

	ptr = avltree_search((node **) &(pix->root), pe, SRF_FINDEQUAL | SRF_SETMARK);
	if (ptr == NULL)
		return AVL_IX_FAIL;
	avltree_delete((node **) &(pix->root), pe, SRF_FROMMARK);
	return AVL_IX_OK;
}

/**
 * @brief
 *      return the first record in tree
 *
 * @param[out] pix - pointer to root node of tree.
 *
 * @return      Void
 */
void
avl_first_key(AVL_IX_DESC *pix)
{
	avltree_first((node **) &(pix->root));
}

/**
 * @brief
 *      copies and returns  the next node index.
 *
 * @param[out] pe - place to hold copied node data
 * @param[in] pix - pointer to root of tree
 *
 * @return      int
 * @retval      AVL_EOIX(-2)    error
 * @retval      AVL_IX_OK(1)    success
 *
 */
int
avl_next_key(AVL_IX_REC *pe, AVL_IX_DESC *pix)
{
	rectype *ptr;
	ix_keylength = pix->keylength;
	ix_flags = pix->flags;

	if ((ptr = avltree_search((node **) &(pix->root),
				  pe, /* pe not used */
				  SRF_FROMMARK | SRF_SETMARK | SRF_FINDGREAT)) == NULL)
		return AVL_EOIX;
	copydata(pe, ptr);
	return AVL_IX_OK;
}

/**
 * @brief
 *	Create an AVL key based on the string provided
 *
 * @param[in] - key - String to be used as the key
 *
 * @return	The AVL key
 * @retval	NULL - Failure (out of memory)
 * @retval	!NULL - Success - The AVL key
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
AVL_IX_REC *
avlkey_create(AVL_IX_DESC *tree, void *key)
{
	size_t keylen;
	AVL_IX_REC *pkey;

	if (tree->keylength != 0)
		keylen = sizeof(AVL_IX_REC) - AVL_DEFAULTKEYLEN + tree->keylength;
	else {
		if (key == NULL)
			keylen = sizeof(AVL_IX_REC) + MAX_AVLKEY_LEN + 1;
		else
			keylen = sizeof(AVL_IX_REC) + strlen(key) + 1;
	}
	pkey = calloc(1, keylen);
	if (pkey == NULL)
		return NULL;

	if (key != NULL) {
		if (tree->keylength != 0)
			memcpy(pkey->key, key, tree->keylength);
		else
			strcpy(pkey->key, (char *) key);
	}

	return (pkey);
}
