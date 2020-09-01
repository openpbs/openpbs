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
#include <pbs_config.h>
#include <arpa/inet.h>
#include <assert.h>
#include <errno.h>
#include <stdlib.h>
#include "auth.h"
#include "dis.h"
#include "pbs_error.h"
#include "pbs_internal.h"

#define PKT_MAGIC    "PKTV1"
#define PKT_MAGIC_SZ sizeof(PKT_MAGIC)
#define PKT_HDR_SZ   (PKT_MAGIC_SZ + 1 + sizeof(int))

static pbs_dis_buf_t *dis_get_readbuf(int);
static pbs_dis_buf_t *dis_get_writebuf(int);
static int dis_resize_buf(pbs_dis_buf_t *, size_t);
static int transport_chan_is_encrypted(int);

pbs_tcp_chan_t * (*pfn_transport_get_chan)(int);
int (*pfn_transport_set_chan)(int, pbs_tcp_chan_t *);
int (*pfn_transport_recv)(int, void *, int);
int (*pfn_transport_send)(int, void *, int);

/**
 * @brief
 * 	transport_chan_set_ctx_status - set auth context status tcp chan assosiated with given fd
 *
 * @param[in] fd - file descriptor
 * @param[in] status - auth ctx status
 * @param[in] for_encrypt - is authctx for encrypt/decrypt?
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
transport_chan_set_ctx_status(int fd, int status, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);

	if (chan == NULL)
		return;
	chan->auths[for_encrypt].ctx_status = status;
}

/**
 * @brief
 * 	transport_chan_get_ctx_status - get auth context status tcp chan assosiated with given fd
 *
 * @param[in] fd - file descriptor
 * @param[in] for_encrypt - whether to get encrypt/decrypt authctx status or for authentication
 *
 * @return int
 *
 * @retval -1 - error
 * @retval !-1 - status
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
transport_chan_get_ctx_status(int fd, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);

	if (chan == NULL)
		return -1;
	return chan->auths[for_encrypt].ctx_status;
}

/**
 * @brief
 * 	transport_chan_set_authctx - associates authenticaion context with connection
 *
 * @param[in] fd - file descriptor
 * @param[in] authctx - the context
 * @param[in] for_encrypt - is authctx for encrypt/decrypt?
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
transport_chan_set_authctx(int fd, void *authctx, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);

	if (chan == NULL)
		return;
	chan->auths[for_encrypt].ctx = authctx;
}

/**
 * @brief
 * 	transport_chan_get_authctx - gets authentication context associated with connection
 *
 * @param[in] fd - file descriptor
 * @param[in] for_encrypt - whether to get encrypt/decrypt authctx or for authentication
 *
 * @return void *
 *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void *
transport_chan_get_authctx(int fd, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);

	if (chan == NULL)
		return NULL;
	return chan->auths[for_encrypt].ctx;
}

/**
 * @brief
 * 	transport_chan_set_authdef - associates authdef structure with connection
 *
 * @param[in] fd - file descriptor
 * @param[in] authdef - the authdef structure for association
 * @param[in] for_encrypt - is authdef for encrypt/decrypt?
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
transport_chan_set_authdef(int fd, auth_def_t *authdef, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);

	if (chan == NULL)
		return;
	chan->auths[for_encrypt].def = authdef;
}

/**
 * @brief
 * 	transport_chan_get_authdef - gets authdef structure associated with connection
 *
 * @param[in] fd - file descriptor
 * @param[in] for_encrypt - whether to get encrypt/decrypt authdef or for authentication
 *
 * @return auth_def_t *
 *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
auth_def_t *
transport_chan_get_authdef(int fd, int for_encrypt)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);

	if (chan == NULL)
		return NULL;
	return chan->auths[for_encrypt].def;
}

/**
 * @brief
 * 	transport_chan_is_encrypted - is chan assosiated with given fd is encrypted?
 *
 * @param[in] fd - file descriptor
 *
 * @return int
 *
 * @retval 0 - not encrypted
 * @retval 1 - encrypted
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
transport_chan_is_encrypted(int fd)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);

	if (chan == NULL)
		return 0;
	return (chan->auths[FOR_ENCRYPT].def != NULL && chan->auths[FOR_ENCRYPT].ctx_status == AUTH_STATUS_CTX_READY);
}

/**
 * @brief
 * 	send pkt from given DIS buffer over network
 * 	after patching pkt header for data size and
 * 	if not encrypted already and chan is encrypted
 * 	then encrypt data before send
 *
 * @param[in] fd - file descriptor
 * @param[in] tp - pointer to DIS buffer
 * @param[in] encrypt_done - is data already encrypted
 *
 * @return int
 *
 * @retval >= 0  - success
 * @retval -1 - failure
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
__send_pkt(int fd, pbs_dis_buf_t *tp, int encrypt_done)
{
	int i;

	if (!encrypt_done && transport_chan_is_encrypted(fd)) {
		void *authctx = transport_chan_get_authctx(fd, FOR_ENCRYPT);
		auth_def_t *authdef = transport_chan_get_authdef(fd, FOR_ENCRYPT);
		void *data_out;
		size_t len_out;

		if (authdef == NULL || authdef->encrypt_data == NULL)
			return -1;

		if (authdef->encrypt_data(authctx, (void *)(tp->tdis_data + PKT_HDR_SZ), tp->tdis_len - PKT_HDR_SZ, &data_out, &len_out) != 0)
			return -1;

		dis_resize_buf(tp, len_out + PKT_HDR_SZ);
		memcpy((void *)(tp->tdis_data + PKT_HDR_SZ), data_out, len_out);
		free(data_out);
		tp->tdis_len = len_out + PKT_HDR_SZ;
	}

	i = htonl(tp->tdis_len - PKT_HDR_SZ);
	memcpy((void *) (tp->tdis_data + PKT_HDR_SZ - sizeof(int)), &i, sizeof(int));

	i = transport_send(fd, (void *) tp->tdis_data, tp->tdis_len);
	if (i < 0)
		return i;
	if (i != tp->tdis_len)
		return -1;
	dis_clear_buf(tp);
	return i;
}

/**
 * @brief
 * 	create pkt based on given value
 * 	and send it over network. If channel for given fd is
 * 	encrypted then given data will be encrypted first
 * 	then pkt will be sent
 *
 * @param[in] fd - file descriptor
 * @param[in] type - type of pkt
 * @param[in] data_in - data of pkt
 * @param[in] len_in - length of data
 *
 * @return int
 *
 * @retval >= 0  - success
 * @retval -1 - failure
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
transport_send_pkt(int fd, int type, void *data_in, size_t len_in)
{
	pbs_dis_buf_t *tp;

	if (data_in == NULL || len_in == 0 || (tp = dis_get_writebuf(fd)) == NULL)
		return -1;

	dis_clear_buf(tp);
	dis_resize_buf(tp, len_in + PKT_HDR_SZ);
	strcpy(tp->tdis_data, PKT_MAGIC);
	*(tp->tdis_data + PKT_MAGIC_SZ) = (char) type;
	tp->tdis_pos = tp->tdis_data + PKT_HDR_SZ;

	if (transport_chan_is_encrypted(fd)) {
		void *authctx = transport_chan_get_authctx(fd, FOR_ENCRYPT);
		auth_def_t *authdef = transport_chan_get_authdef(fd, FOR_ENCRYPT);
		void *data_out;
		size_t len_out;

		if (authdef == NULL || authdef->encrypt_data == NULL)
			return -1;

		if (authdef->encrypt_data(authctx, data_in, len_in, &data_out, &len_out) != 0)
			return -1;

		dis_resize_buf(tp, len_out + PKT_HDR_SZ);
		memcpy(tp->tdis_pos, data_out, len_out);
		free(data_out);
		tp->tdis_len = len_out;
	} else {
		memcpy(tp->tdis_pos, data_in, len_in);
		tp->tdis_len = len_in;
	}
	tp->tdis_len += PKT_HDR_SZ;

	return __send_pkt(fd, tp, 1);
}

/**
 * @brief
 * 	receive pkt in given DIS buffer from network
 * 	If channel for given fd is encrypted then decrypt data
 * 	in received pkt
 *
 * @param[in] fd - file descriptor
 * @param[out] type - type of pkt
 * @param[in/out] tp - pointer to DIS buffer
 *
 * @return int
 *
 * @retval >= 0  - success
 * @retval -1 - failure
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
__recv_pkt(int fd, int *type, pbs_dis_buf_t *tp)
{
	int i;
	size_t datasz;
	char pkthdr[PKT_HDR_SZ];

	dis_clear_buf(tp);
	i = transport_recv(fd, (void *) &pkthdr, PKT_HDR_SZ);
	if (i != PKT_HDR_SZ)
		return (i < 0 ? i : -1);
	if (strncmp(pkthdr, PKT_MAGIC, PKT_MAGIC_SZ) != 0) {
		/* no pkt magic match, reject data/connection */
		return -1;
	}

	*type = (int) pkthdr[PKT_MAGIC_SZ];
	memcpy(&i, (void *) &(pkthdr[PKT_HDR_SZ - sizeof(int)]), sizeof(int));
	datasz = ntohl(i);
	if (datasz <= 0)
		return -1;
	dis_resize_buf(tp, datasz);
	i = transport_recv(fd, tp->tdis_data, datasz);
	if (i != datasz)
		return (i < 0 ? i : -1);

	if (transport_chan_is_encrypted(fd)) {
		void *data;
		void *authctx = transport_chan_get_authctx(fd, FOR_ENCRYPT);
		auth_def_t *authdef = transport_chan_get_authdef(fd, FOR_ENCRYPT);

		if (authdef == NULL || authdef->decrypt_data == NULL)
			return -1;

		if (authdef->decrypt_data(authctx, tp->tdis_data, i, &data, &datasz) != 0)
			return -1;

		free(tp->tdis_data);
		tp->tdis_data = data;
		tp->tdis_bufsize = datasz;
	}
	tp->tdis_pos = tp->tdis_data;
	tp->tdis_len = datasz;
	return datasz;
}

