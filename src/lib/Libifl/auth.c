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

#include <pbs_config.h>   /* the master config generated by configure */
#include <stdio.h>
#include <errno.h>
#include <arpa/inet.h>
#ifndef WIN32
#include <netinet/tcp.h>
#include <dlfcn.h>
#else
#include "win.h"
#endif
#include "dis.h"
#include "pbs_ifl.h"
#include "libpbs.h"
#include "libsec.h"
#include "auth.h"
#include "log.h"

static auth_def_t **auths = NULL;

static int _invoke_pbs_iff(int psock, char *server_name, int server_port, char *ebuf, size_t ebufsz);
static int _handle_client_handshake(int fd, char *hostname, char *method, int for_encrypt, pbs_auth_config_t *config, char *ebuf, size_t ebufsz);
static char * _get_load_lib_error(int reset);
static void * _load_lib(char *loc);
static void * _load_symbol(char *libloc, void *libhandle, char *name, int required);
static auth_def_t * _load_auth(char *name);
static void _unload_auth(auth_def_t *auth);

static char *
_get_load_lib_error(int reset)
{
	if (reset) {
#ifndef WIN32
		(void)dlerror();
#else
		(void)SetLastError(0);
#endif
		return NULL;
	}
#ifndef WIN32
	return dlerror();
#else
	static char buf[LOG_BUF_SIZE + 1] = {'\0'};
	LPVOID lpMsgBuf;
	int err = GetLastError();
	int len = 0;

	FormatMessage(
		FORMAT_MESSAGE_ALLOCATE_BUFFER |
		FORMAT_MESSAGE_FROM_SYSTEM |
		FORMAT_MESSAGE_IGNORE_INSERTS,
		NULL, err,
		MAKELANGID(LANG_NEUTRAL, SUBLANG_DEFAULT),
		(LPTSTR)&lpMsgBuf, 0, NULL);
	strncpy(buf, lpMsgBuf, sizeof(buf));
	LocalFree(lpMsgBuf);
	buf[sizeof(buf) - 1] = '\0';
	len = strlen(buf);
	if (buf[len - 1] == '\n')
		len--;
	if (buf[len - 1] == '.')
		len--;
	buf[len - 1] = '\0';
	return buf;
#endif
}

static void *
_load_lib(char *loc)
{
	(void)_get_load_lib_error(1);
#ifndef WIN32
	return dlopen(loc, RTLD_LAZY);
#else
	return LoadLibrary(loc);
#endif
}

static void *
_load_symbol(char *libloc, void *libhandle, char *name, int required)
{
	void *handle = NULL;

	(void)_get_load_lib_error(1);
#ifndef WIN32
	handle = dlsym(libhandle, name);
#else
	handle = GetProcAddress(libhandle, name);
#endif
	if (required && handle == NULL) {
		char *errmsg = _get_load_lib_error(0);
		if (errmsg) {
			fprintf(stderr, "%s\n", errmsg);
		} else {
			fprintf(stderr, "symbol %s not found in %s", name, libloc);
		}
		return NULL;
	}
	return handle;
}

