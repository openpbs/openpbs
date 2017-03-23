/*
 * Copyright (C) 1994-2017 Altair Engineering, Inc.
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
 * WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A
 * PARTICULAR PURPOSE.  See the GNU Affero General Public License for more details.
 *  
 * You should have received a copy of the GNU Affero General Public License along 
 * with this program.  If not, see <http://www.gnu.org/licenses/>.
 *  
 * Commercial License Information: 
 * 
 * The PBS Pro software is licensed under the terms of the GNU Affero General 
 * Public License agreement ("AGPL"), except where a separate commercial license 
 * agreement for PBS Pro version 14 or later has been executed in writing with Altair.
 *  
 * Altair’s dual-license business model allows companies, individuals, and 
 * organizations to create proprietary derivative works of PBS Pro and distribute 
 * them - whether embedded or bundled with other software - under a commercial 
 * license agreement.
 * 
 * Use of Altair’s trademarks, including but not limited to "PBS™", 
 * "PBS Professional®", and "PBS Pro™" and Altair’s logos is subject to Altair's 
 * trademark licensing policies.
 *
 */


#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <errno.h>
#include <limits.h>

#include "bitfield.h"

#include "allocnodes.h"
#include "mapnodes.h"
/**
 * @file	allocnodes.c
 */
/* local prototypes */
static unsigned long long alloc_chunk(unsigned long long chunk, int need);
static int msbit(unsigned long long word);
static int lsbit(unsigned long long word);
static int pop_count(unsigned long long word);
static int nodemask_popcount(Bitfield *nm);
static void nodes_log2phys(Bitfield *log_mask, Bitfield *fiz_mask);
static void nodes_phys2log(Bitfield *fiz_mask, Bitfield *log_mask);

extern int schd_Chunk_Quantum;
extern int alloc_nodes_greedy;

/**
 * @brief
 *	allocate requested number of nodes for job.
 *
 * @param[in] request - num of nodes requested
 * @param[in] from - pointer to Bitfield struct(nodepool)
 * @param[in] chose - pointer to Bitfield struct indicating assigned node
 *
 * @return	int
 * @retval	num of nodes assigned	success
 * @retval	0			error
 *
 */
int
alloc_nodes(int request, Bitfield *from, Bitfield *chose)
{
	Bitfield avail_log;
	Bitfield avail_fiz;
	Bitfield job_mask_fiz;
	int chunk_counts[BITFIELD_WORDS];
	unsigned long long chunk;
	int how_many;
	int ndx;
	int most;
	int mndx;
	int need;
	int small_ungreedy_failed = 0;

	/* check that we're configured */
	if (schd_Chunk_Quantum == -1)
		schd_Chunk_Quantum = 1;	/* default to 1 node */

	/*====================================*/
	/* see what's currently available and */
	/* check whether we can satisfy rqst  */
	/*====================================*/
	BITFIELD_CPY(&avail_log, from);
	nodes_log2phys(&avail_log, &avail_fiz);
	how_many = 0;
	for (ndx=0 ; ndx < BITFIELD_WORDS ; ++ndx) {
		chunk = BITFIELD_WORD(&avail_fiz, ndx);
		chunk_counts[ndx] = pop_count(chunk);
		how_many += chunk_counts[ndx];
	}
	if (how_many < request)
		return 0;

	BITFIELD_CLRALL(&job_mask_fiz);

	if (request <= 64) {
		/*========================================*/
		/* can fit within a chunk -- POLICY: only */
		/* allocate the nodes if they can be had  */
		/* from a _single_ chunk:   DON'T SPAN    */
		/*========================================*/
		for (ndx=0 ; ndx < BITFIELD_WORDS ; ++ndx)
			if (request <= chunk_counts[ndx])
				break;				/*"first fit"*/
		if (ndx == BITFIELD_WORDS) {
			if (!alloc_nodes_greedy)
				return 0;
			small_ungreedy_failed = 1;
		} else {

			chunk = BITFIELD_WORD(&avail_fiz, ndx);
			if (request < chunk_counts[ndx])
				chunk = alloc_chunk(chunk, request);
			BITFIELD_SET_WORD(&job_mask_fiz, ndx, chunk);
		}

	}

	if (small_ungreedy_failed || request > 64) {
		/*===============================*/
		/* this one _has_ to span chunks */
		/*     do "greedy allocation"    */
		/*===============================*/
		need = request;
		while (need > 0) {
			most = chunk_counts[0];
			mndx = 0;
			for (ndx=0 ; ndx < BITFIELD_WORDS ; ++ndx)
				if (chunk_counts[ndx] > most) {
					most = chunk_counts[ndx];
					mndx = ndx;
				}
			if (need >= chunk_counts[mndx]) {
				/* just grab 'em all _directly_ */
				chunk = BITFIELD_WORD(&avail_fiz, mndx);
				need -= chunk_counts[mndx];
				chunk_counts[mndx] = 0;
			} else {
				/* have to "pick and choose" */
				chunk = BITFIELD_WORD(&avail_fiz, mndx);
				chunk = alloc_chunk(chunk, need);
				need = 0;
			}
			BITFIELD_SET_WORD(&job_mask_fiz, mndx, chunk);
		}
	}

	nodes_phys2log(&job_mask_fiz, chose);
	BITFIELD_CLRM(from, chose);

	return nodemask_popcount(chose);
}