/**
 * @brief
 * 	transport_recv_pkt - receive pkt over network.
 * 	If channel for given fd is encrypted then decrypt it
 * 	and parse pkt to find pkt type, data and its length
 *
 * 	@warning returned data should not be free'd as it is
 * 		 internal dis buffer
 *
 * @param[in] fd - file descriptor
 * @param[out] type - type of pkt
 * @param[out] data_out - data of pkt
 * @param[out] len_out - length of data
 *
 * @return int
 *
 * @retval >= 0  - success
 * @retval -1 - failure
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
transport_recv_pkt(int fd, int *type, void **data_out, size_t *len_out)
{
	int i;
	pbs_dis_buf_t *tp = dis_get_readbuf(fd);

	*type = 0;
	*data_out = NULL;
	*len_out = 0;

	if (tp == NULL)
		return -1;
	i = __recv_pkt(fd, type, tp);
	if (i <= 0)
		return i;
	*data_out = (void *) tp->tdis_data;
	*len_out = i;
	dis_clear_buf(tp);
	return *len_out;
}

/**
 * @brief
 * 	dis_get_readbuf - get dis read buffer associated with connection
 *
 * @return pbs_dis_but_t *
 *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static pbs_dis_buf_t *
dis_get_readbuf(int fd)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);

	if (chan == NULL)
		return NULL;
	return &(chan->readbuf);
}

/**
 * @brief
 * 	dis_get_writebuf - get dis write buffer associated with connection
 *
 * @return pbs_dis_but_t *
 *
 * @retval !NULL - success
 * @retval NULL - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static pbs_dis_buf_t *
dis_get_writebuf(int fd)
{
	pbs_tcp_chan_t *chan = transport_get_chan(fd);

	if (chan == NULL)
		return NULL;
	return &(chan->writebuf);
}

/**
 * @brief
 * 	dis_resize_buf - resize given dis buffer to appropriate size based on given needed
 *
 * 	if use_lead is true then it will use tdis_lead to calculate new size else tdis_eod
 *
 * @param[in] tp - dis buffer to pack
 * @param[in] needed - min needed buffer size
 *
 * @return int
 *
 * @retval 0 - success
 * @retval -1 - error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
static int
dis_resize_buf(pbs_dis_buf_t *tp, size_t needed)
{
	if ((tp->tdis_len + needed) >= tp->tdis_bufsize) {
		int offset = tp->tdis_len > 0 ? (tp->tdis_pos - tp->tdis_data) : 0;
		char *tmpcp = (char *) realloc(tp->tdis_data, tp->tdis_bufsize + needed + PBS_DIS_BUFSZ);
		if (tmpcp == NULL) {
			return -1; /* realloc failed */
		} else {
			tp->tdis_data = tmpcp;
			tp->tdis_bufsize = tp->tdis_bufsize + needed + PBS_DIS_BUFSZ;
			tp->tdis_pos = tp->tdis_data + offset;
		}
	}
	return 0;
}

