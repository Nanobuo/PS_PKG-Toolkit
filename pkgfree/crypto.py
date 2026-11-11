"""Cryptographic primitives used by PS4 fake PKGs."""

import hashlib
import hmac
import struct

from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from . import keys
from .i18n import tr

XTS_SECTOR_SIZE = 0x1000


class CryptoError(Exception):
    pass


def _rsa_decrypt_pkcs1v15(ciphertext: bytes, n: int, d: int) -> bytes:
    """Raw RSA decryption followed by PKCS#1 v1.5 (type 2) unpadding."""
    c = int.from_bytes(ciphertext, "big")
    if c >= n:
        raise CryptoError(tr("Testo cifrato RSA fuori intervallo"))
    em = pow(c, d, n).to_bytes(256, "big")
    if em[0] != 0 or em[1] != 2:
        raise CryptoError(tr("RSA padding non valido (PKG retail o chiave errata)"))
    sep = em.find(b"\x00", 2)
    if sep < 10:
        raise CryptoError(tr("RSA padding non valido (PKG retail o chiave errata)"))
    return em[sep + 1:]


def decrypt_dk3(ciphertext: bytes) -> bytes:
    return _rsa_decrypt_pkcs1v15(ciphertext, keys.PKG_DERIVED_KEY3_N, keys.PKG_DERIVED_KEY3_D)[:32]


def decrypt_ekpfs(ciphertext: bytes) -> bytes:
    return _rsa_decrypt_pkcs1v15(ciphertext, keys.FAKE_N, keys.FAKE_D)[:32]


def entry_iv_key(entry_raw: bytes, dk3: bytes) -> bytes:
    """SHA-256 over the 32-byte table entry followed by DK3: first 16 bytes IV, last 16 key."""
    return hashlib.sha256(entry_raw + dk3).digest()


def aes_cbc_decrypt(iv_key: bytes, data: bytes) -> bytes:
    usable = len(data) - (len(data) % 16)
    dec = Cipher(algorithms.AES(iv_key[16:32]), modes.CBC(iv_key[:16])).decryptor()
    return dec.update(data[:usable]) + dec.finalize() + data[usable:]


def pfs_gen_crypto_key(ekpfs: bytes, seed: bytes, new_crypt: bool = False) -> tuple[bytes, bytes]:
    """Derive the (data_key, tweak_key) pair of the PFS image."""
    if new_crypt:
        ekpfs = hmac.new(ekpfs, seed, hashlib.sha256).digest()
    digest = hmac.new(ekpfs, struct.pack("<I", 1) + seed, hashlib.sha256).digest()
    tweak_key, data_key = digest[:16], digest[16:32]
    return data_key, tweak_key


class XtsDecryptor:
    """AES-128-XTS with 0x1000-byte sectors, as used by encrypted PFS images."""

    def __init__(self, data_key: bytes, tweak_key: bytes):
        self._key = algorithms.AES(data_key + tweak_key)

    def decrypt(self, data: bytes, first_sector: int) -> bytes:
        if len(data) % XTS_SECTOR_SIZE:
            raise CryptoError("XTS data must be sector aligned")
        out = bytearray(len(data))
        view = memoryview(data)
        for i in range(0, len(data), XTS_SECTOR_SIZE):
            tweak = (first_sector + i // XTS_SECTOR_SIZE).to_bytes(16, "little")
            dec = Cipher(self._key, modes.XTS(tweak)).decryptor()
            out[i:i + XTS_SECTOR_SIZE] = dec.update(view[i:i + XTS_SECTOR_SIZE])
        return bytes(out)


# -- encryption side (used to build PKGs) --------------------------------------------

_SHA256_DIGEST_INFO = bytes.fromhex("3031300d060960864801650304020105000420")


class _MersenneTwister:
    """MT19937 seeded with an array (init_by_array), as used by LibOrbisPkg."""

    def __init__(self, key: list[int]):
        n = 624
        mt = [0] * n
        mt[0] = 19650218
        for i in range(1, n):
            mt[i] = (1812433253 * (mt[i - 1] ^ (mt[i - 1] >> 30)) + i) & 0xFFFFFFFF
        i, j = 1, 0
        for _ in range(max(n, len(key))):
            mt[i] = ((mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1664525)) + key[j] + j) & 0xFFFFFFFF
            i, j = i + 1, j + 1
            if i >= n:
                mt[0], i = mt[n - 1], 1
            if j >= len(key):
                j = 0
        for _ in range(n - 1):
            mt[i] = ((mt[i] ^ ((mt[i - 1] ^ (mt[i - 1] >> 30)) * 1566083941)) - i) & 0xFFFFFFFF
            i += 1
            if i >= n:
                mt[0], i = mt[n - 1], 1
        mt[0] = 0x80000000
        self._mt, self._i = mt, n

    def next(self) -> int:
        mt, n = self._mt, 624
        if self._i >= n:
            for k in range(n):
                y = (mt[k] & 0x80000000) | (mt[(k + 1) % n] & 0x7FFFFFFF)
                mt[k] = mt[(k + 397) % n] ^ (y >> 1) ^ (0x9908B0DF if y & 1 else 0)
            self._i = 0
        y = mt[self._i]
        self._i += 1
        y ^= y >> 11
        y ^= (y << 7) & 0x9D2C5680
        y ^= (y << 15) & 0xEFC60000
        y ^= y >> 18
        return y


