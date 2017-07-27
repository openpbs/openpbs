#include <stdio.h>
#include <stdlib.h>
#include <ctype.h>
#include <memory.h>
#include <string.h>
#include <stdlib.h>

#include <openssl/evp.h>
#include <openssl/aes.h>
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
#define CIPHER_CONTEXT_INIT(v) v = EVP_CIPHER_CTX_new(); if (!v) return -1;
#define CIPHER_CONTEXT_CLEAN(v) EVP_CIPHER_CTX_free(v)
#endif

/**
 * @brief
 *	Encrypt the input string using AES encryption. The keys are rotated
 *	for each block of data equal to the size of each key.
 *
 * @param[in]	uncrypted - The input data to encrypt
 * @param[out]	credtype  - The credential type
 * @param[in]	len 	  - Length of input data to be encrypted
 * @param[out]	credbuf	  - The buffer containing the encrypted data
 * @param[out]	outlen	  - Length of the buffer containing encrypted data
 *
 * @return      int
 * @retval	-1 - Failure
 * @retval	 0 - Success
 *
 */
int
pbs_encrypt_data(char *uncrypted, int *credtype, size_t len, char **crypted, size_t *outlen)
{
        int plen, len2 = 0;
        char *cblk;

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

        if (EVP_EncryptUpdate(ctx, cblk, &plen, uncrypted, len) == 0) {
                CIPHER_CONTEXT_CLEAN(ctx);
                free(cblk);
                return -1;
        }

        if (EVP_EncryptFinal_ex(ctx, cblk + plen, &len2) == 0) {
                CIPHER_CONTEXT_CLEAN(ctx);
                free(cblk);
                return -1;
        }

        CIPHER_CONTEXT_CLEAN(ctx);

        *crypted = cblk;
        *outlen = plen + len2;
        *credtype = PBS_CREDTYPE_AES;

        return 0;
}

/*
 * Convenience wrapper for encrypting a string password
 */
int
pbs_encrypt_pwd(char *str, int *credtype, char **credbuf, size_t *credlen)
{
        return pbs_encrypt_data(str, credtype, strlen(str) + 1, credbuf, credlen);
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
 * @param[out]  outlen    - The length of the decrypted data
 *
 * @return      int
 * @retval	-1 - Failure
 * @retval	 0 - Success
 *
 */
int
pbs_decrypt_data(char *crypted, int credtype, size_t len, char **uncrypted, size_t *outlen)
{
        char *cblk;
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

        if (EVP_DecryptUpdate(ctx, cblk, &plen, crypted, len) == 0) {
                CIPHER_CONTEXT_CLEAN(ctx);
                free(cblk);
                return -1;
        }

        if (EVP_DecryptFinal_ex(ctx, cblk + plen, &len2) == 0) {
                CIPHER_CONTEXT_CLEAN(ctx);
                free(cblk);
                return -1;
        }

        CIPHER_CONTEXT_CLEAN(ctx);

        *uncrypted = cblk;
        *outlen = plen + len2;

        return 0;
}

/*
 * Convenience wrapper for encrypting a string password
 */
int
pbs_decrypt_pwd(char *crypted, int credtype, size_t len, char **str)
{
        size_t outlen;
        int ret;

        if ((ret = pbs_decrypt_data(crypted, credtype, len, str, &outlen)) == 0)
                (*str)[outlen] = 0; /* set a null character at the end */

        return ret;
}
