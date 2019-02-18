/*
 * Copyright (C) 1994-2019 Altair Engineering, Inc.
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
 * @file	entlim.c
 * @brief
 * 	entlim functions - This file contains functions to deal will adding to,
 *	finding in, and removing from entities limits from a data structure.
 *
 *	We will attempt to hide the details of the fgc holding structure,
 *	which for this implementation will be an AVL tree.
 *
 * More to come.....
 */

#include <stdlib.h>
#include <string.h>
#include <stdio.h>
#include "avltree.h"
#include "pbs_entlim.h"
#ifdef WIN32
#include <windows.h>
#include <win.h>
#endif


static size_t maxkeylen = 0;
static size_t defkeylen = 0;
/**
 * @brief
 * 	entlim_initialize_ctx - initialize the data context structure
 *	For now it an AVL Tree
 *
 */

void *
entlim_initialize_ctx(void)
{
	AVL_IX_DESC *ctx;
	ctx = (AVL_IX_DESC *)malloc(sizeof(AVL_IX_DESC));
	if (ctx != NULL) {
		avl_create_index(ctx, AVL_NO_DUP_KEYS, 0);
		if (maxkeylen == 0) {
			defkeylen = sizeof(AVL_IX_REC);
			maxkeylen = defkeylen;
		}
	}
	return ((void *)ctx);
}

/**
 * @brief
 * 	entlim_create_key - create a key to hold the key string used for indexing
 *
 * @param[in] keystr - key string
 *
 * @return	pbs_entlim_key_t*
 * @retval	pointer to key info	success
 * @retval	NULL			error
 *
 */

static pbs_entlim_key_t *
entlim_create_key(const char *keystr)
{
	size_t		 keylen;
	pbs_entlim_key_t *pkey;

	if ((keystr != NULL) && (*keystr != '\0')) {
		keylen = defkeylen + strlen(keystr) + 1;
		if (keylen > maxkeylen)
			maxkeylen = keylen;
	} else {
		keylen = maxkeylen;
	}
	pkey = (pbs_entlim_key_t *)malloc(keylen);
	if (pkey == NULL)
		return NULL;
	memset((void *)pkey, 0, keylen);
	if ((keystr != NULL) && (*keystr != '\0'))
		strcpy(pkey->key, keystr);
	return (pkey);
}

/**
 * @brief
 * 	entlim_get - get record whose key is built from the given key-string
 *
 * @param[in] keystr - key string whose key is to be built
 * @param[in] ctx - pointer to avl descending order tree info
 *
 * @return	void text
 * @retval	key		success
 * @retval	NULL		error
 *
 */

void *
entlim_get(const char *keystr, void *ctx)
{
	pbs_entlim_key_t *pkey;
	void	         *rtn;

	pkey =  entlim_create_key(keystr);
	if (pkey == NULL)
		return NULL;
	if (avl_find_key((AVL_IX_REC *)pkey, (AVL_IX_DESC *)ctx) == AVL_IX_OK) {
		rtn = pkey->recptr;
		free(pkey);
		return (rtn);
	} else {
		free(pkey);
		return NULL;
	}
}

/**
 * @brief
 * 	entlim_add - add a record with a key based on the key-string
 *
 * @param[in] keystr - key string whose key is to be built
 * @param[in] recptr - pointer to record
 * @param[in] ctx - pointer to avl descending order tree info
 *
 * @return	int
 * @retval	0	success, record added
 * @retval	-1	add failed
 */
int
entlim_add(const char *keystr, const void *recptr, void *ctx)
{
	pbs_entlim_key_t *pkey;

	pkey = entlim_create_key(keystr);
	if (pkey == NULL)
		return -1;

	pkey->recptr = (AVL_RECPOS)recptr;

	if (avl_add_key((AVL_IX_REC *)pkey, (AVL_IX_DESC *)ctx) == AVL_IX_OK) {
		free(pkey);
		return 0;
	} else {
		return -1;
	}
}

/**
 * @brief
 * 	entlim_replace - replace a record with a key based on the key-string
 *	if the record already exists, if not then this becomes equivalent
 *	to entlim_add().
 *
 * @param[in] keystr - key string whose key is to be built
 * @param[in] recptr - pointer to record
 * @param[in] ctx - pointer to avl descending order tree info
 * @param[in] free_leaf() - function called to delete data record when removing
 *			    exiting record.
 *
 * @return	int
 * @retval	0	success, record replace/added
 * @retval	-1	change failed
 */
