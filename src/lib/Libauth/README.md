***This file explains about LibAuth API Interface descriptions and design...***

# pbs_auth_set_config
 - **Synopsis:** void pbs_auth_set_config(void (*logfunc)(int type, int objclass, int severity, const char *objname, const char *text), char *cred_location)
 - **Description:** This API sets configuration for the authentication library like logging method, where it can find required credentials... This API should be called first before calling any other LibAuth API.
 - **Arguments:**

	- void (*logfunc)(int type, int objclass, int severity, const char *objname, const char *text)

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Function pointer to the logging method with the same signature as log_event from Liblog. With this, the user of the authentication library can redirect logs from the authentication library into respective log files or stderr in case no log files. If func is set to NULL then logs will be written to stderr (if available, else no logging at all).

	- char *cred_location

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Path to the location where the authentication library can find the required credentials. This should be a null-terminated string.

 - **Return Value:** None, void

# pbs_auth_create_ctx
 - **Synopsis:** int pbs_auth_create_ctx(void **ctx, int mode)
 - **Description:** This API creates an authentication context for a given mode, which will be used by other LibAuth API for authentication, encrypt and decrypt data.
 - **Arguments:**

	- void **ctx

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Pointer to auth context to be created

	- int mode

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Specify which type of context to be created, should be one of AUTH_CLIENT or AUTH_SERVER.

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Use AUTH_CLIENT for client-side (aka who is initiating authentication) context

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Use AUTH_SERVER for server-side (aka who is authenticating incoming user/connection) context

 - **Return Value:** Integer

	- 0 - On Success

	- 1 - On Failure

 - **Cleanup:** A context created by this API should be destroyed by auth_free_ctx when the context is no more required

# pbs_auth_destroy_ctx
 - **Synopsis:** void pbs_auth_destroy_ctx(void *ctx)
 - **Description:** This API destroys the authentication context created by pbs_auth_create_ctx
 - **Arguments:**

	- void *ctx

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Pointer to auth context to be destroyed

 - **Return Value:** None, void

# pbs_auth_get_userinfo
 - **Synopsis:** int pbs_auth_get_userinfo(void *ctx, char **user, char **host, char **realm)
 - **Description:** Extract username and its realm, hostname of the connecting party from the given authentication context. Extracted user, host and realm values will be a null-terminated string. This API is mostly useful on authenticating server-side to get another party (aka auth client) information and the auth server might want to use this information from the auth library to match against the actual username/realm/hostname provided by the connecting party.
 - **Arguments:**

	- void *ctx

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Pointer to auth context from which information will be extracted

	- char **user

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Pointer to a buffer in which this API will write the user name

	- char **host

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Pointer to a buffer in which this API will write hostname

	- char **realm

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Pointer to a buffer in which this API will write the realm

 - **Return Value:** Integer

	- 0 - On Success

	- 1 - On Failure

 - **Cleanup:** Returned user, host, and realm should be freed using free() when no more required, as it will be allocated heap memory.

# pbs_auth_process_handshake_data
 - **Synopsis:** int pbs_auth_process_handshake_data(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out, int *is_handshake_done)
 - **Description:** Process incoming handshake data and do the handshake, and if required generate handshake data which will be sent to another party. If there is no incoming data then initiate a handshake and generate initial handshake data to be sent to the authentication server.
 - **Arguments:**

	- void *ctx

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Pointer to auth context for which handshake is happening

	- void *data_in

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Incoming handshake data to process if any. This can be NULL which indicates to initiate handshake and generate initial handshake data to be sent to the authentication server.

	- size_t len_in

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Length of incoming handshake data if any, else 0

	- void **data_out

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Outgoing handshake data to be sent to another authentication party, this can be NULL is handshake is completed and no further data needs to be sent.

	- size_t *len_out

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Length of outgoing handshake data if any, else 0

	- int *is_handshake_done

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;To indicate whether handshake is completed or not, 0 - means handshake is not completed or 1 - means handshake is completed

 - **Return Value:** Integer

	- 0 - On Success

	- 1 - On Failure

 - **Cleanup:** Returned data_out (if any) should be freed using free() when no more required, as it will be allocated heap memory.

# pbs_auth_encrypt_data
 - **Synopsis:** int pbs_auth_encrypt_data(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out)
 - **Description:** Encrypt given clear text data with the given authentication context
 - **Arguments:**

	- void *ctx

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Pointer to auth context which will be used while encrypting given clear text data

	- void *data_in

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;clear text data to encrypt

	- size_t len_in

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Length of clear text data

	- void **data_out

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Encrypted data

	- size_t *len_out

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Length of encrypted data

 - **Return Value:** Integer

	- 0 - On Success

	- 1 - On Failure

 - **Cleanup:** Returned data_out should be freed using free() when no more required, as it will be allocated heap memory.

# pbs_auth_decrypt_data
 - **Synopsis:** int pbs_auth_decrypt_data(void *ctx, void *data_in, size_t len_in, void **data_out, size_t *len_out)
 - **Description:** Decrypt given encrypted data with the given authentication context
 - **Arguments:**

	- void *ctx

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Pointer to auth context which will be used while decrypting given encrypted data

	- void *data_in

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Encrypted data to decrypt

	- size_t len_in

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Length of Encrypted data

	- void **data_out

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;clear text data

	- size_t *len_out

		&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Length of clear text data

 - **Return Value:** Integer

	- 0 - On Success

	- 1 - On Failure

 - **Cleanup:** Returned data_out should be freed using free() when no more required, as it will be allocated heap memory.
