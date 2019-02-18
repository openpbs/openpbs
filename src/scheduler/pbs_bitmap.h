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

#ifndef _PBS_BITMASK_H
#define _PBS_BITMASK_H
#ifdef	__cplusplus
extern "C" {
#endif


struct pbs_bitmap {
	unsigned long *bits;	/* bit storage */
	long num_longs;		/* number of longs in the bits array */
	long num_bits;		/* number of bits that are in use (both 1's and 0's */
};

typedef struct pbs_bitmap pbs_bitmap;

/* Allocate bits to a bitmap (and possibly the bitmap itself) */
pbs_bitmap *pbs_bitmap_alloc(pbs_bitmap *pbm, long num_bits);

/* Destructor */
void pbs_bitmap_free(pbs_bitmap *bm);

/* Turn a bit on */
int pbs_bitmap_bit_on(pbs_bitmap *pbm, long bit);

/* Turn a bit off */
int pbs_bitmap_bit_off(pbs_bitmap *pbm, long bit);

/* Get a bit */
int pbs_bitmap_get_bit(pbs_bitmap *pbm, unsigned long bit);

/* Get the first on bit in a bitmap */
int pbs_bitmap_first_on_bit(pbs_bitmap *bm);

/* Starting at start_bit get the next on bit */
int pbs_bitmap_next_on_bit(pbs_bitmap *pbm, long start_bit);

/* pbs_bitmap's version of L = R */
int pbs_bitmap_assign(pbs_bitmap *L, pbs_bitmap *R);

/* pbs_bitmap's version of L == R */
int pbs_bitmap_is_equal(pbs_bitmap *L, pbs_bitmap *R);

#ifdef	__cplusplus
}
#endif
#endif	/* _PBS_BITMASK_H */