static auth_def_t *
_load_auth(char *name)
{
	char libloc[MAXPATHLEN + 1] = {'\0'};
	char *errmsg = NULL;
	auth_def_t *auth = NULL;

	if (strcmp(name, AUTH_RESVPORT_NAME) == 0)
		return NULL;

	auth = (auth_def_t *)calloc(1, sizeof(auth_def_t));
	if (auth == NULL) {
		return NULL;
	}

	strcpy(auth->name, name);
	auth->name[MAXAUTHNAME] = '\0';

#ifndef WIN32
	snprintf(libloc, MAXPATHLEN, "%s/lib/libauth_%s.so", pbs_conf.pbs_exec_path, name);
#else
	snprintf(libloc, MAXPATHLEN, "%slib/libauth_%s.dll", pbs_conf.pbs_exec_path, name);
#endif
	libloc[MAXPATHLEN] = '\0';

	auth->lib_handle = _load_lib(libloc);
	if (auth->lib_handle == NULL) {
		errmsg = _get_load_lib_error(0);
		if (errmsg) {
			fprintf(stderr, "%s\n", errmsg);
		} else {
			fprintf(stderr, "Failed to load %s\n", libloc);
		}
		return NULL;
	}

	auth->set_config = _load_symbol(libloc, auth->lib_handle, "pbs_auth_set_config", 1);
	if (auth->set_config == NULL)
		goto err;

	auth->create_ctx = _load_symbol(libloc, auth->lib_handle, "pbs_auth_create_ctx", 1);
	if (auth->create_ctx == NULL)
		goto err;

	auth->destroy_ctx = _load_symbol(libloc, auth->lib_handle, "pbs_auth_destroy_ctx", 1);
	if (auth->destroy_ctx == NULL)
		goto err;

	auth->get_userinfo = _load_symbol(libloc, auth->lib_handle, "pbs_auth_get_userinfo", 1);
	if (auth->get_userinfo == NULL)
		goto err;

	auth->process_handshake_data = _load_symbol(libloc, auth->lib_handle, "pbs_auth_process_handshake_data", 1);
	if (auth->process_handshake_data == NULL)
		goto err;

	/*
	 * There are possiblity that auth lib only support authentication
	 * but not encrypt/decrypt of data (for example munge auth lib)
	 * so below 2 methods are marked as NOT required
	 * and no error check for _load_symbol
	 */
	auth->encrypt_data = _load_symbol(libloc, auth->lib_handle, "pbs_auth_encrypt_data", 0);
	auth->decrypt_data = _load_symbol(libloc, auth->lib_handle, "pbs_auth_decrypt_data", 0);

	return auth;

err:
	(void)_unload_auth(auth);
	return NULL;
}

static void
_unload_auth(auth_def_t *auth)
{
	if (auth == NULL)
		return;
	if (auth->lib_handle != NULL) {
#ifndef WIN32
		(void)dlclose(auth->lib_handle);
#else
		(void)FreeLibrary(auth->lib_handle);
#endif
	}
	memset(auth, 0, sizeof(auth_def_t));
	free(auth);
	return;
}


auth_def_t *
get_auth(char *method)
{
	int i = 0;

	if (auths == NULL)
		return NULL;

	while (auths[i] != NULL) {
		if (strcmp(auths[i]->name, method) == 0)
			return auths[i];
		i++;
	}

	return NULL;
}

int
load_auths(void)
{
	int i = 0;
	int count = 0;

	if (pbs_conf.supported_auth_methods == NULL || auths != NULL)
		return 0;

	i = 0;
	while (pbs_conf.supported_auth_methods[i++] != NULL) count++;

	if (count == 0)
		return 1;

	auths = (auth_def_t **)calloc(1, sizeof(auth_def_t *) * (count + 1)); /* +1 for last NULL */
	if (auths == NULL)
		return 1;

	count = 0;
	i = 0;
	while (pbs_conf.supported_auth_methods[i] != NULL) {
		auth_def_t *auth = NULL;
		if (strcmp(pbs_conf.supported_auth_methods[i], AUTH_RESVPORT_NAME) == 0) {
			i++;
			continue;
		}
		auth = _load_auth(pbs_conf.supported_auth_methods[i]);
		if (auth == NULL) {
			unload_auths();
			return 1;
		}
		auths[count++] = auth;
		i++;
	}

	return 0;
}

void
unload_auths(void)
{
	int i = 0;

	if (auths == NULL)
		return;

	while (auths[i] != NULL) {
		_unload_auth(auths[i]);
		auths[i] = NULL;
	}
	free(auths);
	auths = NULL;
}

int
is_valid_encrypt_method(char *method)
{
	int rc = 0;
	auth_def_t *auth = _load_auth(method);

	if (auth && auth->encrypt_data && auth->decrypt_data) {
		rc = 1;
	}

	_unload_auth(auth);
	return rc;
}

/**
 * @brief
 *	tcp_send_auth_req - encodes and sends PBS_BATCH_Authenticate request
 *
 * @param[in] sock - socket descriptor
 *
 * @return	int
 * @retval	0 on success
 * @retval	-1 on error
 */
