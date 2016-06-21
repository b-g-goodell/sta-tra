import os
import unittest
from AESCrypt import AESCrypt
from Crypto.Cipher import AES

class PWManager(object):
    def __init__(self):
        self.filename = "pwm.txt"
        self.self_path = os.path.dirname(os.path.realpath(__file__))
        self.pwm = None
        self._open_pwm()
        pass
        
    def _open_pwm(self):
        if not os.path.isfile(self.filename):
            open(self.filename, "w").close()
        temp_file = open(self.filename, "r")
        
        lines = temp_file.readlines()
        self.pwm = {}
        for line in lines:
            line = line.split()
            if len(line)==3:
                self.pwm[line[0]] = (line[1],line[2])
            else:
                break
        pass
        
    def _write_pwm(self):
        temp_file = open(self.filename, "r")
        lines = temp_file.readlines()
        temp_file.close()
        temp_pwm = {}
        for line in lines:
            line = line.split()
            if len(line)==3:
                temp_pwm[line[0]] = (line[1],line[2])
        temp_file = open(self.filename,"wa")
        for username in self.pwm:
            if username not in temp_pwm:
                new_line = username + " " + self.pwm[username][0] + " " + self.pwm[username][1] + "\n"
                temp_file.write(new_line)
        temp_file.close()
        pass
        
    def prompt_user_for_login_info(self, username=None):
        assert self.pwm != None
        if username == None:
            username = raw_input("user:\t")
        success = None
        if username not in self.pwm.keys():
            success = self._add_user(username)
        else:
            black_box = AESCrypt()
            hashed_password = self.pwm[username][0]
            salt = self.pwm[username][1] 
            alleged_hashed_password = black_box.hash_passphrase(raw_input("password:\t"), salt)
            success = ( hashed_password == alleged_hashed_password)
        return success
        
    def _add_user(self, username):
        print "Welcome user ", username, ", time for you to pick a password."
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
        
        self._write_pwm()
        return password_verified


class Test_PWManager(unittest.TestCase):
    def test_pwmanager(self):
        print "Testing Paul the password manager. Paul should be empty so the first username you enter should definitely require a new password."
        paul = PWManager()
        self.assertTrue(len(paul.pwm.keys()) == 0)
        success = paul.prompt_user_for_login_info()
        self.assertTrue(len(paul.pwm.keys()) == 1)
        self.assertTrue(success)
        print "Testing adding a user directly with username \"test username\""
        success = paul._add_user("test username")
        self.assertTrue(len(paul.pwm.keys()) == 2)
        self.assertTrue(success)
        #print "
        #paul.prompt_user_for_login_info()
        print "Let's try logging in as \"test username\" with the password you just provided."
        success = paul.prompt_user_for_login_info("test username")
        self.assertTrue(len(paul.pwm.keys()) == 2)
        self.assertTrue(success)
        print "Let's try failing to log in as \"test username\" with a different password."
        success = paul.prompt_user_for_login_info("test username")
        if not success:
            print "Incorrect username or password."
        self.assertTrue(len(paul.pwm.keys()) == 2)
        self.assertFalse(success)

suite = unittest.TestLoader().loadTestsFromTestCase(Test_PWManager)
unittest.TextTestRunner(verbosity=1).run(suite)

