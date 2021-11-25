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

#include <stdlib.h>
#include <stdio.h>
#include <string.h>
#include <krb5.h>

#include "base64.h"

#define VAR_NAME_KEYTAB "PBS_RENEW_KRB_KEYTAB"

static krb5_error_code
prepare_ccache(krb5_context context, krb5_creds *creds, krb5_ccache *cc)
{
	krb5_error_code ret;
	krb5_ccache ccache = NULL;

	ret = krb5_cc_new_unique(context, "MEMORY", NULL, &ccache);
	if (ret) {
		fprintf(stderr, "krb5_cc_new_unique() failed (%s)",
			krb5_get_error_message(context, ret));
		goto end;
	}

	ret = krb5_cc_initialize(context, ccache, creds->client);
	if (ret) {
		fprintf(stderr, "krb5_cc_initialize() failed (%s)",
			krb5_get_error_message(context, ret));
		goto end;
	}

	ret = krb5_cc_store_cred(context, ccache, creds);
	if (ret) {
		fprintf(stderr, "krb5_cc_store_cred() failed (%s)",
			krb5_get_error_message(context, ret));
		goto end;
	}

	*cc = ccache;
	ccache = NULL;

end:
	if (ccache)
		krb5_cc_destroy(context, ccache);

	return ret;
}

static krb5_error_code
get_init_creds_user(krb5_context context, const char *username, krb5_creds *creds)
{
	krb5_error_code ret;
	krb5_get_init_creds_opt *opt = NULL;
	krb5_keytab keytab = NULL;
	krb5_principal user = NULL;

	ret = krb5_parse_name(context, username, &user);
	if (ret) {
		fprintf(stderr, "Parsing user principal (%s) failed: %s.\n",
			username, krb5_get_error_message(context, ret));
		goto end;
	}

	if (getenv(VAR_NAME_KEYTAB))
		ret = krb5_kt_resolve(context, getenv(VAR_NAME_KEYTAB), &keytab);
	else
		ret = krb5_kt_default(context, &keytab);
	if (ret) {
		fprintf(stderr, "Cannot open keytab: %s\n",
			krb5_get_error_message(context, ret));
		goto end;
	}

	ret = krb5_get_init_creds_opt_alloc(context, &opt);
	if (ret) {
		fprintf(stderr, "krb5_get_init_creds_opt_alloc() failed (%s)\n",
			krb5_get_error_message(context, ret));
		goto end;
	}

	krb5_get_init_creds_opt_set_forwardable(opt, 1);

	ret = krb5_get_init_creds_keytab(context, creds, user, keytab, 0, NULL, opt);
	if (ret) {
		fprintf(stderr, "krb5_get_init_creds_keytab() failed (%s)\n",
			krb5_get_error_message(context, ret));
		goto end;
	}

end:
	if (opt)
		krb5_get_init_creds_opt_free(context, opt);
	if (user)
		krb5_free_principal(context, user);
	if (keytab)
		krb5_kt_close(context, keytab);

	return (ret);
}

static krb5_error_code
init_auth_context(krb5_context context, krb5_auth_context *auth_context)
{
	int32_t flags;
	krb5_error_code ret;

	ret = krb5_auth_con_init(context, auth_context);
	if (ret) {
		fprintf(stderr, "krb5_auth_con_init() failed: %s.\n",
			krb5_get_error_message(context, ret));
		return ret;
	}

	krb5_auth_con_getflags(context, *auth_context, &flags);
	/* We disable putting times in the message so the message could be cached
	   and re-sent in the future. If caching isn't needed, it could be enabled
	   again (but read below) */
	/* N.B. The semantics of KRB5_AUTH_CONTEXT_DO_TIME applied in
	   krb5_fwd_tgt_creds() seems to differ between Heimdal and MIT. MIT uses
	   it to (also) enable replay cache checks (that are useless and
	   troublesome for us). Heimdal uses it to just specify whether or not the
	   timestamp is included in the forwarded message. */
	flags &= ~(KRB5_AUTH_CONTEXT_DO_TIME);
#ifdef HEIMDAL
	/* With Heimdal, we need explicitly set that the credential is in cleartext.
	 * MIT does not have the flag KRB5_AUTH_CONTEXT_CLEAR_FORWARDED_CRED */
	flags |= KRB5_AUTH_CONTEXT_CLEAR_FORWARDED_CRED;
#endif
	krb5_auth_con_setflags(context, *auth_context, flags);

	return 0;
}

