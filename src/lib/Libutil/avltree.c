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
 **    OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE DISCLAIMED.
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
/**
 * @file	avltree.c
 */
#include "avltree.h"

#include <stdlib.h>
#include <stddef.h>
#include <stdio.h>
#include <string.h>
#include <limits.h>
#include <pthread.h>


/*
 **	'inner' avl stuff
 */
/* way3.h */

typedef char	way3; /* -1, 0, 1 */

#define way3stop  ((way3)0)
#define way3left ((way3)-1)
#define way3right ((way3)1)

#define way3sum(x, y) ((x)+(y))
/* assume x!=y */

#define way3opp(x) (-(x))


/* node.h */

typedef struct _node {
	struct _node 	*ptr[2]; /* left, right */
	way3 		balance, trace;
	rectype 	data;
} node;

#define stepway(n, x) (((n)->ptr)[way3ix(x)])
#define stepopp(n, x) (((n)->ptr)[way3ix(way3opp(x))])

/* tree.h */

#define SRF_FINDEQUAL 1
#define SRF_FINDLESS  2
#define SRF_FINDGREAT 4
#define SRF_SETMARK   8
#define SRF_FROMMARK 16

#define avltree_init(x) (*(x)=NULL)

typedef struct {
	int __ix_keylength;
	int __ix_dupkeys;	/* set from AVL_IX_DESC */
	int __rec_keylength;		/* set from actual key */
	int __node_overhead;

	node **__t;
	node *__r;
	node *__s;
	way3 __wayhand;
} avl_tls_t;

static pthread_once_t avl_init_once = PTHREAD_ONCE_INIT;
static pthread_key_t avl_tls_key;

#define MAX_AVLKEY_LEN 100

/**
 * @brief
 *	initializes avl tls by creating a key.
 *
 */
void
avl_init_tls(void)
{
	if (pthread_key_create(&avl_tls_key, NULL) != 0) {
		fprintf(stderr, "avl tls key creation failed\n");
		exit(1);
	}
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

	pthread_once(&avl_init_once, avl_init_tls);

	if ((p_avl_tls = (avl_tls_t *) pthread_getspecific(avl_tls_key)) == NULL) {
		p_avl_tls = (avl_tls_t *) calloc(1, sizeof(avl_tls_t));
		if (!p_avl_tls) {
			fprintf(stderr, "Out of memory creating avl_tls\n");
			exit(1);
		}
		p_avl_tls->__node_overhead = sizeof(node)-AVL_DEFAULTKEYLEN;
		pthread_setspecific(avl_tls_key, (void *) p_avl_tls);
	}
	return p_avl_tls;
}

#define ix_keylength     (((avl_tls_t *) get_avl_tls())->__ix_keylength)
#define ix_dupkeys 	     (((avl_tls_t *) get_avl_tls())->__ix_dupkeys)
#define rec_keylength 	 (((avl_tls_t *) get_avl_tls())->__rec_keylength)
#define node_overhead 	 (((avl_tls_t *) get_avl_tls())->__node_overhead)

#define avl_t 	         (((avl_tls_t *) get_avl_tls())->__t)
#define avl_r            (((avl_tls_t *) get_avl_tls())->__r)
#define avl_s 	 		 (((avl_tls_t *) get_avl_tls())->__s)
#define avl_wayhand 	 (((avl_tls_t *) get_avl_tls())->__wayhand)

/*
avl_tls_t avl;
#define ix_keylength     (avl.__ix_keylength)
#define ix_dupkeys 	     (avl.__ix_dupkeys)
#define rec_keylength 	 (avl.__rec_keylength)
#define node_overhead 	 (avl.__node_overhead)

#define avl_t 	         (avl.__t)
#define avl_r            (avl.__r)
#define avl_s 	 		 (avl.__s)
#define avl_wayhand 	 (avl.__wayhand)
*/


/******************************************************************************
 WAY3
 ******************************************************************************/
static way3
makeway3(int n)
{
	return n>0 ? way3right : n<0 ? way3left : way3stop;
}

static way3
way3opp2(way3 x, way3 y)
{
	return x==y ? way3opp(x) : way3stop;
}

#if	0
static way3
way3random()
{
	return rand()>rand() ? way3left : way3right;
}
#endif


