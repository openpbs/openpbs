/*
 * Copyright (C) 1994-2020 Altair Engineering, Inc.
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
#ifndef _AUTH_H
#define _AUTH_H
#ifdef __cplusplus
extern "C" {
#endif

#include "batch_request.h"
#include "net_connect.h"

/*
 * the function pointer to set configuration for auth lib
 * MUST exist in auth lib
 */
extern void (*pbs_auth_set_config)(void (*func)(int type, int objclass, int severity, const char *objname, const char *text), char *cred_location);

/*
 * the function pointer to create new auth context used by auth lib
 * MUST exist in auth lib
 */
extern int (*pbs_auth_create_ctx)(void **ctx, int mode, const char *hostname);

/*
 * the function pointer to free auth context used by auth lib
 * MUST exist in auth lib
 */
extern void (*pbs_auth_destroy_ctx)(void *ctx);

/*
 * the function pointer to get user, host and realm information from authentication context
 * MUST exist in auth lib
 */
extern int (*pbs_auth_get_userinfo)(void *ctx, char **user, char **host, char **realm);

/*
 * the function pointer to do auth handshake and authenticate user/connection
 * MUST exist in auth lib
 */
extern int (*pbs_auth_do_handshake)(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out, int *is_handshake_done);

/*
 * the function pointer to encrypt data
 * Should exist in auth lib if auth lib supports encrypt/decrypt
 */
extern int (*pbs_auth_encrypt_data)(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out);

/*
 * the function pointer to decrypt data
 * Should exist in auth lib if auth lib supports encrypt/decrypt
 */
extern int (*pbs_auth_decrypt_data)(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out);


enum AUTH_MSG_TYPES {
	AUTH_CTX_DATA = 1, /* starts from 1, zero means EOF */
	AUTH_ENCRYPTED_DATA,
	AUTH_LAST_MSG
};

extern int recv_auth_token(int, int *, void **, size_t *);
extern int send_auth_token(int, int, void *, size_t);
extern int engage_client_auth(int, char *, char *, size_t);
extern int engage_server_auth(int, char *, char *, char *, size_t);
extern int load_auth_lib(void);
extern void unload_auth_lib(void);

#ifdef __cplusplus
}
#endif
#endif /* _AUTH_H */
