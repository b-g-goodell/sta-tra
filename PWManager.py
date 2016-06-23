import os
import unittest
import base64
from AESCrypt import AESCrypt
from Crypto.Cipher import AES

class PWManager(object):
    def __init__(self):
        self.filename = "pwm.txt"
        self.self_path = os.path.dirname(os.path.realpath(__file__))
        self.pwm = None
        self.max_count = 5
        self.pwm = self._open_pwm()
        
    def _open_pwm(self):
        temp_pwm = {}
        
        if not os.path.isfile(self.filename):
            open(self.filename, "w").close()
        temp_file = open(self.filename, "r")
        
        lines = temp_file.readlines()
        for line in lines:
            line = line.split("\t")
            assert len(line) >= 3
            aes_key_salts = None
            if len(line)>3:
                aes_key_salts = []
                for k in range(3, len(line)):
                    aes_key_salts.append(base64.b64decode(line[k]))
            temp_pwm[line[0]] = (base64.b64decode(line[1]),base64.b64decode(line[2]), aes_key_salts)
        return temp_pwm
        
    def _write_pwm(self):
        ''' For each entry in our current password manager, write our
        current information to file.
        ''' 
        with open(self.filename,"w") as temp_file:
            temp_pwm = self._open_pwm()
            for username in self.pwm:
                aes_key_salts = None
                password_salt = base64.b64encode(self.pwm[username][0])
                hashed_password = base64.b64encode(self.pwm[username][1])
                if self.pwm[username][2] is not None:
                    aes_key_salts = []
                    for salt in self.pwm[username][2]:
                        aes_key_salts.append(base64.b64encode(salt))
                new_line = username + "\t" + password_salt + "\t" + hashed_password
                if aes_key_salts is not None:
                    for salt in aes_key_salts:
                        new_line += "\t" + salt
                new_line += "\n"
                temp_file.write(new_line)

    def _change_password(self, username):
        print "Welcome user ", username, ", what would you like to be your new password?."
        success = None
        black_box = AESCrypt()
        salt = os.urandom(black_box.salt_length)
        password_verified = False
        while(not password_verified):
            hashed_password = black_box.hash_passphrase(raw_input("New user please enter a password:\t"), salt)
            check_hashed_password = black_box.hash_passphrase(raw_input("Re-enter password to verify:\t"), salt)
            password_verified = (hashed_password == check_hashed_password)
            if not password_verified:
                print "Woops, passwords didn't match. Try again."
        self.pwm[username] = []
        self.pwm[username].append(hashed_password)
        self.pwm[username].append(salt)
        self.pwm[username].append(None)
        
        self._write_pwm()
        return password_verified
        
    def _check_password(self, username=None):
        if username is not None:
            count = 1
            black_box = AESCrypt()
            hashed_password = self.pwm[username][0]
            salt = self.pwm[username][1] 
            alleged_hashed_password = black_box.hash_passphrase(raw_input("password:\t"), salt)
            success = (hashed_password == alleged_hashed_password)
            while not success and count < self.max_count:
                count += 1
                alleged_hashed_password = black_box.hash_passphrase(raw_input("incorrect password, try again:\t"), salt)
                success = (hashed_password == alleged_hashed_password)
        return success, username
        
    def prompt_user_for_login_info(self, username=None):
        assert self.pwm is not None
        if username is None:
            username = raw_input("user:\t")
        success = None
        if username not in self.pwm.keys():
            success = self._change_password(username)
        else:
            success, username = self._check_password(username)
        return success, username
        
        
    #def add_aes_keys(self, username):
    #    print "Okay, ", username, ", let's generate some AES keys."
    #    num_keys_to_generate = int(raw_input( \
    #        "How many files do you need to encrypt? (integer)")
    #    self._che
    #    while num_keys_to_generate > 0:
    #        num_keys_to_generate -= 1


class Test_PWManager(unittest.TestCase):
    def test_pwmanager(self):
        print "Testing Paul the password manager. Paul should be empty so the first username you enter should definitely require a new password."
        paul = PWManager()
        success = paul.prompt_user_for_login_info()
        self.assertTrue(success)
        print "Testing adding a user directly with username \"test username\""
        success = paul._change_password("test username")
        self.assertTrue(success)
        print "Let's try logging in as \"test username\" with the password you just provided."
        success, username = paul.prompt_user_for_login_info("test username")
        self.assertTrue(success)
        print "Let's try failing to log in as \"test username\" with a different password."
        success, username = paul.prompt_user_for_login_info("test username")
        self.assertFalse(success)

suite = unittest.TestLoader().loadTestsFromTestCase(Test_PWManager)
unittest.TextTestRunner(verbosity=1).run(suite)

