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

#ifndef	_DIS_H
#define	_DIS_H
#ifdef	__cplusplus
extern "C" {
#endif

#include <string.h>
#include <limits.h>
#include <float.h>
#include "Long.h"
#include "auth.h"

#ifndef TRUE
#define TRUE	1
#define FALSE	0
#endif

/*
 * Integer function return values from Data-is-Strings reading calls
 */

#define DIS_SUCCESS	0	/* No error */
#define DIS_OVERFLOW	1	/* Value too large to convert */
#define DIS_HUGEVAL	2	/* Tried to write floating point infinity */
#define DIS_BADSIGN	3	/* Negative sign on an unsigned datum */
#define DIS_LEADZRO	4	/* Input count or value has leading zero */
#define DIS_NONDIGIT	5	/* Non-digit found where a digit was expected */
#define DIS_NULLSTR	6	/* String read has an embedded ASCII NUL */
#define DIS_EOD		7	/* Premature end of message */
#define DIS_NOMALLOC	8	/* Unable to malloc space for string */
#define DIS_PROTO	9	/* Supporting protocol failure */
#define DIS_NOCOMMIT	10	/* Protocol failure in commit */
#define DIS_EOF		11	/* End of File */


unsigned long disrul(int stream, int *retval);

/*#if UINT_MAX == ULONG_MAX*/
#if SIZEOF_UNSIGNED == SIZEOF_LONG
#define disrui(stream, retval) (unsigned)disrul(stream, (retval))
#else
unsigned disrui(int stream, int *retval);
#endif

/*#if USHRT_MAX == UINT_MAX*/
#if SIZEOF_UNSIGNED_SHORT == SIZEOF_UNSIGNED_INT
#define disrus(stream, retval) (unsigned short)disrui(stream, (retval))
#else
unsigned short disrus(int stream, int *retval);
#endif

/*#if UCHAR_MAX == USHRT_MAX*/
#if SIZEOF_UNSIGNED_CHAR == SIZEOF_UNSIGNED_SHORT
#define disruc(stream, retval) (unsigned char)disrus(stream, (retval))
#else
unsigned char disruc(int stream, int *retval);
#endif

long disrsl(int stream, int *retval);
/*#if INT_MIN == LONG_MIN && INT_MAX == LONG_MAX*/
#if SIZEOF_INT == SIZEOF_LONG
#define disrsi(stream, retval) (int)disrsl(stream, (retval))
#else
int disrsi(int stream, int *retval);
#endif

/*#if SHRT_MIN == INT_MIN && SHRT_MAX == INT_MAX*/
#if SIZEOF_SHORT == SIZEOF_INT
#define disrss(stream, retval) (short)disrsi(stream, (retval))
#else
short disrss(int stream, int *retval);
#endif

/*#if CHAR_MIN == SHRT_MIN && CHAR_MAX == SHRT_MAX*/
#if SIZEOF_SIGNED_CHAR == SIZEOF_SHORT
#define disrsc(stream, retval) (signed char)disrss(stream, (retval))
#else
signed char disrsc(int stream, int *retval);
#endif

/*#if CHAR_MIN, i.e. if chars are signed*/
/* also, flip the order of statements */
#if __CHAR_UNSIGNED__
#define disrc(retval, stream) (char)disruc(stream, (retval))
#else
#define disrc(stream, retval) (char)disrsc(stream, (retval))
#endif

char *disrcs(int stream, size_t *nchars, int *retval);
int disrfcs(int stream, size_t *nchars, size_t achars, char *value);
char *disrst(int stream, int *retval);
int disrfst(int stream, size_t achars, char *value);

/*
 * some compilers do not like long doubles, if long double is the same
 * as a double, just use a double.
 */
#if SIZEOF_DOUBLE == SIZEOF_LONG_DOUBLE
typedef double dis_long_double_t;
#else
typedef long double dis_long_double_t;
#endif

dis_long_double_t disrl(int stream, int *retval);
/*#if DBL_MANT_DIG == LDBL_MANT_DIG && DBL_MAX_EXP == LDBL_MAX_EXP*/
#if SIZEOF_DOUBLE == SIZEOF_LONG_DOUBLE
#define disrd(stream, retval) (double)disrl(stream, (retval))
#else
double disrd(int stream, int *retval);
#endif

/*#if FLT_MANT_DIG == DBL_MANT_DIG && FLT_MAX_EXP == DBL_MAX_EXP*/
#if SIZEOF_FLOAT == SIZEOF_DOUBLE
#define disrf(stream, retval) (float)disrd(stream, (retval))
#else
float disrf(int stream, int *retval);
#endif

int diswul(int stream, unsigned long value);
/*#if UINT_MAX == ULONG_MAX*/
#if SIZEOF_UNSIGNED_INT == SIZEOF_UNSIGNED_LONG
#define diswui(stream, value) diswul(stream, (unsigned long)(value))
#else
int diswui(int stream, unsigned value);
#endif
#define diswus(stream, value) diswui(stream, (unsigned)(value))
#define diswuc(stream, value) diswui(stream, (unsigned)(value))

int diswsl(int stream, long value);
/*#if INT_MIN == LONG_MIN && INT_MAX == LONG_MAX*/
#if SIZEOF_INT == SIZEOF_LONG
#define diswsi(stream, value) diswsl(stream, (long)(value))
#else
int diswsi(int stream, int value);
#endif
#define diswss(stream, value) diswsi(stream, (int)(value))
#define diswsc(stream, value) diswsi(stream, (int)(value))

/*#if CHAR_MIN*/
#if __UNSIGNED_CHAR__
#define diswc(stream, value) diswui(stream, (unsigned)(value))
#else
#define diswc(stream, value) diswsi(stream, (int)(value))
#endif

int diswcs(int stream, const char *value, size_t nchars);
#define diswst(stream, value) diswcs(stream, value, strlen(value))

int diswl_(int stream, dis_long_double_t value, unsigned int ndigs);
#define diswl(stream, value) diswl_(stream, (value), LDBL_DIG)
#define diswd(stream, value) diswl_(stream, (dis_long_double_t)(value), DBL_DIG)
/*#if FLT_MANT_DIG == DBL_MANT_DIG || DBL_MANT_DIG == LDBL_MANT_DIG*/
#if SIZEOF_FLOAT == SIZEOF_DOUBLE
#define diswf(stream, value) diswl_(stream, (dis_long_double_t)(value), FLT_DIG)
#else
int diswf(int stream, double value);
#endif

int diswull(int stream, u_Long value);
u_Long disrull(int stream, int *retval);

extern const char *dis_emsg[];

/* the following routines set/control DIS over tcp */
extern void DIS_tcp_funcs();

#define PBS_DIS_BUFSZ 8192

#define DIS_WRITE_BUF 0
#define DIS_READ_BUF 1

typedef struct pbs_dis_buf {
	size_t tdis_bufsize;
	size_t tdis_len;
	char *tdis_pos;
	char *tdis_data;
} pbs_dis_buf_t;

typedef struct pbs_tcp_auth_data {
	int ctx_status;
	void *ctx;
	auth_def_t *def;
} pbs_tcp_auth_data_t;

typedef struct pbs_tcp_chan {
	pbs_dis_buf_t readbuf;
	pbs_dis_buf_t writebuf;
	int is_old_client; /* This is just for backward compatibility */
	pbs_tcp_auth_data_t auths[2];
} pbs_tcp_chan_t;

void dis_clear_buf(pbs_dis_buf_t *);
void dis_reset_buf(int, int);
int disr_skip(int, size_t);
int dis_getc(int);
int dis_gets(int, char *, size_t);
int dis_puts(int, const char *, size_t);
int dis_flush(int);
void dis_setup_chan(int, pbs_tcp_chan_t * (*)(int));
void dis_destroy_chan(int);

void transport_chan_set_ctx_status(int, int, int);
int transport_chan_get_ctx_status(int, int);
void transport_chan_set_authctx(int, void *, int);
void * transport_chan_get_authctx(int, int);
void transport_chan_set_authdef(int, auth_def_t *, int);
auth_def_t * transport_chan_get_authdef(int, int);
int transport_send_pkt(int, int, void *, size_t);
int transport_recv_pkt(int, int *, void **, size_t *);

extern pbs_tcp_chan_t * (*pfn_transport_get_chan)(int);
extern int (*pfn_transport_set_chan)(int, pbs_tcp_chan_t *);
extern int (*pfn_transport_recv)(int, void *, int);
extern int (*pfn_transport_send)(int, void *, int);

#define transport_recv(x, y, z) (*pfn_transport_recv)(x, y, z)
#define transport_send(x, y, z) (*pfn_transport_send)(x, y, z)
#define transport_get_chan(x) (*pfn_transport_get_chan)(x)
#define transport_set_chan(x, y) (*pfn_transport_set_chan)(x, y)

#ifdef	__cplusplus
}
#endif
#endif	/* _DIS_H */