/* Creates a KRB_CRED message containing serialized credentials. The credentials
   aren't encrypted, relying on the protection by application protocol, see RFC 6448 */
static krb5_error_code
get_fwd_creds(krb5_context context, krb5_creds *creds, krb5_data *creds_data)
{
	krb5_error_code ret;
	krb5_auth_context auth_context = NULL;
	krb5_ccache ccache = NULL;

	ret = init_auth_context(context, &auth_context);
	if (ret)
		goto end;

	ret = prepare_ccache(context, creds, &ccache);
	if (ret)
		goto end;

	/* It's necessary to pass a hostname to pass the code (Heimdal segfaults
	 * otherwise), MIT tries to get a credential for the host if session keys
	 * doesn't exist. It should be noted that the krb5 configuration should set
	 * the no-address flags for tickets (otherwise tickets couldn't be cached,
	 * wouldn't work with multi-homed machines etc.).
     */
	ret = krb5_fwd_tgt_creds(context, auth_context, "localhost", creds->client,
				 NULL, ccache, 1, creds_data);
	if (ret) {
		fprintf(stderr, "krb5_fwd_tgt_creds() failed: %s.\n",
			krb5_get_error_message(context, ret));
		goto end;
	}

end:
	if (auth_context)
		krb5_auth_con_free(context, auth_context);
	if (ccache)
		krb5_cc_destroy(context, ccache);

	return (ret);
}

static int
output_creds(krb5_context context, krb5_creds *target_creds)
{
	krb5_error_code ret;
	krb5_auth_context auth_context = NULL;
	krb5_creds **creds = NULL, **c;
	char *encoded = NULL;
	krb5_data _creds_data, *creds_data = &_creds_data;

	memset(&_creds_data, 0, sizeof(_creds_data));

	ret = get_fwd_creds(context, target_creds, creds_data);
	if (ret)
		goto end;

	ret = init_auth_context(context, &auth_context);
	if (ret)
		goto end;

	encoded = k5_base64_encode(creds_data->data, creds_data->length);
	if (encoded == NULL) {
		fprintf(stderr, "failed to encode the credentials, exiting.\n");
		ret = -1;
		goto end;
	}

	ret = krb5_rd_cred(context, auth_context, creds_data, &creds, NULL);
	if (ret) {
		fprintf(stderr, "krb5_rd_cred() failed: %s.\n",
			krb5_get_error_message(context, ret));
		goto end;
	}

	printf("Type: Kerberos\n");
	/* there might be multiple credentials exported, which we silently ignore */
	printf("Valid until: %ld\n", (long int) creds[0]->times.endtime);
	printf("%s\n", encoded);

	ret = 0;

end:
	krb5_free_data_contents(context, &_creds_data);
	if (auth_context)
		krb5_auth_con_free(context, auth_context);
	if (encoded)
		free(encoded);
	if (creds) {
		for (c = creds; c != NULL && *c != NULL; c++)
			krb5_free_creds(context, *c);
		free(creds);
	}

	return (ret);
}

static int
doit(const char *user)
{
	int ret;
	krb5_creds my_creds;
	krb5_context context = NULL;

	memset((char *) &my_creds, 0, sizeof(my_creds));

	ret = krb5_init_context(&context);
	if (ret) {
		fprintf(stderr, "Cannot initialize Kerberos, exiting.\n");
		return (ret);
	}

	ret = get_init_creds_user(context, user, &my_creds);
	if (ret)
		goto end;

	ret = output_creds(context, &my_creds);

end:
	krb5_free_cred_contents(context, &my_creds);
	krb5_free_context(context);

	return (ret);
}

int
main(int argc, char *argv[])
{
	char *progname;
	int ret;

	if ((progname = strrchr(argv[0], '/')))
		progname++;
	else
		progname = argv[0];

	if (argc != 2) {
		fprintf(stderr, "Usage: %s principal_name\n", progname);
		exit(1);
	}

	ret = doit(argv[1]);

	if (ret != 0)
		ret = 1;
	return (ret);
}