/**
 * @brief
 *	allocates resources for job as chunks.
 *
 * @param[in] chunk - available chunk
 * @param[in] need - needed chunk
 *
 * @return	unsigned long long
 * @retval	num of chunk allocated 		success
 * @retval	0				error
 *
 */
static unsigned long long
alloc_chunk(unsigned long long chunk, int need)
{
	unsigned long long jchunk;
	unsigned long long candidate;
	unsigned long long test;
	int n_found;
	int try_siz;
	int amsb;
	int alsb;
	int cmsb;
	int clsb;

	n_found = 0;	/* how many we've allocated so far */
	jchunk = 0;	/* which they are */

	try_siz = need;	/* size of "clump" to hunt for */

	while (n_found < need) {

		/* delimit the bits where we'll look this pass: */
		amsb = msbit(chunk);
		alsb = lsbit(chunk);

		/* build & align a clump of 'try_siz' contiguous bits */
		candidate = ~(~(unsigned long long)0 << try_siz);
		candidate <<= alsb;

		cmsb = msbit(candidate);
		clsb = lsbit(candidate);

		while (clsb >= alsb && cmsb <= amsb) {
			test = candidate & chunk;
			if (test == candidate) {
				/* entire clump available -- grab 'em */
				chunk &= ~candidate;
				jchunk |= candidate;
				n_found += try_siz;
				/*  Shall I continue _this_ pass ??   */
				/* I.e., do I still need this many ?? */
				if (n_found + try_siz > need)
					break;
				/* yes - get past new 0s in 'chunk' */
				candidate <<= try_siz;
				clsb += try_siz;
				cmsb += try_siz;
			} else {
				/*=========================================*/
				/* POLICY: we allocate nodes in clumps     */
				/* which have a multiple of CHUNK_QUANTUM  */
				/* bits -- this depends critically on the  */
				/* fact that all jobs are forced to use a  */
				/* number of nodes = 0 (mod CHUNK_QUANTUM) */
				/*=========================================*/
				candidate <<= schd_Chunk_Quantum;
				clsb += schd_Chunk_Quantum;
				cmsb += schd_Chunk_Quantum;
			}
		}
		/* have we allocated enough ? */
		if (n_found >= need)
			break;
		/* no -- lower our expectations and press on */
		try_siz -= schd_Chunk_Quantum;
		if (try_siz + n_found > need)
			try_siz = need - n_found;
		/*=================================*/
		/* since both 'need','n_found' are */
		/* 0 mod CHUNK_QUANTUM, so is the  */
		/* newly-adjusted value 'try_siz'  */
		/*=================================*/
	}

	return jchunk;
}

/**
 * @brief
 *	set most significant bit of allocated chunk.
 *
 * @param[in] word - chunk
 *
 * @return	int
 * @retval	msb set val	success
 *
 */
static int
msbit(unsigned long long word)
{
	int ndx = CHAR_BIT*sizeof(unsigned long long) - 1;
	unsigned char *p = (unsigned char *)&word;
	int i;
	int j;
	static unsigned char mask[CHAR_BIT] = {
		0x80, 0x40, 0x20, 0x10, 0x08, 0x04, 0x02, 0x01
	};

	i = 0;
	while (i < sizeof(unsigned long long) && p[i] == '\0') {
		ndx -= CHAR_BIT;
		++i;
	}
	if (i < sizeof(unsigned long long)) {
		for (j=0 ; j < CHAR_BIT ; ++j)
			if (p[i] & mask[j])
				break;
		ndx -= j;
	}
	return ndx;
}

/**
 * @brief
 *      set least significant bit of allocated chunk.
 *
 * @param[in] word - chunk
 *
 * @return      int
 * @retval      lsb set val     success
 *
 */

static int
lsbit(unsigned long long word)
{
	int ndx = 0;
	unsigned char *p = (unsigned char *)&word;
	int i;
	int j;
	static unsigned char mask[CHAR_BIT] = {
		0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80
	};

	i = sizeof(unsigned long long) - 1;
	while (i >= 0 && p[i] == '\0') {
		ndx += CHAR_BIT;
		--i;
	}
	if (i >= 0) {
		for (j=0 ; j < CHAR_BIT ; ++j)
			if (p[i] & mask[j])
				break;
		ndx += j;
	}
	return ndx;
}

