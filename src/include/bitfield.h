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

#ifndef _BITFIELD_H
#define _BITFIELD_H
#ifdef __cplusplus
extern "C" {
#endif

/*
 * Definition of interface for dealing with arbitrarily large numbers of
 * contiguous bits.  Size of the bitfield is declared at compile time with
 * the BITFIELD_SIZE #define (default is 128 bits).
 *
 * Macros/inlines all take pointers to a Bitfield, and provide :
 *
 * Macro BITFIELD_WORD(Bitfield *p,int ndx)
 * Macro BITFIELD_SET_WORD(Bitfield *p, int ndx, unsigned long long word)
 *
 * Macro BITFIELD_CLRALL(Bitfield *p)
 * Macro BITFIELD_SETALL(Bitfield *p)
 * 	Clear or set all bits in a Bitfield.
 *
 * Macro BITFIELD_SET_LSB(Bitfield *p)
 * Macro BITFIELD_CLR_LSB(Bitfield *p)
 * Macro BITFIELD_SET_MSB(Bitfield *p)
 * Macro BITFIELD_CLR_MSB(Bitfield *p)
 *	Set the least or most significant bit of a Bitfield.
 *
 * Macro BITFIELD_LSB_ISONE(Bitfield *p)
 * Macro BITFIELD_MSB_ISONE(Bitfield *p)
 * 	Equals non-zero if the least or most significant bit of the Bitfield
 * 	    is set, or zero otherwise.
 *
 * Macro BITFIELD_SETB(Bitfield *p, int bit)
 * Macro BITFIELD_CLRB(Bitfield *p, int bit)
 * Macro BITFIELD_TSTB(Bitfield *p, int bit)
 * 	Set, clear, or test the bit at position 'bit' in the Bitfield '*p'.
 * 	BITFIELD_TSTB() is non-zero if the bit at position 'bit' is set, or
 *	     zero if it is clear.
 *
 * Inline BITFIELD_IS_ZERO(Bitfield *p)
 * Inline BITFIELD_IS_ONES(Bitfield *p)
 * 	Return non-zero if the bitfield is composed of all zeros or ones,
 *	     or zero if the bitfield is non-homogeneous.
 *
 * Inline BITFIELD_IS_NONZERO(Bitfield *p)
 *	Returns non-zero if the bitfield contains at least one set bit.
 *
 * Inline BITFIELD_NUM_ONES(Bitfield *p)
 *	Returns number of '1' bits in the bitfield.
 *
 * Inline BITFIELD_MS_ONE(Bitfield *p)
 * Inline BITFIELD_LS_ONE(Bitfield *p)
 *	Returns bit position number of least or most significant 1-bit in
 *	the Bitfield.
 *
 * Inline BITFIELD_EQ(Bitfield *p, Bitfield *q)
 * Inline BITFIELD_NOTEQ(Bitfield *p, Bitfield *q)
 *	Return non-zero if Bitfields '*p' and '*q' are (not) equal.
 *
 * Inline BITFIELD_SETM(Bitfield *p, Bitfield *mask)
 * Inline BITFIELD_CLRM(Bitfield *p, Bitfield *mask)
 * Inline BITFIELD_ANDM(Bitfield *p, Bitfield *mask)
 * Inline BITFIELD_TSTM(Bitfield *p, Bitfield *mask)
 * Inline BITFIELD_TSTALLM(Bitfield *p, Bitfield *mask)
 *	Apply the specified 'mask' to the given bitfield 'p':
 *	SETM() sets bits in 'p' for any bits set in 'mask' ('p |= mask').
 *	CLRM() clears bits in 'p' for any bits set in 'mask' ('p &=~ mask').
 *	ANDM() logical-and's 'mask' into 'p' ('p &= mask');
 *	TSTM() returns non-zero if *any* bits set in 'mask' are set in 'p'.
 *	TSTMALL() returns non-zero if *all* bits set in 'mask' are also set
 *		in 'p'.
 *
 * Inline BITFIELD_CPY(Bitfield *p, Bitfield *q)
 * Inline BITFIELD_CPYNOTM(Bitfield *p, Bitfield *q)
 *	Copy the (inverse of) bitfield 'q' into 'p'.
 *
 * Inline BITFIELD_ORNOTM(Bitfield *p, Bitfield *q)
 * 	Set any bits in 'p' where the corresponding bit in 'q' is clear.
 * 	    (p |= ~q)
 *
 * Inline BITFIELD_SHIFTL(Bitfield *p)
 * Inline BITFIELD_SHIFTR(Bitfield *p)
 * 	Shift the bits in Bitfield 'p' one bit to the right or left.
 */

/* The size of bitfields being used.  Default to 256 bits. */
#ifndef BITFIELD_SIZE
#define BITFIELD_SIZE 256
#endif /* !BITFIELD_SIZE */

#include <assert.h>
#define BITFIELD_BPW ((int) (sizeof(unsigned long long) * 8))

#define BITFIELD_SHIFT(bit) ((bit) / BITFIELD_BPW)
#define BITFIELD_OFFSET(bit) ((bit) & (BITFIELD_BPW - 1))
#define BITFIELD_WORDS (BITFIELD_SHIFT(BITFIELD_SIZE))

typedef struct bitfield {
	unsigned long long _bits[BITFIELD_WORDS];
} Bitfield;

#define INLINE __inline

/* Word-oriented operations on bitfields */
#define BITFIELD_WORD(p, ndx) \
	(((ndx) >= 0 && (ndx) < BITFIELD_WORDS) ? (p)->_bits[ndx] : 0ULL)

#define BITFIELD_SET_WORD(p, ndx, word)                   \
	{                                                 \
		if ((ndx) >= 0 && (ndx) < BITFIELD_WORDS) \
			(p)->_bits[ndx] = word;           \
	}

/* Operate on least significant bit of a bitfield. */

#define BITFIELD_LSB_ISONE(p) \
	((p)->_bits[0] & 1ULL)

#define BITFIELD_SET_LSB(p) \
	((p)->_bits[0] |= 1ULL)

#define BITFIELD_CLR_LSB(p) \
	((p)->_bits[0] &= ~(1ULL))

/* Operate on most significant bit of a bitfield. */

#define BITFIELD_MSB_ISONE(p) \
	((p)->_bits[BITFIELD_SHIFT(BITFIELD_SIZE - 1)] & (1ULL << (BITFIELD_BPW - 1)))

#define BITFIELD_SET_MSB(p) \
	((p)->_bits[BITFIELD_SHIFT(BITFIELD_SIZE - 1)] |= (1ULL << (BITFIELD_BPW - 1)))

#define BITFIELD_CLR_MSB(p) \
	((p)->_bits[BITFIELD_SHIFT(BITFIELD_SIZE - 1)] &= ~(1ULL << (BITFIELD_BPW - 1)))

/* Operate on arbitrary bits within the bitfield. */

#define BITFIELD_SETB(p, bit) (((bit) >= 0 && (bit) < BITFIELD_SIZE) ? (p)->_bits[BITFIELD_SHIFT(bit)] |= (1ULL << BITFIELD_OFFSET(bit)) : 0)

#define BITFIELD_CLRB(p, bit) (((bit) >= 0 && (bit) < BITFIELD_SIZE) ? (p)->_bits[BITFIELD_SHIFT(bit)] &= ~(1ULL << BITFIELD_OFFSET(bit)) : 0)

#define BITFIELD_TSTB(p, bit) (((bit) >= 0 && (bit) < BITFIELD_SIZE) ? ((p)->_bits[BITFIELD_SHIFT(bit)] & (1ULL << BITFIELD_OFFSET(bit))) : 0)

/* Clear or set all the bits in the bitfield. */

#define BITFIELD_CLRALL(p)                           \
	{                                            \
		int w;                               \
		assert(p != NULL);                   \
		for (w = 0; w < BITFIELD_WORDS; w++) \
			(p)->_bits[w] = 0ULL;        \
	}

#define BITFIELD_SETALL(p)                           \
	{                                            \
		int w;                               \
		assert(p != NULL);                   \
		for (w = 0; w < BITFIELD_WORDS; w++) \
			(p)->_bits[w] = ~(0ULL);     \
	}

/* Comparison functions for two bitfield. */

INLINE int
BITFIELD_IS_ZERO(Bitfield *p)
{
	int w;
	assert(p != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		if ((p)->_bits[w])
			return 0;
	return 1;
}

INLINE int
BITFIELD_IS_ONES(Bitfield *p)
{
	int w;
	assert(p != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		if ((p)->_bits[w] != ~(0ULL))
			return 0;
	return 1;
}

INLINE int
BITFIELD_IS_NONZERO(Bitfield *p)
{
	int w;
	assert(p != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		if ((p)->_bits[w])
			return 1;
	return 0;
}

INLINE int
BITFIELD_NUM_ONES(Bitfield *p)
{
	int w, cnt;
	unsigned long long n;
	assert(p != NULL);

	cnt = 0;
	for (w = 0; w < BITFIELD_WORDS; w++)
		for (n = (p)->_bits[w]; n != 0ULL; cnt++)
			n &= (n - 1);

	return (cnt);
}

INLINE int
BITFIELD_LS_ONE(Bitfield *p)
{
	int w, bit;
	unsigned long long n, x;
	assert(p != NULL);

	bit = 0;
	for (w = 0; w < BITFIELD_WORDS; w++) {
		n = (p)->_bits[w];

		/* Look for the first non-zero word. */
		if (n != 0ULL)
			break;

		bit += BITFIELD_BPW;
	}

	/* No non-zero words found in the bitfield. */
	if (w == BITFIELD_WORDS)
		return (-1);

	/* Slide a single bit left, looking for the non-zero bit. */
	for (x = 1ULL; !(n & x); bit++)
		x <<= 1;

	return (bit);
}

INLINE int
BITFIELD_MS_ONE(Bitfield *p)
{
	int w, bit;
	unsigned long long n, x;
	assert(p != NULL);

	bit = BITFIELD_SIZE - 1;
	for (w = BITFIELD_WORDS - 1; w >= 0; w--) {
		n = (p)->_bits[w];

		/* Look for the first non-zero word. */
		if (n != 0ULL)
			break;

		bit -= BITFIELD_BPW;
	}

	/* No non-zero words found in the bitfield. */
	if (w < 0)
		return (-1);

	/* Slide a single bit right, looking for the non-zero bit. */
	for (x = 1ULL << BITFIELD_BPW - 1; !(n & x); bit--)
		x >>= 1;

	return (bit);
}

INLINE int
BITFIELD_EQ(Bitfield *p, Bitfield *q)
{
	int w;
	assert(p != NULL && q != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		if ((p)->_bits[w] != (q)->_bits[w])
			return 0;
	return 1;
}

INLINE int
BITFIELD_NOTEQ(Bitfield *p, Bitfield *q)
{
	int w;
	assert(p != NULL && q != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		if ((p)->_bits[w] != (q)->_bits[w])
			return 1;
	return 0;
}

/* Logical manipulation functions for applying one bitfield to another. */

INLINE int
BITFIELD_SETM(Bitfield *p, Bitfield *mask)
{
	int w;
	assert(p != NULL && mask != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		(p)->_bits[w] |= (mask)->_bits[w];
	return 0;
}

INLINE int
BITFIELD_CLRM(Bitfield *p, Bitfield *mask)
{
	int w;
	assert(p != NULL && mask != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		(p)->_bits[w] &= ~((mask)->_bits[w]);
	return 0;
}

INLINE int
BITFIELD_ANDM(Bitfield *p, Bitfield *mask)
{
	int w;
	assert(p != NULL && mask != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		(p)->_bits[w] &= (mask)->_bits[w];
	return 0;
}

INLINE int
BITFIELD_TSTM(Bitfield *p, Bitfield *mask)
{
	int w;
	assert(p != NULL && mask != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		if ((p)->_bits[w] & (mask)->_bits[w])
			return 1;
	return 0;
}

INLINE int
BITFIELD_TSTALLM(Bitfield *p, Bitfield *mask)
{
	int w;
	assert(p != NULL && mask != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		if (((p)->_bits[w] & (mask)->_bits[w]) != (mask)->_bits[w])
			return 0;
	return 1;
}

INLINE int
BITFIELD_CPY(Bitfield *p, Bitfield *q)
{
	int w;
	assert(p != NULL && q != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		(p)->_bits[w] = (q)->_bits[w];
	return 0;
}

INLINE int
BITFIELD_CPYNOTM(Bitfield *p, Bitfield *q)
{
	int w;
	assert(p != NULL && q != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		(p)->_bits[w] = ~((q)->_bits[w]);
	return 0;
}

INLINE int
BITFIELD_ORNOTM(Bitfield *p, Bitfield *q)
{
	int w;
	assert(p != NULL && q != NULL);
	for (w = 0; w < BITFIELD_WORDS; w++)
		(p)->_bits[w] |= ~((q)->_bits[w]);
	return 0;
}

/* Logical shift left and shift right for bitfield. */

INLINE int
BITFIELD_SHIFTL(Bitfield *p)
{
	int w, upper;
	assert(p != NULL);

	for (w = 0; w < BITFIELD_WORDS - 1; w++) {
		upper = (p->_bits[w] & (1ULL << (BITFIELD_BPW - 1))) ? 1 : 0;
		p->_bits[w] <<= 1;
		p->_bits[w + 1] <<= 1;
		p->_bits[w + 1] |= upper;
	}
	return 0;
}

INLINE int
BITFIELD_SHIFTR(Bitfield *p)
{
	int w, lower;
	assert(p != NULL);

	for (w = BITFIELD_WORDS - 1; w > 0; w--) {
		lower = p->_bits[w] & 1ULL;
		p->_bits[w] >>= 1;
		p->_bits[w - 1] >>= 1;
		p->_bits[w - 1] |= (lower ? (1ULL << (BITFIELD_BPW - 1)) : 0);
	}
	return 0;
}
#ifdef __cplusplus
}
#endif
#endif /* _BITFIELD_H */
