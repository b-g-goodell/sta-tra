import os
import unittest
import base64
from AESCrypt import AESCrypt
from Crypto.Cipher import AES

class API_Key_Manager(object):
    def __init__(self):
        self.self_path = os.path.dirname(os.path.realpath(__file__))
        self.key_manager = {}
        self.this_user = {}
        # self.this_user has keys 'username', 'user_id', 'pwd_salt',
        # 'hashed_pwd', and 'api_keys'
        
    def get_api_keys(self):
        success, username = self.login()
        result = None
        if success:
            result = self.this_user['api_keys']
        return result
        
    def login(self, username = None):
        success = None
        if username is None:
            username = raw_input("user:\t")
        self.this_user['username'] = username
        self.this_user['user_id'] = self._get_user_id(username)
        self._open_key_manager()
        if username in self.key_manager:
            assert self.this_user['user_id'] == self.key_manager[username]['user_id']
            self.this_user['pwd_salt'] = self.key_manager[username]['pwd_salt']
            self.this_user['hashed_pwd'] = self.key_manager[username]['hashed_pwd']            
            self.this_user['aes_key_salts'] = self.key_manager[username]['aes_key_salts']
            success = self._encrypted_file_and_pwd_to_api_keys(username)
        else:
            black_box = AESCrypt()
            self.key_manager[username] = {}
            self.key_manager[username]['user_id'] = self.this_user['user_id']
            self.key_manager[username]['pwd_salt'] = base64.b64encode(os.urandom(black_box.salt_length))
            self.this_user['pwd_salt'] = self.key_manager[username]['pwd_salt']
            success = self._pwd_and_api_keys_to_encrypted_file(username)
            self._update_key_manager_file()
        return success, username
            
    def _update_key_manager_file(self):
        filename = self.self_path  + "/key_manager/key_manager.txt"
        with open(filename, "w") as key_manager_file:
            for username in self.key_manager:
                newline = username + "\t" + self.key_manager[username]['user_id'] + "\t" + self.key_manager[username]['pwd_salt'] + "\t" + self.key_manager[username]['hashed_pwd']
                for salt in self.key_manager[username]['aes_key_salts']:
                    newline = newline + "\t" + salt
                key_manager_file.write(newline + "\n")
        
    def _get_user_id(self, username=None):
        assert username is not None
        black_box = AESCrypt()
        user_id_salt = "00000000000="
        user_id = base64.b64encode(black_box.hash_passphrase(username,user_id_salt, bits_to_read=32))
        return user_id
        
    def _open_key_manager(self):
        filename = self.self_path  + "/key_manager/key_manager.txt"
        if not os.path.isfile(filename):
            open(filename, "w").close()
        with open(filename, "r") as key_manager_file:
            lines = key_manager_file.readlines()
            if len(lines) != 0:
                for line in lines:
                    if len(line) != 0:
                        line.rstrip()
                        line = line.split("\t")
                        username = line[0]
                        user_id = self._get_user_id(username)
                        assert user_id == line[1]
                        
                        self.key_manager[username] = {}
                        self.key_manager[username]['user_id'] = user_id
                        self.key_manager[username]['pwd_salt'] = line[2]
                        self.key_manager[username]['hashed_pwd'] = line[3]
                        self.key_manager[username]['aes_key_salts'] = line[4:]
            
    def _encrypted_file_and_pwd_to_api_keys(self, username):
        success = None
        black_box = AESCrypt()
        user_id_code = self.this_user['user_id']
        aes_key_salts = self.this_user['aes_key_salts']
        pwd = raw_input("password:\t")
        hpwd = base64.b64encode(black_box.hash_passphrase(pwd, self.this_user['pwd_salt'], bits_to_read=32))
        count = 0
        success = ((hpwd == self.this_user['hashed_pwd']) or count >= self.max_count)
        while not success:
            count += 1
            pwd = raw_input("Wrong password, try again:\t")
            hpwd = base64.b64encode(black_box.hash_passphrase(pwd, self.this_user['pwd_salt'], bits_to_read=32))
        if success:
            api_keys = []
            for salt in self.key_manager[username]['aes_key_salts']:
                salt_code = salt
                user_id_code = ''.join([i for i in user_id_code if i.isalpha()])
                user_id_code = user_id_code[:4]
                salt_code = ''.join([i for i in salt_code if i.isalpha()])
                salt_code = salt_code[:4]
                filename = self.self_path + "/key_manager/" +  user_id_code + "." + salt_code + "." + str(self.key_manager[username]['aes_key_salts'].index(salt)) + ".txt"
                with open(filename, "r") as aes_file:
                    encrypted_data = aes_file.read()
                    api_keys.append(black_box.passphrase_decrypt(base64.b64decode(encrypted_data), pwd, base64.b64decode(salt)))
            self.this_user['api_keys'] = api_keys
        return success
        
    def _pwd_and_api_keys_to_encrypted_file(self, username=None, api_keys = [None, None]):
        success = None
        black_box = AESCrypt()
        if username is not None:
            if api_keys[0] is None and api_keys[1] is None:
                print "Okay, let's encrypt some API keys which come in pairs."
                self.this_user['api_keys'] = []
                self.this_user['api_keys'].append(raw_input("What's the first API key?\t"))
                self.this_user['api_keys'].append(raw_input("What's the second API key?\t"))
            else:
                self.this_user['api_keys'] = [api_keys[0], api_keys[1]]
                
            self.this_user['aes_key_salts'] = [base64.b64encode(os.urandom(black_box.salt_length)), base64.b64encode(os.urandom(black_box.salt_length))]
            self.key_manager[username]['aes_key_salts'] = self.this_user['aes_key_salts']
            pwd = raw_input("Password?\t")
            vpwd = raw_input("Verify password?\t")
            while pwd != vpwd:
                pwd = raw_input("Passwords didn't match. Try again. Password?\t")
                vpwd = raw_input("Verify password?\t")
            
            self.this_user['hashed_pwd'] = base64.b64encode(black_box.hash_passphrase(pwd, self.this_user['pwd_salt'], bits_to_read=32))
            self.key_manager[username]['hashed_pwd'] = self.this_user['hashed_pwd']
            
            user_id_code = self.this_user['user_id']
            user_id_code = ''.join([i for i in user_id_code if i.isalpha()])
            user_id_code = user_id_code[:4]
            
            salt_codes = [None,None]
            salt_codes[0] = self.this_user['aes_key_salts'][0]
            salt_codes[0] = ''.join([i for i in salt_codes[0] if i.isalpha()])
            salt_codes[0] = salt_codes[0][:4]
            salt_codes[1] = self.this_user['aes_key_salts'][1]
            salt_codes[1] = ''.join([i for i in salt_codes[1] if i.isalpha()])
            salt_codes[1] = salt_codes[1][:4]
            
            plaintext_one = self.this_user['api_keys'][0]
            salt_one = base64.b64decode(self.this_user['aes_key_salts'][0])
            plaintext_two = self.this_user['api_keys'][1]
            salt_two = base64.b64decode(self.this_user['aes_key_salts'][1])
            
            encrypted_data = [base64.b64encode(black_box.passphrase_encrypt(plaintext_one, pwd, salt_one)), base64.b64encode(black_box.passphrase_encrypt(plaintext_two, pwd, salt_two))]
             
            filenames = [None, None]
            filenames[0] = self.self_path + "/key_manager/" + user_id_code + "." + salt_codes[0] + ".0.txt"
            filenames[1] = self.self_path + "/key_manager/" + user_id_code + "." + salt_codes[1] + ".1.txt"
            #if not os.path.isfile(filenames[0]):
            #    open(filenames[0], "w").close()
            with open(filenames[0], "w") as temp_file:
                temp_file.write(encrypted_data[0])
            with open(filenames[1],"w") as temp_file:
                temp_file.write(encrypted_data[1])
                            
        return success
        

#class Test_API_Key_Manager(unittest.TestCase):
#    def test_api_key_manager(self):
#        abed = API_Key_Manager()
#        abed.login()
#        api_keys = abed.get_api_keys()
#        print api_keys
        
#suite = unittest.TestLoader().loadTestsFromTestCase(Test_API_Key_Manager)
#unittest.TextTestRunner(verbosity=1).run(suite)
