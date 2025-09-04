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
#ifndef _LIBAUTH_H
#define _LIBAUTH_H
#ifdef __cplusplus
extern "C" {
#endif

#include "log.h"
#include "portability.h"

/* Max length of auth method name */
#define MAXAUTHNAME 100

/* Type of roles */
enum AUTH_ROLE {
	/* Unknown role, mostly used as initial value */
	AUTH_ROLE_UNKNOWN = 0,
	/* Client role, aka who is initiating authentication */
	AUTH_CLIENT,
	/* Server role, aka who is authenticating incoming user/connection */
	AUTH_SERVER,
	/* qsub side, when authenticating an interactive connection (i.e. qsub -I) from an execution host */
	AUTH_INTERACTIVE,
	/* last role, mostly used while error checking for role value */
	AUTH_ROLE_LAST
};

/* Type of connections */
enum AUTH_CONN_TYPE {
	/* user-oriented connection (aka like PBS client is connecting to PBS Server) */
	AUTH_USER_CONN = 0,
	/* service-oriented connection (aka like PBS Mom is connecting to PBS Server via PBS Comm) */
	AUTH_SERVICE_CONN
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

	/*
	 * Function pointer to the logging method with the same signature as log_event from Liblog.
	 * With this, the user of the authentication library can redirect logs from the authentication
	 * library into respective log files or stderr in case no log files.
	 * If func is set to NULL then logs will be written to stderr (if available, else no logging at all).
	 */
	void (*logfunc)(int type, int objclass, int severity, const char *objname, const char *text);
} pbs_auth_config_t;

/** @brief
 *	pbs_auth_set_config - Set auth config
 *
 * @param[in] config - auth config structure
 *
 * @return void
 *
 */
extern DLLEXPORT void pbs_auth_set_config(const pbs_auth_config_t *config);

/** @brief
 *	pbs_auth_create_ctx - allocates auth context structure
 *
 * @param[in] ctx - pointer in which auth context to be allocated
 * @param[in] mode - AUTH_SERVER or AUTH_CLIENT
 * @param[in] conn_type - AUTH_USER_CONN or AUTH_SERVICE_CONN
 * @param[in] hostname - hostname of other authenticating party in case of AUTH_CLIENT else not used
 *
 * @return	int
 * @retval	0 - success
 * @retval	1 - error
 */
extern DLLEXPORT int pbs_auth_create_ctx(void **ctx, int mode, int conn_type, const char *hostname);

/** @brief
 *	pbs_auth_destroy_ctx - destroy given auth context structure
 *
 * @param[in] ctx - pointer to auth context
 *
 * @return void
 */
extern DLLEXPORT void pbs_auth_destroy_ctx(void *ctx);

/** @brief
 *	pbs_auth_get_userinfo - get user, host and realm from authentication context
 *
 * @param[in] ctx - pointer to auth context
 * @param[out] user - username assosiate with ctx
 * @param[out] host - hostname/realm assosiate with ctx
 * @param[out] realm - realm assosiate with ctx
 *
 * @return	int
 * @retval	0 on success
 * @retval	1 on error
 */
extern DLLEXPORT int pbs_auth_get_userinfo(void *ctx, char **user, char **host, char **realm);

/** @brief
 *	pbs_auth_process_handshake_data - process incoming auth handshake data or start auth handshake if no incoming data
 *
 * @param[in] ctx - pointer to auth context
 * @param[in] data_in - received auth token data (if any, else NULL)
 * @param[in] len_in - length of received auth token data (if any else 0)
 * @param[out] data_out - auth token data to send (if any, else NULL)
 * @param[out] len_out - lenght of auth token data to send (if any, else 0)
 * @param[out] is_handshake_done - indicates whether handshake is done (1) or not (0)
 *
 * @return	int
 * @retval	0 on success
 * @retval	!0 on error
 */
extern DLLEXPORT int pbs_auth_process_handshake_data(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out, int *is_handshake_done);

/** @brief
 *	pbs_auth_encrypt_data - encrypt data based on given auth context.
 *
 * @param[in] ctx - pointer to auth context
 * @param[in] data_in - clear text data
 * @param[in] len_in - length of clear text data
 * @param[out] data_out - encrypted data
 * @param[out] len_out - length of encrypted data
 *
 * @return	int
 * @retval	0 on success
 * @retval	1 on error
 */
extern DLLEXPORT int pbs_auth_encrypt_data(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out);

/** @brief
 *	pbs_auth_decrypt_data - decrypt data based on given auth context.
 *
 * @param[in] ctx - pointer to auth context
 * @param[in] data_in - encrypted data
 * @param[in] len_in - length of encrypted data
 * @param[out] data_out - clear text data
 * @param[out] len_out - length of clear text data
 *
 * @return	int
 * @retval	0 on success
 * @retval	1 on error
 */
extern DLLEXPORT int pbs_auth_decrypt_data(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out);

#ifdef __cplusplus
}
#endif
#endif /* _LIBAUTH_H */