/**
 * @brief
 *	counts the chunk of resource allocated.
 *
 * @param[in] word - chunk
 *
 * @return	int
 * @retval	summed chunk	success
 * @retval	0		error
 *
 */
static int
pop_count(unsigned long long word)
{
	int n_bits = 0;

	while (word) {
		word &= (word-1);
		++n_bits;
	}

	return n_bits;
}

/**
 * @brief
 *	counts and returns the num of nodes allocated.
 *
 * @param[in] nm - pointer to Bitfield struct indicating allocated nodes for a job.
 *
 * @return	int
 * @retval	num of allocated nodes		success
 * @retval	0				error
 *
 */
static int
nodemask_popcount(Bitfield *nm)
{
	unsigned long long word;
	int i;
	int popcount;

	popcount = 0;
	for (i=0 ; i < BITFIELD_WORDS ; ++i) {
		word = BITFIELD_WORD(nm, i);
		popcount += pop_count(word);
	}

	return popcount;
}

/**
 * @brief
 *	converts bitfield to hexadecimal string and returns it.
 *
 * @param[in] nm - Bitfield val
 *
 * @return	string
 * @retval	hex dec string		success
 * @retval	NULL			error
 *
 */
char *
bitfield2hex(Bitfield *nm)
{
	static char hexmask[2*sizeof(Bitfield)+2+1];
	static int width = 2*sizeof(unsigned long long);
	char *p;
	unsigned long long word;
	int ndx;

	p = hexmask;		/* BigEndian, so we go backwards */
	*p++ = '0';
	*p++ = 'x';
	ndx = BITFIELD_WORDS;
	while (ndx) {
		--ndx;
		word = BITFIELD_WORD(nm, ndx);		/* next bunch */
		sprintf(p, "%0*.*llx", width, width, word);	/* string'ize */
		p += strlen(p);
	}

	return hexmask;
}

/**
 * @brief
 *      converts bitfield to binary string and returns it.
 *
 * @param[in] nm - Bitfield val
 *
 * @return      string
 * @retval      binary string          success
 * @retval      NULL                    error
 *
 */
char *
bitfield2bin(Bitfield *nm)
{
	static char binmask[MAX_NODES_PER_HOST+1];
	int i;

	for (i=0; i < BITFIELD_SIZE; i++) {
		if (BITFIELD_TSTB(nm, i))
			binmask[i] = '1';
		else
			binmask[i] = '0';
	}
	binmask[i] = '\0';

	return binmask;
}

/**
 * @brief
 *	converts logical node num to physical node num.
 *
 * @param[in] log_mask - pointer to Bitfield struct indicating logical node mask
 * @param[out] fiz_mask - pointer to Bitfield struct indicating physical node mask
 *
 * @return	Void
 *
 */
static void
nodes_log2phys(Bitfield *log_mask, Bitfield *fiz_mask)
{
	int i;
	unsigned long long log_bit;
	int phys_bit;

	/* clear the bits */
	BITFIELD_CLRALL(fiz_mask);

	for (i=0 ; i < BITFIELD_SIZE ; ++i) {
		/* fetch the i'th bit from input */
		log_bit = BITFIELD_TSTB(log_mask, i);
		if (!log_bit)
			continue;		/* not set */
		/*==========================*/
		/*  is set -- which is the  */
		/* corresponding _physical_ */
		/*      node number ?       */
		/*==========================*/
		phys_bit = schd_nodes_log2phys[i];
		BITFIELD_SETB(fiz_mask, phys_bit);	/* set it */
	}

	return;
}

/**
 * @brief
 *      converts physical node num to logical node num.
 *
 * @param[out] log_mask - pointer to Bitfield struct indicating logical node mask
 * @param[in] fiz_mask - pointer to Bitfield struct indicating physical node mask
 *
 * @return      Void
 *
 */

static void
nodes_phys2log(Bitfield *fiz_mask, Bitfield *log_mask)
{
	int i;
	int log_bit;
	unsigned long long phys_bit;

	/* clear the bits */
	BITFIELD_CLRALL(log_mask);

	for (i=0 ; i < BITFIELD_SIZE ; ++i) {
		/* fetch the i'th bit from input */
		phys_bit = BITFIELD_TSTB(fiz_mask, i);
		if (!phys_bit)
			continue;		/* not set */
		/*==========================*/
		/*  is set -- which is the  */
		/* corresponding _physical_ */
		/*      node number ?       */
		/*==========================*/
		log_bit = schd_nodes_phys2log[i];
		BITFIELD_SETB(log_mask, log_bit);	/* set it */
	}

	return;
}
