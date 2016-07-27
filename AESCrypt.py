import os
import unittest
from pbkdf2 import PBKDF2
from Crypto.Cipher import AES
import base64


class AESCrypt(object):
    def __init__(self):
        self.blocksize = 32
        self.iv_length = 16
        self.salt_length = 8
        self.self_path = os.path.dirname(os.path.realpath(__file__))

    def _pad(self, s):
        pad_val = self.blocksize - len(s) % self.blocksize
        return s + pad_val*chr(pad_val)

    def encrypt(self, message, key, mode=AES.MODE_CFB):
        message = self._pad(message)
        iv = os.urandom(self.iv_length)
        cipher = AES.new(key,mode,iv)
        ciphertext = base64.b64encode(iv + cipher.encrypt(message))
        return ciphertext

    def decrypt(self, ciphertext, key, mode=AES.MODE_CFB):
        ciphertext = base64.b64decode(ciphertext)
        iv = ciphertext[:self.iv_length]
        cipher = AES.new(key,mode,iv)
        message = self._unpad((cipher.decrypt(ciphertext[self.iv_length:])).decode('utf-8'))
        return message

    def passphrase_encrypt(self, message, passphrase, salt, bits_to_read=32, mode=AES.MODE_CFB):
        assert salt != None
        key = self.hash_passphrase(passphrase, salt, bits_to_read)
        return self.encrypt(message,key,mode)

    def passphrase_decrypt(self,ciphertext,passphrase,salt, bits_to_read=32, mode=AES.MODE_CFB):
        assert salt != None
        key = self.hash_passphrase(passphrase, salt, bits_to_read)
        return self.decrypt(ciphertext, key, mode)

    @staticmethod
    def hash_passphrase(passphrase, salt, bits_to_read=32):
        assert salt != None
        key = PBKDF2(passphrase, salt).read(bits_to_read)
        return key

    @staticmethod
    def _unpad(s):
        pad_val = -ord(s[len(s)-1:])
        return s[:pad_val:]


class Test_AESCrypt(unittest.TestCase):
    def test_aescrypt(self):
        black_box = AESCrypt()
        plaintext = "hello world"
        secret_password = "secret password"
        salt = os.urandom(black_box.salt_length)
        ciphertext = black_box.passphrase_encrypt(plaintext, secret_password, salt, bits_to_read=32, \
            mode=AES.MODE_CFB)
        alleged_plaintext = black_box.passphrase_decrypt(ciphertext, secret_password, salt, bits_to_read=32, \
            mode=AES.MODE_CFB)
        print "plaintext:\t", plaintext
        print "alleged plaintext:\t", alleged_plaintext
        self.assertTrue(plaintext == alleged_plaintext)

    def test_hash_passphrase(self):
        print "Testing hash passphrase:\n"
        black_box = AESCrypt()
        salt = "0000"
        #print "salt = ", salt
        #print "type(salt) = ", type(salt)
        passphrase = "tulip"
        #print "passphrase = ", passphrase
        self.assertTrue("55ITBnbO1lxle02Ey/sjlalWDOnYzLFQN8+27HUlsZg=" == base64.b64encode( \
            black_box.hash_passphrase(passphrase, salt)))

        salt = "0001"
        #print "salt = ", salt
        #print "type(salt) = ", type(salt)
        passphrase = "tulip"
        #print "passphrase = ", passphrase
        self.assertTrue("T5POFcwZConeMtv9dYOHgMkOlXwq18xLTMfN1Sgc3Ik=" == base64.b64encode( \
            black_box.hash_passphrase(passphrase, salt)))

suite = unittest.TestLoader().loadTestsFromTestCase(Test_AESCrypt)
unittest.TextTestRunner(verbosity=1).run(suite)
