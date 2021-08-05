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

#include <pbs_config.h>

#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <memory.h>
#include <string.h>
#include <stdlib.h>

#include <openssl/evp.h>
#include <openssl/aes.h>
#include <openssl/bio.h>
#include <openssl/buffer.h>
#include <openssl/sha.h>
#include "ticket.h"
/**
 * @file	pbs_aes_encrypt.c
 */
extern unsigned char pbs_aes_key[];
extern unsigned char pbs_aes_iv[];

#if OPENSSL_VERSION_NUMBER < 0x10100000L
#define CIPHER_CONTEXT_INIT(v) EVP_CIPHER_CTX_init(v)
#define CIPHER_CONTEXT_CLEAN(v) EVP_CIPHER_CTX_cleanup(v)
#else
#define CIPHER_CONTEXT_INIT(v) v = EVP_CIPHER_CTX_new(); if (!v) return -1
#define CIPHER_CONTEXT_CLEAN(v) EVP_CIPHER_CTX_cleanup(v);EVP_CIPHER_CTX_free(v)
#endif

/**
 * @brief
 *	Encrypt the input string using AES encryption. The keys are rotated
 *	for each block of data equal to the size of each key.
 *
 * @param[in]	uncrypted - The input data to encrypt
 * @param[out]	credtype  - The credential type
 * @param[out]	credbuf	  - The buffer containing the encrypted data
 * @param[out]	outlen	  - Length of the buffer containing encrypted data
 *
 * @return      int
 * @retval	-1 - Failure
 * @retval	 0 - Success
 *
 */
int
pbs_encrypt_pwd(char *uncrypted, int *credtype, char **crypted, size_t *outlen, const unsigned char *aes_key, const unsigned char *aes_iv)
{
        int plen, len2 = 0;
        unsigned char *cblk;
        size_t len = strlen(uncrypted) + 1;

#if OPENSSL_VERSION_NUMBER < 0x10100000L
        EVP_CIPHER_CTX real_ctx;
        EVP_CIPHER_CTX *ctx = &real_ctx;
#else
        EVP_CIPHER_CTX *ctx = NULL;
#endif

        CIPHER_CONTEXT_INIT(ctx);

        if (EVP_EncryptInit_ex(ctx, EVP_aes_256_cbc(), NULL, (const unsigned char *) aes_key, (const unsigned char *) aes_iv) == 0) {
                CIPHER_CONTEXT_CLEAN(ctx);
                return -1;
        }

        plen = len + EVP_CIPHER_CTX_block_size(ctx) + 1;
        cblk = malloc(plen);
        if (!cblk) {
                CIPHER_CONTEXT_CLEAN(ctx);
                return -1;
        }

        if (EVP_EncryptUpdate(ctx, cblk, &plen, (unsigned char *)uncrypted, len) == 0) {
                CIPHER_CONTEXT_CLEAN(ctx);
                free(cblk);
                cblk = NULL;
                return -1;
        }

        if (EVP_EncryptFinal_ex(ctx, cblk + plen, &len2) == 0) {
                CIPHER_CONTEXT_CLEAN(ctx);
                free(cblk);
                cblk = NULL;
                return -1;
        }

        CIPHER_CONTEXT_CLEAN(ctx);

        *crypted = (char *)cblk;
        *outlen = plen + len2;
        *credtype = PBS_CREDTYPE_AES;

        return 0;
}

/**
 * @brief
 *	Decrypt the encrypted input data using AES decryption.
 *	The keys are rotated for each block of data equal to size of each key.
 *
 * @param[in]	crypted   - The encrypted data to decrypt
 * @param[in]   credtype  - The credential type
 * @param[in]	len	      - The length of crypted
 * @param[out]	uncrypted - The decrypted data
 *
 * @return      int
 * @retval	-1 - Failure
 * @retval	 0 - Success
 *
 */
int
pbs_decrypt_pwd(char *crypted, int credtype, size_t len, char **uncrypted, const unsigned char *aes_key, const unsigned char *aes_iv)
{
        unsigned char *cblk;
        int plen, len2 = 0;

#if OPENSSL_VERSION_NUMBER < 0x10100000L
        EVP_CIPHER_CTX real_ctx;
        EVP_CIPHER_CTX *ctx = &real_ctx;
#else
        EVP_CIPHER_CTX *ctx = NULL;
#endif

        CIPHER_CONTEXT_INIT(ctx);

        if (EVP_DecryptInit_ex(ctx, EVP_aes_256_cbc(), NULL, (const unsigned char *) aes_key, (const unsigned char *) aes_iv) == 0) {
                CIPHER_CONTEXT_CLEAN(ctx);
                return -1;
        }

        cblk = malloc(len + EVP_CIPHER_CTX_block_size(ctx) + 1);
        if (!cblk) {
                CIPHER_CONTEXT_CLEAN(ctx);
                return -1;
        }

        if (EVP_DecryptUpdate(ctx, cblk, &plen, (unsigned char *)crypted, len) == 0) {
                CIPHER_CONTEXT_CLEAN(ctx);
                free(cblk);
                cblk = NULL;
                return -1;
        }

        if (EVP_DecryptFinal_ex(ctx, cblk + plen, &len2) == 0) {
                CIPHER_CONTEXT_CLEAN(ctx);
                free(cblk);
                cblk = NULL;
                return -1;
        }

        CIPHER_CONTEXT_CLEAN(ctx);

        *uncrypted = (char *)cblk;
        (*uncrypted)[plen + len2] = '\0';

        return 0;
}

