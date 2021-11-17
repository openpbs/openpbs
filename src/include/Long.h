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

#ifndef _LONG_H
#define _LONG_H
#ifdef __cplusplus
extern "C" {
#endif

#include <limits.h>

/*
 * Define Long and u_Long to be the largest integer types supported by the
 * native compiler.  They need not be supported by printf or scanf or their
 * ilk.  Ltostr, uLtostr, strtoL, strtouL, and atoL provide conversion to and
 * from character string form.
 *
 * The following sections are listed in decreasing order of brain damage.
 */

/****************************************************************************/
#if defined(__GNUC__)

/* On these systems, the compiler supports 64-bit integers as long longs but */
/* there seems to be neither defined constant support nor library support. */

typedef long long Long;
typedef unsigned long long u_Long;

#define lONG_MIN (-0x7FFFFFFFFFFFFFFFLL - 1)
#define lONG_MAX 0x7FFFFFFFFFFFFFFFLL
#define UlONG_MAX 0xFFFFFFFFFFFFFFFFULL

Long strToL(const char *nptr, char **endptr, int base);
u_Long strTouL(const char *nptr, char **endptr, int base);
#define atoL(nptr) strToL((nptr), NULL, 10)

/****************************************************************************/
#elif defined(WIN32) /* Windows */

/* long long and unsigned long long are 64 bit signed  and unsigned */
/* integers on Windows platforms. */
/* C compilers under Windows has built in functions for conversion */
/* from string to 64 bit integers of signed and unsigned version. */

typedef long long Long;
typedef unsigned long long u_Long;

#define lONG_MIN LLONG_MIN
#define lONG_MAX LLONG_MAX
#define UlONG_MAX ULLONG_MAX

#define strToL(n, e, b) _strtoi64(n, e, (b))
#define strTouL(n, e, b) _strtoui64(n, e, (b))
#define aToL(nptr) _atoi64((nptr))
#define atoL(nptr) aToL((nptr))

/****************************************************************************/

#endif

const char *uLTostr(u_Long value, int base);
#ifdef __cplusplus
}
#endif
#endif /* _LONG_H */
