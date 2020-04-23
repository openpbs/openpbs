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
pbs_encrypt_pwd(char *uncrypted, int *credtype, char **crypted, size_t *outlen)
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

        if (EVP_EncryptInit_ex(ctx, EVP_aes_256_cbc(), NULL, (const unsigned char *) pbs_aes_key, (const unsigned char *) pbs_aes_iv) == 0) {
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
pbs_decrypt_pwd(char *crypted, int credtype, size_t len, char **uncrypted)
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

        if (EVP_DecryptInit_ex(ctx, EVP_aes_256_cbc(), NULL, (const unsigned char *) pbs_aes_key, (const unsigned char *) pbs_aes_iv) == 0) {
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