/**
 * @brief
 *	encode_to_base64 - Encode data into base64 format
 *
 * @param[in]		buffer			-	Data buffer for encoding
 * @param[in]		buffer_len		-	Length of the data buffer
 * @param[in/out]	ret_encoded_data	-	Return the encoded data
 *
 * @return int
 * @retval 0 - for success
 * @retval 1 - for failure
 */
int
encode_to_base64(const unsigned char* buffer, size_t buffer_len, char** ret_encoded_data)
{
	BIO *mem_obj1, *mem_obj2;
	long buf_len = 0;
	char *buf;

	mem_obj1 = BIO_new(BIO_s_mem());
	if (mem_obj1 == NULL)
		return 1;
	mem_obj2 = BIO_new(BIO_f_base64());
	if (mem_obj2 == NULL) {
		BIO_free(mem_obj1);
		return 1;
	}

	mem_obj1 = BIO_push(mem_obj2, mem_obj1);
	BIO_set_flags(mem_obj1, BIO_FLAGS_BASE64_NO_NL);
	BIO_write(mem_obj1, buffer, buffer_len);
	(void)BIO_flush(mem_obj1);
	buf_len = BIO_get_mem_data(mem_obj1, &buf);
	if (buf_len <= 0)
		return 1;
	*ret_encoded_data = (char *)malloc(buf_len + 1);
	if (*ret_encoded_data == NULL) {
		BIO_free_all(mem_obj1);
		return 1;
	}
	memcpy(*ret_encoded_data, buf, buf_len);
	(*ret_encoded_data)[buf_len] = '\0';

	BIO_free_all(mem_obj1);
	return 0;
}

/**
 * @brief
 *	decode_from_base64 - Decode data from base64 format
 *
 * @param[in]		buffer			-	Data buffer for decoding
 * @param[in/out]	ret_decoded_data	-	Return the decoded data
 * @param[in/out]	ret_decoded_len		-	Return length of the decoded data
 *
 * @return int
 * @retval 0 - for success
 * @retval 1 - for failure
 */
int
decode_from_base64(char* buffer, unsigned char** ret_decoded_data, size_t* ret_decoded_len)
{
	BIO *mem_obj1, *mem_obj2;
	size_t decode_length = 0;
	size_t input_len = 0;
	size_t char_padding = 0;
	int padding_enabled = 1;

	input_len = strlen(buffer);
	if (input_len == 0)
		return 1;
	if ((buffer[input_len - 1] == '=') && (buffer[input_len - 2] == '=')) {
		char_padding = 2;
		padding_enabled = 0;
	}
	if (padding_enabled) {
		if (buffer[input_len - 1] == '=')
			char_padding = 1;
	}
	decode_length = ((input_len * 3)/4 - char_padding);
	*ret_decoded_data = (unsigned char*)malloc(decode_length + 1);
	if (*ret_decoded_data == NULL)
		return 1;
	(*ret_decoded_data)[decode_length] = '\0';

	mem_obj1 = BIO_new_mem_buf(buffer, -1);
	if (mem_obj1 == NULL)
		return 1;
	mem_obj2 = BIO_new(BIO_f_base64());
	if (mem_obj2 == NULL) {
		BIO_free_all(mem_obj1);
		return 1;
	}

	mem_obj1 = BIO_push(mem_obj2, mem_obj1);
	BIO_set_flags(mem_obj1, BIO_FLAGS_BASE64_NO_NL);
	*ret_decoded_len = BIO_read(mem_obj1, *ret_decoded_data, strlen(buffer));

	if (*ret_decoded_len != decode_length) {
		BIO_free_all(mem_obj1);
		return 1;
	}
	BIO_free_all(mem_obj1);
	return 0;
}
/** @brief
 *	encode_SHA - Returns the hexadecimal hash.
 *
 *	@param[in] : str - token to hash
 *	@param[in] : len - length of the
 *	@param[in] ebufsz - size of ebuf
 *	@return	int
 *	@retval 1 on error
 *			0 on success
 */

void
encode_SHA(char* token, size_t cred_len, char ** hex_digest)
{
    unsigned char obuf[SHA_DIGEST_LENGTH] = {'\0'};
    int i;

    SHA1((const unsigned char*)token, cred_len, obuf);
    for (i = 0; i < SHA_DIGEST_LENGTH; i++) {
        sprintf((char*) (*hex_digest + (i*2)) , "%02x", obuf[i] );
    }
}