/**
 * @brief
 * 	dis_clear_buf - reset dis buffer to empty by updating its counter
 *
 *
 * @param[in] tp - dis buffer to clear
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
dis_clear_buf(pbs_dis_buf_t *tp)
{
	tp->tdis_pos = tp->tdis_data;
	tp->tdis_len = 0;
}

/**
 * @brief
 * 	dis_reset_buf - reset appropriate dis buffer associated with connection
 *
 * @param[in] fd - file descriptor
 * @param[in] rw - reset write buffer if true else read buffer
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
dis_reset_buf(int fd, int rw)
{
	dis_clear_buf((rw == DIS_WRITE_BUF) ? dis_get_writebuf(fd) : dis_get_readbuf(fd));
}

/**
 * @brief
 * 	disr_skip - dis suport routine to skip over data in read buffer
 *
 * @param[in] fd - file descriptor
 * @param[in] ct - count
 *
 * @return	int
 *
 * @retval	number of characters skipped
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
disr_skip(int fd, size_t ct)
{
	pbs_dis_buf_t *tp = dis_get_readbuf(fd);

	if (tp == NULL)
		return 0;
	if (ct > tp->tdis_len)
		dis_clear_buf(tp);
	else {
		tp->tdis_pos += ct;
		tp->tdis_len -= ct;
	}
	return (int) ct;
}

/**
 * @brief
 * 	dis_getc - dis support routine to get next character from read buffer
 *
 * @param[in] fd - file descriptor
 *
 * @return	int
 *
 * @retval	>0 	number of characters read
 * @retval	-1 	if EOD or error
 * @retval	-2 	if EOF (stream closed)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
dis_getc(int fd)
{
	pbs_dis_buf_t *tp = dis_get_readbuf(fd);
	int c;

	if (tp == NULL)
		return -1;
	if (tp->tdis_len <= 0) {
		/* not enought data, try to get more */
		int unused;

		dis_clear_buf(tp);
		if ((c = __recv_pkt(fd, &unused, tp)) <= 0) {
			dis_clear_buf(tp);
			return c;  /* Error or EOF */
		}
	}
	c = *tp->tdis_pos;
	tp->tdis_pos++;
	tp->tdis_len--;
	return c;
}