def rsa_encrypt_key(data: bytes, n: int, e: int = 0x10001) -> bytes:
    """RSA-2048 encryption of a 32-byte value with PKCS#1 v1.5 type 2 padding.

    The padding comes from a PRNG seeded with the key and the value, like LibOrbisPkg,
    so the same input always gives the same output.
    """
    if len(data) != 32:
        raise CryptoError("RSA key encryption expects 32 bytes")
    modulus = n.to_bytes(256, "big")
    seed = hashlib.sha256(hashlib.sha256(modulus + data).digest()).digest()
    mt = _MersenneTwister(list(struct.unpack(">8I", seed)))
    em = bytearray(256)
    em[1] = 2
    em[224:] = data
    k = 2
    while k < 223:
        rnd = hashlib.sha256(struct.pack(">12I", *(mt.next() for _ in range(12)))).digest()
        for r in rnd:
            if k >= 223:
                break
            if r:
                em[k] = r
                k += 1
    return pow(int.from_bytes(em, "big"), e, n).to_bytes(256, "big")


def rsa_sign_sha256(digest: bytes, n: int, d: int) -> bytes:
    """PKCS#1 v1.5 signature of a SHA-256 digest."""
    t = _SHA256_DIGEST_INFO + digest
    em = b"\x00\x01" + b"\xff" * (256 - 3 - len(t)) + b"\x00" + t
    return pow(int.from_bytes(em, "big"), d, n).to_bytes(256, "big")


def aes_cbc_encrypt(iv_key: bytes, data: bytes) -> bytes:
    """Counterpart of aes_cbc_decrypt (same IV/key split, trailing partial block kept)."""
    usable = len(data) - (len(data) % 16)
    enc = Cipher(algorithms.AES(iv_key[16:32]), modes.CBC(iv_key[:16])).encryptor()
    return enc.update(data[:usable]) + enc.finalize() + data[usable:]


def aes_cbc_encrypt_raw(key: bytes, iv: bytes, data: bytes) -> bytes:
    enc = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
    return enc.update(data) + enc.finalize()


class XtsEncryptor:
    def __init__(self, data_key: bytes, tweak_key: bytes):
        self._key = algorithms.AES(data_key + tweak_key)

    def encrypt(self, data: bytes, first_sector: int) -> bytes:
        if len(data) % XTS_SECTOR_SIZE:
            raise CryptoError("XTS data must be sector aligned")
        out = bytearray(len(data))
        view = memoryview(data)
        for i in range(0, len(data), XTS_SECTOR_SIZE):
            tweak = (first_sector + i // XTS_SECTOR_SIZE).to_bytes(16, "little")
            enc = Cipher(self._key, modes.XTS(tweak)).encryptor()
            out[i:i + XTS_SECTOR_SIZE] = enc.update(view[i:i + XTS_SECTOR_SIZE])
        return bytes(out)
