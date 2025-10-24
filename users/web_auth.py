import base64

from Crypto.PublicKey import RSA
from Crypto.Cipher import PKCS1_v1_5


ID_RSA_PUB_COOKIE = '''-----BEGIN PUBLIC KEY-----
MIGfMA0GCSqGSIb3DQEBAQUAA4GNADCBiQKBgQCKiUJEGiMR+G8CUjTNUx021gQ9bVQnBDQs7gfC
zIPOuUCiHBF2F+gQqDFl8bXc6SNx/Frx1H+ldXKVqaE50uw+eMYZpU/88a0dzfjbBq2O408b13kU
rL8B+aDsWnYl7zIrk8mQ3VY8Jt2Miwtq3MWJvaCGltkeL3B7C7OgbknJhwIDAQAB
-----END PUBLIC KEY-----'''


def escape_padding(data):
    if data[0] != b'\x01' and data[0] != 1:  # yeah, for the fucking Python3
        return

    pos = data.find(b'\x00')
    if pos == -1:
        raise Exception

    return data[pos+1:]


def encrypt_cookie(value):
    pkey = RSA.importKey(ID_RSA_PUB_COOKIE)
    pkey = PKCS1_v1_5.new(pkey)
    sec = pkey.encrypt(value.encode('utf-8'))
    sec = base64.encodebytes(sec).decode()
    sec = sec.replace('\n', '')

    return sec