int
entlim_replace(const char *keystr, void *recptr, void *ctx,
	void fr_leaf(void *))
{
	pbs_entlim_key_t *pkey;
	int		  rc;

	pkey = entlim_create_key(keystr);
	if (pkey == NULL)
		return -1;
	pkey->recptr = recptr;
	if (avl_add_key((AVL_IX_REC *)pkey, (AVL_IX_DESC *)ctx) == AVL_IX_OK) {
		free(pkey);
		return 0;
	} else {
		/* record with key may already exist, try deleting it */
		rc = avl_find_key((AVL_IX_REC *)pkey, (AVL_IX_DESC *)ctx);
		if (rc == AVL_IX_OK) {
			void *olddata = pkey->recptr;
			rc = avl_delete_key((AVL_IX_REC *)pkey, (AVL_IX_DESC *)ctx);
			if (rc == AVL_IX_OK) {
				fr_leaf(olddata);
				free(pkey);
				pkey = entlim_create_key(keystr);
				if (pkey == NULL)
					return -1;
				pkey->recptr = recptr;
				rc = avl_add_key((AVL_IX_REC *)pkey, (AVL_IX_DESC *)ctx);
			}
		}
		free(pkey);
		if (rc == AVL_IX_OK)
			return 0;
		else
			return -1;
	}
}

/**
 * @brief
 * 	entlim_delete - delete record with a key based on the keystr
 *
 * @param[in] keystr - key string whose key is to be built
 * @param[in] recptr - pointer to record
 * @param[in] ctx - pointer to avl descending order tree info
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
	pbs_entlim_key_t *pkey;
	int               rc;
	void 		 *prec;

	pkey = entlim_create_key(keystr);
	if (pkey == NULL)
		return -1;

	rc =  avl_delete_key((AVL_IX_REC *)pkey, (AVL_IX_DESC *)ctx);
	prec = pkey->recptr;
	free(pkey);
	if (rc == AVL_IX_OK) {
		free_leaf(prec);
		return 0;
	} else
		return -1;
}

/**
 * @brief
 * 	entlim_get_next - walk the objects returning the next entry.
 *	If called with a NULL key, it allocates a key and returns
 *	the first entry; otherwise it returns the next entry.
 *
 * @param[in] keystr - key string whose key is to be built
 * @param[in] ctx - pointer to avl descending order tree info
 *
 * @return	structure handle
 * @retval	key info		success
 * @retval	NULL			error
 *		Returns NULL following the last entry or when no entry found
 *		The key needs to be freed by the caller when all is said and done.
 */
pbs_entlim_key_t *
entlim_get_next(pbs_entlim_key_t *pkey, void *ctx)
{

	if (ctx == NULL)
		return NULL;
	if (pkey == NULL) {
		pkey = entlim_create_key(NULL);
		if (pkey == NULL)
			return NULL;
		avl_first_key((AVL_IX_DESC *)ctx);
	}

	if (avl_next_key(pkey, (AVL_IX_DESC *)ctx) == AVL_IX_OK) {
		return pkey;
	} else {
		free(pkey);
		return NULL;
	}
}

/**
 * @brief
 * 	entlim_free_ctx - free the data structure including all keys and records
 *
 * @param[in] ctx - pointer to avl descending order tree info
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
	pbs_entlim_key_t *leaf;
	int		 rc;

	leaf = entlim_create_key(NULL);	/* alloc space for max sized key */
	if (leaf == NULL)
		return -1;
	avl_first_key((AVL_IX_DESC *)ctx);

	while ((rc = avl_next_key((AVL_IX_REC *)leaf, (AVL_IX_DESC *)ctx)) == AVL_IX_OK) {
		free_leaf(leaf->recptr);
	}
	free(leaf);
	avl_destroy_index((AVL_IX_DESC *)ctx);
	free(ctx);
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
 * @param[in] pk - pointer to key info
 * @param[in] rtnname - a buffer large enought to hold the max entity name +1
 * @param[in] ln      - the size of that buffer
 *
 * @return	int
 * @retval	0	entity name found and returned
 * @retval	-1	entity name would not fit
 */
int
entlim_entity_from_key(pbs_entlim_key_t *pk, char *rtnname, size_t ln)
{
	char *pc;
	int   sz = 0;

	pc = pk->key+2;
	while (*pc && (*pc != ';')) {
		++sz;
		++pc;
	}
	if ((size_t)sz < ln) {
		(void)strncpy(rtnname, pk->key+2, sz);
		*(rtnname+sz) = '\0';
		return 0;
	} else
	return -1;
}

/**
 * @brief
 * 	entlim_resc_from_key - obtain the resource name from a key if it
 *	includes one.
 *
 * @param[in] pk - pointer to key info
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
entlim_resc_from_key(pbs_entlim_key_t *pk, char *rtnresc, size_t ln)
{
	char *pc;

	pc = strchr(pk->key, (int)';');
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