/*****************************************************************************/

/**
 * @brief
 *	frees node n of type (node*).
 */
static void
freenode(node *n)
{
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
	int n= ix_keylength ?
		memcmp(r1->key, r2->key, ix_keylength) :
		strcmp(r1->key, r2->key);
	if (n  ||  ix_dupkeys == AVL_NO_DUP_KEYS)
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
 *	check for duplicate records.
 *
 */
static void
duprec(rectype *r)
{
	if (r->count++==UINT_MAX) {
		fprintf(stderr, "avltrees: repeat count exceeded\n");
		exit(1);
	}
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
	int size=(ix_keylength ? ix_keylength : rec_keylength);
	node *n=(node *)malloc(size+node_overhead);
	if (n==NULL) {
		fprintf(stderr, "avltrees: out of memory\n");
		exit(1);
	}
	if (ix_dupkeys != AVL_NO_DUP_KEYS)
		n->data.count=1;
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
	node *old=*ptrptr;
	*ptrptr=new;
	return old;
}

static int
way3ix(way3 x) /* assume x!=0 */
{
	return x==way3right ? 1 : 0;
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
	way3 n=avl_r->balance, c;
	node *p;
	bool g= n==way3stop ? op_del : n==avl_wayhand;
	if (g) p=avl_r;
	else {
		p=stepopp(avl_r, avl_wayhand);
		stepopp(avl_r, avl_wayhand)=swapptr(&stepway(p, avl_wayhand), avl_r);
		c=p->balance;
		avl_s->balance= way3opp2(c, avl_wayhand);
		avl_r->balance= way3opp2(c, way3opp(avl_wayhand));
		p->balance= way3stop;
	}
	stepway(avl_s, avl_wayhand)=swapptr(&stepopp(p, avl_wayhand), avl_s);
	*avl_t=p;
#ifdef TESTING
	if (op_del) {
		if (g)
			rstd1++;
		else
			rstd2++;
	} else {
		if (g)
			rsti1++;
		else
			rsti2++;
	}
#endif
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
	node	*p, *q, *pp;
	way3	aa, waydir, wayopp;

	if (!(~searchflags & (SRF_FINDGREAT|SRF_FINDLESS)))
		return NULL;
	if (!(searchflags & (SRF_FINDGREAT|SRF_FINDEQUAL|SRF_FINDLESS)))
		return NULL;
	waydir=searchflags & SRF_FINDGREAT ? way3right :
		searchflags & SRF_FINDLESS ? way3left : way3stop;
	wayopp=way3opp(waydir);
	p=q=NULL;
	while ((pp=*tt)!=NULL) {
		aa= searchflags & SRF_FROMMARK ? pp->trace :
			makeway3(compkey(key, &(pp->data)));
		if (searchflags & SRF_SETMARK)
			pp->trace=aa;
		if (aa==way3stop) {
			if (searchflags & SRF_FINDEQUAL)
				return &(pp->data);
			if ((q=stepway(pp, waydir))==NULL)
				break;
			if (searchflags & SRF_SETMARK)
				pp->trace=waydir;
			while (1) {
				if ((pp=stepway(q, wayopp))==NULL) {
					if (searchflags & SRF_SETMARK)
						q->trace=way3stop;
					return &(q->data);
				}
				if (searchflags & SRF_SETMARK)
					q->trace=wayopp;
				q=pp;
			}
		}
		/* remember the point where we can change direction to waydir */
		if (aa==wayopp)
			p=pp;
		tt=&stepway(pp, aa);
	}
	if (p==NULL || !(searchflags & (SRF_FINDLESS|SRF_FINDGREAT)))
		return NULL;
	if (searchflags & SRF_SETMARK)
		p->trace=way3stop;
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
	while ((pp=*tt)!=NULL) {
		pp->trace=way3left;
		tt=&stepway(pp, way3left);
	}
}

/**
 * @brief
 *      return the address of last node.
 *
 * @param[out] tt - pointer to root node of tree.
 *
 * @erturn      Void
 */

static void
avltree_last(node **tt)
{
	node *pp;
	while ((pp=*tt)!=NULL) {
		pp->trace=way3right;
		tt=&stepway(pp, way3right);
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

	avl_t=tt;
	p=*tt;
	while ((pp=*tt)!=NULL) {
		aa= makeway3(compkey(key, &(pp->data)));
		if (aa==way3stop) {
			if (ix_dupkeys == AVL_COUNT_DUPS)
				duprec(&(pp->data));
			return NULL;
		}
		if (pp->balance!=way3stop)
			avl_t=tt; /* t-> the last disbalanced node */
		pp->trace=aa;
		tt=&stepway(pp, aa);
	}
	*tt=q=allocnode();
	q->balance=q->trace=way3stop;
	stepway(q, way3left)=stepway(q, way3right)=NULL;
	key->count = 1;
	copydata(&(q->data), key);
	/* balancing */
	avl_s=*avl_t; avl_wayhand=avl_s->trace;
	if (avl_wayhand!=way3stop) {
		avl_r=stepway(avl_s, avl_wayhand);
		for (p=avl_r; p!=NULL; p=stepway(p, b))
			b=p->balance=p->trace;
		b=avl_s->balance;
		if (b!=avl_wayhand) avl_s->balance=way3sum(avl_wayhand, b);
		else if (restruct(0)) avl_s->balance=avl_r->balance=way3stop;
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
	node **t1, **tt1, **qq1, **rr=tt;

	avl_t=t1=tt1=qq1=tt;
	p=*tt; q=NULL;
	aaa=way3stop;

	while ((pp=*tt)!=NULL) {
		aa= aaa!=way3stop ? aaa :
			searchflags & SRF_FROMMARK ? pp->trace :
		makeway3(compkey(key, &(pp->data)));
		b=pp->balance;
		if (aa==way3stop) {
			qq1=tt; q=pp; rr=t1;
			aa= b!=way3stop ? b : way3left;
			aaa=way3opp(aa); /* will move opposite to aa */
		}
		avl_t=t1;
		if (b==way3stop || (b!=aa && stepopp(pp, aa)->balance==way3stop))
			t1=tt;
		tt1=tt;
		tt=&stepway(pp, aa);
		pp->trace=aa;
	}
	if (aaa==way3stop)
		return NULL;
	copydata(key, &(q->data));
	p=*tt1;
	*tt1=p1=stepopp(p, p->trace);
	if (p!=q) {
		*qq1=p; memcpy(p->ptr, q->ptr, sizeof(p->ptr));
		p->balance=q->balance;
		avl_wayhand=p->trace=q->trace;
		if (avl_t==&stepway(q, avl_wayhand)) avl_t=&stepway(p, avl_wayhand);
	}
	while ((avl_s=*avl_t)!=p1) {
		avl_wayhand=way3opp(avl_s->trace);
		b=avl_s->balance;
		if (b!=avl_wayhand) {
			avl_s->balance=way3sum(avl_wayhand, b);
		} else {
			avl_r=stepway(avl_s, avl_wayhand);
			if (restruct(1)) {
				if ((bb=avl_r->balance)!=way3stop)
					avl_s->balance=way3stop;
				avl_r->balance=way3sum(way3opp(avl_wayhand), bb);
			}
		}
		avl_t=&stepopp(avl_s, avl_wayhand);
	}
	while ((p=*rr)!=NULL) {
		/* adjusting trace */
		aa= makeway3(compkey(&(q->data), &(p->data)));
		p->trace=aa; rr=&stepway(p, aa);
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
	long nodecount=0L;
	node *p=*tt, *q=NULL, *x, **xx;

	if (p != NULL) {
		while (1) {
			if ((x=stepway(p, way3left))!=NULL ||
				(x=stepway(p, way3right))!=NULL) {
				stepway(p, way3left)=q;
				q=p; p=x; continue;
			}
			freenode(p); nodecount++;
			if (q==NULL) break;
			if (*(xx=&stepway(q, way3right))==p) *xx=NULL;
			p=q; q=*(xx=&stepway(p, way3left)); *xx=NULL;
		}
		*tt=NULL;
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
 * @param[in] dup - value indicating whether to allow dup records.
 * @param[in] keylength - key length
 *
 * @return	Void
 *
 */
void
avl_create_index(AVL_IX_DESC *pix, int dup, int keylength)
{
	if (dup != AVL_NO_DUP_KEYS  &&
		dup != AVL_DUP_KEYS_OK  &&
		dup != AVL_COUNT_DUPS) {
		fprintf(stderr,
			"create_index 'dup'=%d: programming error\n", dup);
		exit(1);
	}
	if (keylength < 0) {
		fprintf(stderr,
			"create_index 'keylength'=%d: programming error\n",
			keylength);
		exit(1);
	}
	pix->root = NULL;
	pix->keylength = keylength;
	pix->dup_keys=dup;

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
	ix_keylength = pix->keylength;
	avltree_clear((node **)&(pix->root));
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

	ix_keylength=pix->keylength; ix_dupkeys=pix->dup_keys;

	memset((void *)&(pe->recptr), 0, sizeof(AVL_RECPOS));
	ptr=avltree_search((node **)&(pix->root), pe,
		SRF_FINDEQUAL|SRF_SETMARK|SRF_FINDGREAT);
	if (ptr == NULL)
		return AVL_IX_FAIL;

	pe->recptr=ptr->recptr;
	pe->count = ptr->count;
	if (compkey(pe, ptr))
		return AVL_IX_FAIL;
	return AVL_IX_OK;
}
/**
 * @brief
 *	search the avl tree for given record .
 *
 * @param[in] pe - record to be searched
 * @param[in] pix - pointer to root node of tree
 *
 * @retval      AVL_IX_OK(1)    success
 * @retval      AVL_IX_FAIL(0)  error
 * @retval	AVL_EOIX(-2)	error
 *
 */
int
avl_locate_key(AVL_IX_REC *pe, AVL_IX_DESC *pix)
{
	rectype	*ptr;
	int	ret;

	ix_keylength=pix->keylength; ix_dupkeys=pix->dup_keys;
	memset((void *)&(pe->recptr), 0, sizeof(AVL_RECPOS));
	ptr=avltree_search((node **)&(pix->root), pe,
		SRF_FINDEQUAL|SRF_SETMARK|SRF_FINDGREAT);
	if (ptr==NULL)
		return AVL_EOIX;
	ret= compkey(pe, ptr) ? AVL_IX_FAIL : AVL_IX_OK;
	copydata(pe, ptr);
	return ret;
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
	ix_keylength=pix->keylength; ix_dupkeys=pix->dup_keys;
	if (ix_keylength == 0)
		rec_keylength = strlen(pe->key) + 1;
	if (avltree_insert((node **)&(pix->root), pe)==NULL  &&
		ix_dupkeys != AVL_COUNT_DUPS)
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

	ix_keylength=pix->keylength; ix_dupkeys=pix->dup_keys;

	ptr=avltree_search((node **)&(pix->root), pe, SRF_FINDEQUAL|SRF_SETMARK);
	if (ptr==NULL)
		return AVL_IX_FAIL;
	if (ix_dupkeys==AVL_COUNT_DUPS && --pe->count)
		return AVL_IX_OK;
	avltree_delete((node **)&(pix->root), pe, SRF_FROMMARK);
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
	avltree_first((node **)&(pix->root));
}

/**
 * @brief
 *	return the last record in tree.
 *
 * @param[out] pix - pointer to root node of tree
 *
 * @return 	Void
 */
void
avl_last_key(AVL_IX_DESC *pix)
{
	avltree_last((node **)&(pix->root));
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
	ix_keylength=pix->keylength; ix_dupkeys=pix->dup_keys;
	if ((ptr=avltree_search((node **)&(pix->root), pe, /* pe not used */
		SRF_FROMMARK|SRF_SETMARK|SRF_FINDGREAT))==NULL)
		return AVL_EOIX;
	copydata(pe, ptr);
	return AVL_IX_OK;
}

/**
 * @brief
 *	copies and returns  the previous node index.
 *
 * @param[out] pe - place to hold copied node data
 * @param[in] pix - pointer to root node of tree
 *
 * @return	int
 * @retval	AVL_EOIX(-2)	error
 * @retval	AVL_IX_OK(1)	success
 *
 */
int
avl_prev_key(AVL_IX_REC *pe, AVL_IX_DESC *pix)
{
	rectype *ptr;
	ix_keylength=pix->keylength; ix_dupkeys=pix->dup_keys;
	if ((ptr=avltree_search((node **)&(pix->root), pe, /* pe not used */
		SRF_FROMMARK|SRF_SETMARK|SRF_FINDLESS))==NULL)
		return AVL_EOIX;
	copydata(pe, ptr);
	return AVL_IX_OK;
}

/**
 * @brief
 *	find exact record in the tree by searching.
 *
 * @param[in] pe - key value
 * @param[in] pix - root node
 *
 * @return	int
 * @retval	AVL_IX_OK(1)	success
 * @retval	AVL_IX_FAIL(0)	error
 */
int
avl_find_exact(AVL_IX_REC *pe, AVL_IX_DESC *pix)
{
	rectype *ptr;
	ix_keylength=pix->keylength; ix_dupkeys=pix->dup_keys;
	ptr=avltree_search((node **)&(pix->root), pe,
		SRF_FINDEQUAL|SRF_FINDGREAT|SRF_SETMARK);
	if (ptr==NULL)
		return AVL_IX_FAIL;
	if (ix_dupkeys != AVL_NO_DUP_KEYS  &&  pe->recptr!=ptr->recptr)
		return AVL_IX_FAIL;
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
		if (key == NULL ) {
			keylen = sizeof(AVL_IX_REC) + MAX_AVLKEY_LEN + 1;
		} else {
			keylen = sizeof(AVL_IX_REC) + strlen(key) + 1;
		}
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

/**
 * @brief
 *	Create an empty AVL tree
 *
 * @param[in] - dups - Whether duplicates are allowed or not
 *
 * @return	The AVL trees root
 * @retval	NULL - Failure (out of memory)
 * @retval	!NULL - Success - The AVL tree root
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
AVL_IX_DESC *
create_tree(int dups, int keylen)
{
	AVL_IX_DESC *AVL_p = NULL;

	AVL_p = (AVL_IX_DESC *) malloc(sizeof(AVL_IX_DESC));
	if (AVL_p == NULL)
		return NULL;

	avl_create_index(AVL_p, dups, keylen);
	return AVL_p;
}

/**
 * @brief
 *	Find a node from the AVL tree based on the supplied key
 *
 * @param[in] - root   - The root of the AVL tree to search
 * @param[in] - key - String to be used as the key
 *
 * @return	The data part of the node if found
 * @retval	NULL - Failure (no node found matching key)
 * @retval	!NULL - Success - The record pointer (data) from the node
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void *
find_tree(AVL_IX_DESC *root, void *key)
{
	AVL_IX_REC *pkey;
	void *p = NULL;

	pkey = (AVL_IX_REC *) avlkey_create(root, key);
	if (pkey == NULL)
		return NULL;

	/* find leaf in the leaf tree */
	if (avl_find_key(pkey, root) == AVL_IX_OK)
		p = pkey->recptr;

	free(pkey);
	return p;
}

/**
 * @brief
 *	Add or delete a key (and record) to a AVL tree
 *
 * @param[in] - root   - Root ptr identifying the AVL tree
 * @param[in] - key - String to be used as the key
 * @param[in] - data   - Data to add to the record (not required for delete)
 * @param[in] - op     - Operation to be performed
 *		 0 - TREE_OP_ADD
 *		 1 - TREE_OP_DEL
 *
 * @return	Error code
 * @retval	-1    - Failure
 * @retval	 0    - Success
 * @retval	 1    - Not found (in case of delete)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
tree_add_del(AVL_IX_DESC *root, void *key, void *data, int op)
{
	AVL_IX_REC *pkey;
	int rc = 0;

	pkey = (AVL_IX_REC *) avlkey_create(root, key);
	if (pkey == NULL) {
		return -1;
	}

	pkey->recptr = data;
	if (op == TREE_OP_ADD) {
		rc = avl_add_key((AVL_IX_REC *) pkey, (AVL_IX_DESC *) root);
		if (rc != AVL_IX_OK)
			rc = -1;
		else
			rc = 0;
	} else {
		rc = avl_delete_key(pkey, root);
		if (rc != AVL_IX_OK)
			rc = 1;
		else
			rc = 0;
	}
	free(pkey);
	return rc;
}
