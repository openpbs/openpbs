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

#ifndef _AUTH_H
#define _AUTH_H
#ifdef __cplusplus
extern "C" {
#endif

#include "libauth.h"

#define AUTH_RESVPORT_NAME "resvport"
#define AUTH_MUNGE_NAME "munge"
#define AUTH_GSS_NAME "gss"
#ifndef MAXPATHLEN
#define MAXPATHLEN 1024
#endif

#define FOR_AUTH 0
#define FOR_ENCRYPT 1

enum AUTH_CTX_STATUS {
	AUTH_STATUS_UNKNOWN = 0,
	AUTH_STATUS_CTX_ESTABLISHING,
	AUTH_STATUS_CTX_READY
};

typedef struct auth_def auth_def_t;
struct auth_def {
	/* name of authentication method name */
	char name[MAXAUTHNAME + 1];

	/* pointer to store handle from loaded auth library */
	void *lib_handle;

	/*
	 * the function pointer to set logger method for auth lib
	 */
	void (*set_config)(const pbs_auth_config_t *auth_config);

	/*
	 * the function pointer to create new auth context used by auth lib
	 */
	int (*create_ctx)(void **ctx, int mode, int conn_type, const char *hostname);

	/*
	 * the function pointer to free auth context used by auth lib
	 */
	void (*destroy_ctx)(void *ctx);

	/*
	 * the function pointer to get user, host and realm information from authentication context
	 */
	int (*get_userinfo)(void *ctx, char **user, char **host, char **realm);

	/*
	 * the function pointer to process auth handshake data and authenticate user/connection
	 */
	int (*process_handshake_data)(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out, int *is_handshake_done);

	/*
	 * the function pointer to encrypt data
	 */
	int (*encrypt_data)(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out);

	/*
	 * the function pointer to decrypt data
	 */
	int (*decrypt_data)(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out);

	/*
	 * pointer to next authdef structure
	 */
	auth_def_t *next;
};

enum AUTH_MSG_TYPES {
	AUTH_CTX_DATA = 1, /* starts from 1, zero means EOF */
	AUTH_ERR_DATA,
	AUTH_CTX_OK,
	AUTH_ENCRYPTED_DATA,
	AUTH_LAST_MSG
};

extern auth_def_t *get_auth(char *);
extern int load_auths(int mode);
extern void unload_auths(void);
int is_valid_encrypt_method(char *);
pbs_auth_config_t *make_auth_config(char *, char *, char *, char *, void *);
void free_auth_config(pbs_auth_config_t *);

extern int engage_client_auth(int, const char *, int, char *, size_t);
extern int engage_server_auth(int, char *, int, int, char *, size_t);
int handle_client_handshake(int fd, const char *hostname, char *method, int for_encrypt, pbs_auth_config_t *config, char *ebuf, size_t ebufsz);

/* For qsub interactive - execution host authentication */
enum INTERACTIVE_AUTH_STATUS {
	INTERACTIVE_AUTH_SUCCESS = 0,
	INTERACTIVE_AUTH_FAILED,
	INTERACTIVE_AUTH_RETRY
};
int auth_exec_socket(int sock, unsigned short port, char *auth_method, char *jobid);
int auth_with_qsub(int sock, unsigned short port, char* hostname, char *auth_method, char *jobid);
int client_cipher_auth(int fd, char *text, char *ebuf, size_t ebufsz);
int server_cipher_auth(int fd, char *text, char *ebuf, size_t ebufsz);

#ifdef __cplusplus
}
#endif
#endif /* _AUTH_H */