int
tcp_send_auth_req(int sock, unsigned int port, char *user)
{
	struct batch_reply *reply;
	int rc;
	int am_len = strlen(pbs_conf.auth_method);
	int em_len = strlen(pbs_conf.encrypt_method);

	if (pbs_conf.encrypt_mode != ENCRYPT_DISABLE && em_len == 0) {
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	set_conn_errno(sock, 0);
	set_conn_errtxt(sock, NULL);

	if (encode_DIS_ReqHdr(sock, PBS_BATCH_Authenticate, user) ||
		diswui(sock, am_len) || /* auth method length */
		diswcs(sock, pbs_conf.auth_method, am_len) || /* auth method */
		diswui(sock, pbs_conf.encrypt_mode)) { /* encrypt mode */
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	if (pbs_conf.encrypt_mode != ENCRYPT_DISABLE) {
		if (diswui(sock, em_len) || /* encrypt method length */
			diswcs(sock, pbs_conf.encrypt_method, em_len)) { /* encrypt method */
			pbs_errno = PBSE_SYSTEM;
			return -1;
		}
	}

	if (diswui(sock, port) || /* port (only used in resvport auth) */
		encode_DIS_ReqExtend(sock, NULL)) {
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	if (dis_flush(sock)) {
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	reply = PBSD_rdrpy_sock(sock, &rc);
	if (reply == NULL) {
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	if ((reply->brp_code != 0)) {
		pbs_errno = reply->brp_code;
		set_conn_errno(sock, pbs_errno);
		if (reply->brp_choice == BATCH_REPLY_CHOICE_Text)
			set_conn_errtxt(sock, reply->brp_un.brp_txt.brp_str);
		PBSD_FreeReply(reply);
		return -1;
	}

	PBSD_FreeReply(reply);

	return 0;
}

/*
 * @brief
 *	_invoke_pbs_iff - call pbs_iff(1) to authenticate user/connection to the PBS server.
 *
 * @note
 * This would create an environment variable PBS_IFF_CLIENT_ADDR set to
 * the client's connecting address, which is made known to the pbs_iff process.
 *
 * If unable to authenticate, an attempt is made to run the old method
 * 'pbs_iff -i <pbs_client_addr>' also.
 *
 *
 * @param[in]  psock           Socket descriptor used by PBS client to connect PBS server.
 * @param[in]  server_name     Connecting PBS server host name.
 * @param[in]  server_port     Connecting PBS server port number.
 *
 * @return int
 * @retval  0 on success.
 * @retval -1 on failure.
 */
static int
_invoke_pbs_iff(int psock, char *server_name, int server_port, char *ebuf, size_t ebufsz)
{
	char cmd[2][PBS_MAXSERVERNAME + 80];
	int i;
	int k;
	char *pbs_client_addr = NULL;
	u_short psock_port = 0;
	int rc;
	struct sockaddr_in sockname;
	pbs_socklen_t socknamelen;
#ifdef WIN32
	struct pio_handles pio;
#else
	FILE *piff;
#endif

	socknamelen = sizeof(sockname);
	if (getsockname(psock, (struct sockaddr *)&sockname, &socknamelen))
		return -1;

	pbs_client_addr = inet_ntoa(sockname.sin_addr);
	if (pbs_client_addr == NULL)
		return -1;
	psock_port = sockname.sin_port;

	/* for compatibility with 12.0 pbs_iff */
	(void)snprintf(cmd[1], sizeof(cmd[1]) - 1, "%s -i %s %s %u %d %u", pbs_conf.iff_path, pbs_client_addr, server_name, server_port, psock, psock_port);
#ifdef WIN32
	(void)snprintf(cmd[0], sizeof(cmd[0]) - 1, "%s %s %u %d %u", pbs_conf.iff_path, server_name, server_port, psock, psock_port);
	for (k = 0; k < 2; k++) {
		rc = 0;
		SetEnvironmentVariable(PBS_IFF_CLIENT_ADDR, pbs_client_addr);
		if (!win_popen(cmd[k], "r", &pio, NULL)) {
			fprintf(stderr, "failed to execute %s\n", cmd[k]);
			SetEnvironmentVariable(PBS_IFF_CLIENT_ADDR, NULL);
			rc = -1;
			break;
		}
		win_pread(&pio, (char *)&rc, (int)sizeof(int));
		pbs_errno = rc;
		if (rc > 0) {
			rc = -1;
			win_pread(&pio, (char *)&rc, (int)sizeof(int));
			if (rc > 0) {
				if (rc > (ebufsz - 1))
					rc = ebufsz - 1;
				win_pread(&pio, ebuf, rc);
				ebuf[ebufsz] = '\0';
			}
			rc = -1;
		}
		win_pclose(&pio);
		SetEnvironmentVariable(PBS_IFF_CLIENT_ADDR, NULL);
		if (rc == 0)
			break;
	}

#else	/* UNIX code here */
	(void)snprintf(cmd[0], sizeof(cmd[0]) - 1, "%s=%s %s %s %u %d %u", PBS_IFF_CLIENT_ADDR, pbs_client_addr, pbs_conf.iff_path, server_name, server_port, psock, psock_port);

	for (k = 0; k < 2; k++) {
		rc = -1;
		piff = (FILE *)popen(cmd[k], "r");
		if (piff == NULL) {
			break;
		}

		while ((i = read(fileno(piff), &rc, sizeof(int))) == -1) {
			if (errno != EINTR)
				break;
		}
		pbs_errno = rc;
		if (rc > 0) {
			rc = -1;
			while ((i = read(fileno(piff), &rc, sizeof(int))) == -1) {
				if (errno != EINTR)
					break;
			}
			if (rc > 0) {
				if (rc > (ebufsz - 1))
					rc = ebufsz - 1;
				while ((i = read(fileno(piff), (void *)ebuf, rc)) == -1) {
					if (errno != EINTR)
						break;
				}
				ebuf[ebufsz] = '\0';
			}
			rc = -1;
		}

		(void)pclose(piff);
		if (rc == 0)
			break;
	}
#endif	/* end of UNIX code */

	return rc;
}

static int
_handle_client_handshake(int fd, char *hostname, char *method, int for_encrypt, pbs_auth_config_t *config, char *ebuf, size_t ebufsz)
{
	void *data_in = NULL;
	size_t len_in = 0;
	void *data_out = NULL;
	size_t len_out = 0;
	int type = 0;
	int is_handshake_done = 0;
	void *authctx = NULL;
	auth_def_t *authdef = NULL;

	authdef = get_auth(method);
	if (authdef == NULL) {
		snprintf(ebuf, ebufsz, "Failed to find authdef");
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	DIS_tcp_funcs();

	transport_chan_set_authdef(fd, authdef, for_encrypt);
	authdef->set_config((const pbs_auth_config_t *)config);
	if ((authctx = transport_chan_get_authctx(fd, for_encrypt)) == NULL) {
		if (authdef->create_ctx(&authctx, AUTH_CLIENT, (const char *)hostname)) {
			snprintf(ebuf, ebufsz, "Failed to create auth context");
			pbs_errno = PBSE_SYSTEM;
			return -1;
		}
		transport_chan_set_authctx(fd, authctx, for_encrypt);
	}

	do {
		if (authdef->process_handshake_data(authctx, data_in, len_in, &data_out, &len_out, &is_handshake_done) != 0) {
			if (len_out > 0) {
				size_t len = len_out;
				if (len > ebufsz)
					len = ebufsz;
				strncpy(ebuf, (char *)data_out, len);
				ebuf[len] = '\0';
				free(data_out);
			} else {
				snprintf(ebuf, ebufsz, "auth_process_handshake_data failure");
			}
			pbs_errno = PBSE_SYSTEM;
			return -1;
		}

		if (len_in) {
			free(data_in);
			data_in = NULL;
			len_in = 0;
		}

		if (len_out > 0) {
			if (transport_send_pkt(fd, AUTH_CTX_DATA, data_out, len_out) <= 0) {
				snprintf(ebuf, ebufsz, "Failed to send auth context token");
				pbs_errno = PBSE_SYSTEM;
				free(data_out);
				return -1;
			}
			free(data_out);
			data_out = NULL;
			len_out = 0;
		}

		if (is_handshake_done == 0) {
			/* recieve ctx token */
			if (transport_recv_pkt(fd, &type, &data_in, &len_in) <= 0) {
				snprintf(ebuf, ebufsz, "Failed to receive auth token");
				return -1;
			}

			if (type == AUTH_ERR_DATA) {
				if (len_in > ebufsz)
					len_in = ebufsz;
				strncpy(ebuf, (char *)data_in, len_in);
				ebuf[len_in] = '\0';
				free(data_in);
				pbs_errno = PBSE_BADCRED;
				return -1;
			}

			if (type != AUTH_CTX_DATA) {
				free(data_in);
				snprintf(ebuf, ebufsz, "incorrect auth token type");
				pbs_errno = PBSE_SYSTEM;
				return -1;
			}
		} else {
			transport_chan_set_ctx_status(fd, AUTH_STATUS_CTX_READY, for_encrypt);
			transport_chan_set_authctx(fd, authctx, for_encrypt);
		}

	} while (is_handshake_done == 0);

	return 0;
}

/**
 * @brief
 * 	this function handles client side authenication
 *
 * @param[in] fd - socket descriptor
 * @param[in] hostname - server hostname
 * @param[out] ebuf - error buffer
 * @param[in] ebufsz - size of error buffer
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	failure
 *
 */
int
engage_client_auth(int fd, char *hostname, int port, char *ebuf, size_t ebufsz)
{
	int rc = 0;
	pbs_auth_config_t *config = NULL;

	config = (pbs_auth_config_t *)calloc(1, sizeof(pbs_auth_config_t));
	if (config == NULL) {
		snprintf(ebuf, ebufsz, "Out of memory in %s!", __func__);
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	(void) strcpy(config->auth_method, pbs_conf.auth_method);
	(void) strcpy(config->encrypt_method, pbs_conf.encrypt_method);
	(void) strcpy(config->pbs_exec_path, pbs_conf.pbs_exec_path);
	(void) strcpy(config->pbs_home_path, pbs_conf.pbs_home_path);
	config->logfunc = NULL;
	config->encrypt_mode = pbs_conf.encrypt_mode;

	if (strcmp(pbs_conf.auth_method, AUTH_RESVPORT_NAME) == 0) {
		if ((rc = CS_client_auth(fd)) == CS_SUCCESS)
			return (0);

		if (rc == CS_AUTH_USE_IFF) {
			if (_invoke_pbs_iff(fd, hostname, port, ebuf, ebufsz) != 0) {
				snprintf(ebuf, ebufsz, "Unable to authenticate connection (%s:%d)", hostname, port);
				return -1;
			}
		}
	} else {
		if (tcp_send_auth_req(fd, 0, pbs_current_user) != 0) {
			snprintf(ebuf, ebufsz, "Failed to send auth request");
			return -1;
		}

		rc = _handle_client_handshake(fd, hostname, pbs_conf.auth_method, FOR_AUTH, config, ebuf, ebufsz);
		if (rc != 0)
			return rc;
	}

	if (pbs_conf.encrypt_mode != ENCRYPT_DISABLE) {
		if (pbs_conf.encrypt_method[0] != '\0' && strcmp(pbs_conf.auth_method, pbs_conf.encrypt_method) != 0) {
			return _handle_client_handshake(fd, hostname, pbs_conf.encrypt_method, FOR_ENCRYPT, config, ebuf, ebufsz);
		} else {
			transport_chan_set_ctx_status(fd, transport_chan_get_ctx_status(fd, FOR_AUTH), FOR_ENCRYPT);
			transport_chan_set_authdef(fd, transport_chan_get_authdef(fd, FOR_AUTH), FOR_ENCRYPT);
			transport_chan_set_authctx(fd, transport_chan_get_authctx(fd, FOR_AUTH), FOR_ENCRYPT);
		}
	}
	return 0;
}

/**
 * @brief
 * 	this function handles incoming authenication related data
 *
 * @param[in] fd - socket descriptor
 * @param[in] hostname - server hostname
 * @param[in] clienthost - hostname associate with fd
 * @param[in] for_encrypt - whether to handle incoming data for encrypt/decrypt auth or for authentication
 * @param[out] ebuf - error buffer
 * @param[in] ebufsz - size of error buffer
 *
 * @return	int
 * @retval	0	success
 * @retval	-1	failure
 *
 */
int
engage_server_auth(int fd, char *hostname, char *clienthost, int for_encrypt, char *ebuf, size_t ebufsz)
{
	void *authctx = NULL;
	auth_def_t *authdef = NULL;
	void *data_in = NULL;
	size_t len_in = 0;
	void *data_out = NULL;
	size_t len_out = 0;
	int type;
	int is_handshake_done = 0;

	DIS_tcp_funcs();

	if (transport_chan_get_ctx_status(fd, for_encrypt) != (int)AUTH_STATUS_CTX_ESTABLISHING) {
		/*
		 * auth ctx not establishing
		 * consider data as clear text or encrypted data
		 * BUT not auth ctx data
		 */
		return 1;
	}

	authdef = transport_chan_get_authdef(fd, for_encrypt);
	if (authdef == NULL) {
		snprintf(ebuf, ebufsz, "No authdef associated with connection");
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	if ((authctx = transport_chan_get_authctx(fd, for_encrypt)) == NULL) {
		if (authdef->create_ctx(&authctx, AUTH_SERVER, clienthost)) {
			snprintf(ebuf, ebufsz, "Failed to create auth context");
			pbs_errno = PBSE_SYSTEM;
			return -1;
		}
		transport_chan_set_authctx(fd, authctx, for_encrypt);
	}

	if (transport_recv_pkt(fd, &type, &data_in, &len_in) <= 0) {
		snprintf(ebuf, ebufsz, "failed to receive auth token");
		pbs_errno = PBSE_SYSTEM;
		return -1;
	}

	if (type != AUTH_CTX_DATA) {
		snprintf(ebuf, ebufsz, "received incorrect auth token");
		pbs_errno = PBSE_SYSTEM;
		free(data_in);
		return -1;
	}

	if (authdef->process_handshake_data(authctx, data_in, len_in, &data_out, &len_out, &is_handshake_done) != 0) {
		if (len_out > 0) {
			size_t len = len_out;
			if (len > ebufsz)
				len = ebufsz;
			strncpy(ebuf, (char *)data_out, len);
			ebuf[len] = '\0';
			(void)transport_send_pkt(fd, AUTH_ERR_DATA, data_out, len_out);
			free(data_out);
		} else {
			snprintf(ebuf, ebufsz, "auth_process_handshake_data failure");
		}
		pbs_errno = PBSE_SYSTEM;
		free(data_in);
		return -1;
	}

	free(data_in);

	if (len_out > 0) {
		if (transport_send_pkt(fd, AUTH_CTX_DATA, data_out, len_out) <= 0) {
			snprintf(ebuf, ebufsz, "Failed to send auth context token");
			free(data_out);
			return -1;
		}
	}

	free(data_out);

	if (is_handshake_done == 1) {
		transport_chan_set_ctx_status(fd, AUTH_STATUS_CTX_READY, for_encrypt);
		transport_chan_set_authctx(fd, authctx, for_encrypt);
	}

	if (for_encrypt == FOR_AUTH) {
		auth_def_t *encryptdef = transport_chan_get_authdef(fd, FOR_ENCRYPT);
		if (encryptdef != NULL && encryptdef == authdef) {
			transport_chan_set_ctx_status(fd, AUTH_STATUS_CTX_READY, FOR_ENCRYPT);
			transport_chan_set_authctx(fd, authctx, FOR_ENCRYPT);
		}
	}
	return 0;
}