/**
 * @brief
 * 	dis_gets - dis support routine to get a string from read buffer
 *
 * @param[in] fd - file descriptor
 * @param[in] str - string to be written
 * @param[in] ct - count
 *
 * @return	int
 *
 * @retval	>0 	number of characters read
 * @retval	0 	if EOD (no data currently avalable)
 * @retval	-1 	if error
 * @retval	-2 	if EOF (stream closed)
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
dis_gets(int fd, char *str, size_t ct)
{
	pbs_dis_buf_t *tp = dis_get_readbuf(fd);

	if (tp == NULL) {
		*str = '\0';
		return -1;
	}
	if (ct == 0) {
		*str = '\0';
		return ct;
	}
	if (tp->tdis_len <= 0) {
		/* not enought data, try to get more */
		int unused;
		int c;

		if ((c = __recv_pkt(fd, &unused, tp)) <= 0) {
			dis_clear_buf(tp);
			return c;  /* Error or EOF */
		}
	}
	memcpy(str, tp->tdis_pos, ct);
	tp->tdis_pos += ct;
	tp->tdis_len -= ct;
	return (int) ct;
}

/**
 * @brief
 * 	dis_puts - dis support routine to put a counted string of characters
 *	into the write buffer.
 *
 * @param[in] fd - file descriptor
 * @param[in] str - string to be written
 * @param[in] ct - count
 *
 * @return	int
 *
 * @retval	>= 0	the number of characters placed
 * @retval	-1 	if error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
dis_puts(int fd, const char *str, size_t ct)
{
	pbs_dis_buf_t *tp = dis_get_writebuf(fd);

	if (tp == NULL)
		return -1;
	if (tp->tdis_len <= 0) {
		if (dis_resize_buf(tp, ct + PKT_HDR_SZ) != 0)
			return -1;
		strcpy(tp->tdis_data, PKT_MAGIC);
		tp->tdis_pos = tp->tdis_data + PKT_HDR_SZ;
		tp->tdis_len = PKT_HDR_SZ;
	} else {
		if (dis_resize_buf(tp, ct) != 0)
			return -1;
	}
	memcpy(tp->tdis_pos, str, ct);
	tp->tdis_pos += ct;
	tp->tdis_len += ct;
	return ct;
}

/**
 * @brief
 *	flush dis write buffer
 *
 *	Writes "committed" data in buffer to file descriptor,
 *	packs remaining data (if any), resets pointers
 *
 * @param[in] - fd - file descriptor
 *
 * @return int
 *
 * @retval  0 on success
 * @retval -1 on error
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
int
dis_flush(int fd)
{
	pbs_dis_buf_t *tp = dis_get_writebuf(fd);

	if (tp == NULL)
		return -1;
	if (tp->tdis_len == 0)
		return 0;
	if (__send_pkt(fd, tp, 0) <= 0)
		return -1;
	return 0;
}

/**
 * @brief
 * 	dis_destroy_chan - release structures associated with fd
 *
 * @param[in] fd - socket descriptor
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
dis_destroy_chan(int fd)
{
	pbs_tcp_chan_t *chan = NULL;

	if (pfn_transport_get_chan == NULL)
		return;
	chan = transport_get_chan(fd);
	if (chan != NULL) {
		if (chan->auths[FOR_AUTH].ctx || chan->auths[FOR_ENCRYPT].ctx) {
			/* DO NOT free authdef here, it will be done in unload_auths() */
			if (chan->auths[FOR_AUTH].ctx && chan->auths[FOR_AUTH].def) {
				chan->auths[FOR_AUTH].def->destroy_ctx(chan->auths[FOR_AUTH].ctx);
			}
			if (chan->auths[FOR_ENCRYPT].def != chan->auths[FOR_AUTH].def &&
			    chan->auths[FOR_ENCRYPT].ctx &&
			    chan->auths[FOR_ENCRYPT].def) {
				chan->auths[FOR_ENCRYPT].def->destroy_ctx(chan->auths[FOR_ENCRYPT].ctx);
			}
			chan->auths[FOR_AUTH].ctx = NULL;
			chan->auths[FOR_AUTH].def = NULL;
			chan->auths[FOR_AUTH].ctx_status = AUTH_STATUS_UNKNOWN;
			chan->auths[FOR_ENCRYPT].ctx = NULL;
			chan->auths[FOR_ENCRYPT].def = NULL;
			chan->auths[FOR_ENCRYPT].ctx_status = AUTH_STATUS_UNKNOWN;
		}
		if (chan->readbuf.tdis_data) {
			free(chan->readbuf.tdis_data);
			chan->readbuf.tdis_data = NULL;
		}
		if (chan->writebuf.tdis_data) {
			free(chan->writebuf.tdis_data);
			chan->writebuf.tdis_data = NULL;
		}
		free(chan);
		transport_set_chan(fd, NULL);
	}
}

/**
 * @brief
 *	allocate dis buffers associated with connection, if already allocated then clear it
 *
 * @param[in] fd - file descriptor
 *
 * @return void
 *
 * @par Side Effects:
 *	None
 *
 * @par MT-safe: Yes
 *
 */
void
dis_setup_chan(int fd, pbs_tcp_chan_t *(*inner_transport_get_chan)(int) )
{
	pbs_tcp_chan_t *chan;
	int rc;

	/* check for bad file descriptor */
	if (fd < 0)
		return;
	chan = (pbs_tcp_chan_t *) (*inner_transport_get_chan)(fd);
	if (chan == NULL) {
		if (errno == ENOTCONN)
			return;
		chan = (pbs_tcp_chan_t *) calloc(1, sizeof(pbs_tcp_chan_t));
		assert(chan != NULL);
		dis_resize_buf(&(chan->readbuf), PBS_DIS_BUFSZ);
		dis_resize_buf(&(chan->writebuf), PBS_DIS_BUFSZ);
		rc = transport_set_chan(fd, chan);
		assert(rc == 0);
	}

	/* initialize read and write buffers */
	dis_clear_buf(&(chan->readbuf));
	dis_clear_buf(&(chan->writebuf));
}
