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

#define AUTH_RESVPORT_NAME "resvport"
#define AUTH_GSS_NAME "gss"
#define MAXAUTHNAME 100
#ifndef MAXPATHLEN
#define MAXPATHLEN 1024
#endif

#define FOR_AUTH 0
#define FOR_ENCRYPT 1

enum ENCRYPT_MODE {
	ENCRYPT_DISABLE = 0,
	ENCRYPT_ONLY_CLIENT_TO_SERVER,
	ENCRYPT_ALL
};

enum AUTH_ROLE {
	AUTH_ROLE_UNKNOWN = 0,
	AUTH_CLIENT,
	AUTH_SERVER,
	AUTH_ROLE_LAST
};

enum AUTH_CTX_STATUS {
	AUTH_STATUS_UNKNOWN = 0,
	AUTH_STATUS_CTX_ESTABLISHING,
	AUTH_STATUS_CTX_READY
};

typedef struct pbs_auth_config {
	/* Path to PBS_HOME directory (aka PBS_HOME in pbs.conf). This should be a null-terminated string. */
	char *pbs_home_path;

	/* Path to PBS_EXEC directory (aka PBS_EXEC in pbs.conf). This should be a null-terminated string. */
	char *pbs_exec_path;

	/* Name of authentication method (aka PBS_AUTH_METHOD in pbs.conf). This should be a null-terminated string. */
	char *auth_method;

	/* Name of encryption method (aka PBS_ENCRYPT_METHOD in pbs.conf). This should be a null-terminated string. */
	char *encrypt_method;

	/* Encryption mode (aka PBS_ENCRYPT_MODE in pbs.conf) */
	int encrypt_mode;

	/*
	 * Function pointer to the logging method with the same signature as log_event from Liblog.
	 * With this, the user of the authentication library can redirect logs from the authentication
	 * library into respective log files or stderr in case no log files.
	 * If func is set to NULL then logs will be written to stderr (if available, else no logging at all).
	 */
	void (*logfunc)(int type, int objclass, int severity, const char *objname, const char *text);
} pbs_auth_config_t;

typedef struct auth_def {
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
	int (*create_ctx)(void **ctx, int mode, const char *hostname);

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
} auth_def_t;

enum AUTH_MSG_TYPES {
	AUTH_CTX_DATA = 1, /* starts from 1, zero means EOF */
	AUTH_ERR_DATA,
	AUTH_ENCRYPTED_DATA,
	AUTH_LAST_MSG
};

extern auth_def_t * get_auth(char *);
extern int load_auths(void);
extern void unload_auths(void);
int is_valid_encrypt_method(char *);

extern int engage_client_auth(int, char *, int , char *, size_t);
extern int engage_server_auth(int, char *, char *, int, char *, size_t);

#ifdef __cplusplus
}
#endif
#endif /* _AUTH_H */
