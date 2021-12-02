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

/*------------------------------------------------------------------------
 * Possible return values for the various external functions in the library
 *------------------------------------------------------------------------
 */

#ifndef _LIBSEC_H
#define _LIBSEC_H
#ifdef __cplusplus
extern "C" {
#endif

#define STD 0  /* standard PBS security (pbs_iff program) */
#define KRB5 1 /* krb5/gssapi based authentication and encryption */

#define CS_SUCCESS 0	     /* success			*/
#define CS_FATAL_NOMEM 1     /* memory allocation failure	*/
#define CS_FATAL_NOAUTH 2    /* authentication failure	*/
#define CS_FATAL 3	     /* non-specific failure		*/
#define CS_NOTIMPLEMENTED 4  /* function not implmeneted	*/
#define CS_AUTH_CHECK_PORT 6 /* STD CS_server_auth return code */
#define CS_AUTH_USE_IFF 7    /* STD CS_client_auth return code */
#define CS_REMAP_CTX_FAIL 8

#define CS_IO_FAIL -1	     /* error in CS_read, CS_write   */
#define CS_CTX_TRAK_FATAL -2 /* error with context tracking  */

#define CS_MODE_CLIENT 0
#define CS_MODE_SERVER 1

extern int CS_read(int sd, char *buf, size_t len);
extern int CS_write(int sd, char *buf, size_t len);
extern int CS_client_auth(int sd);
extern int CS_server_auth(int sd);
extern int CS_close_socket(int sd);
extern int CS_close_app(void);
extern int CS_client_init(void);
extern int CS_server_init(void);
extern int CS_verify(void);
extern int CS_reset_vector(int sd);
extern int CS_remap_ctx(int sd, int newsd);
extern void (*p_cslog)(int ecode, const char *caller, const char *txtmsg);

#define cs_logerr(a, b, c) ((*p_cslog)((a), (b), (c)))

#ifdef __cplusplus
}
#endif
#endif /* _LIBSEC_H */
