import os
import unittest
import base64
from AESCrypt import AESCrypt
from Crypto.Cipher import AES

class API_Key_Manager(object):
	def __init__(self):

		self.self_path = os.path.dirname(os.path.realpath(__file__))
		self.max_count = 5 # Max number of failed login attempts before login fails

		self.key_manager = {} # Dictionary with all users info
		# self.key_manager has keys = usernames
		# Each self.key_manager[username] is a dictionary with key-value pairs:
		# self.key_manager[username]['user_id']      : user_id = hash of username
		# self.key_manager[username]['pwd_salt']     : salt for hashing password
		# self.key_manager[username]['hashed_pwd']   : resulting hashed password
		# self.key_manager[username]['pwd_salt']     : salt for hashing password
		# self.key_manager[username]['aes_key_salts']: salts for encryption

		self.this_user = {} # Dictionary with info for the user who has successfully logged in.
		# self.this_user has key-value pairs:
		# 'username'      : username 
		# 'user_id'       : user_id = hash of username 
		# 'pwd_salt'      : salt for hashing password
		# 'hashed_pwd'    : resulting hashed password 
		# 'aes_key_salts' : salts for encryption 
		# 'api_keys'      : the whole name of the game

	def get_api_keys(self):
		''' The whole machinery leveraged to retun a user's API keys 
		after successful login.
		'''
		success, username = self.login()
		result = None
		if success:
			result = self.this_user['api_keys']
		return success, username, result

	def login(self, username = None):
		''' Basic login method. Prompt for username. If username already 
		exists, call _encrypted_file_and_pwd_to_api_keys. If a username
		does not already exist, call _pwd_and_api_keys_to_encrypted_file
		which will register the new user.
		'''
		success = None
		if username is None:
			username = raw_input("user:\t")
		self.this_user['username'] = username
		self.this_user['user_id'] = self._get_user_id(username)
		self._open_key_manager()
		if username in self.key_manager:
			print "Known user, retrieving salts and decrypting API keys..."
			assert self.this_user['user_id'] == self.key_manager[username]['user_id']
			self.this_user['pwd_salt'] = self.key_manager[username]['pwd_salt']
			self.this_user['hashed_pwd'] = self.key_manager[username]['hashed_pwd']            
			self.this_user['aes_key_salts'] = self.key_manager[username]['aes_key_salts']
			success = self._encrypted_file_and_pwd_to_api_keys(username)
		else:
			print "Unknown user, generating salts and encrypting API keys..."
			black_box = AESCrypt()
			self.key_manager[username] = {}
			self.key_manager[username]['user_id'] = self.this_user['user_id']
			self.key_manager[username]['pwd_salt'] = base64.b64encode(os.urandom(black_box.salt_length))
			self.this_user['pwd_salt'] = self.key_manager[username]['pwd_salt']
			success = self._pwd_and_api_keys_to_encrypted_file(username)
			self._update_key_manager_file()
		return success, username

	def _update_key_manager_file(self):
		''' Write current key_manager dictionary to file.
		'''
		filename = self.self_path  + "/key_manager/key_manager.txt"
		with open(filename, "w") as key_manager_file:
			for username in self.key_manager:
				newline = username + "\t" + self.key_manager[username]['user_id'] + "\t" + self.key_manager[username]['pwd_salt'] + "\t" + self.key_manager[username]['hashed_pwd']
				for salt in self.key_manager[username]['aes_key_salts']:
					newline = newline + "\t" + salt
				key_manager_file.write(newline + "\n")

	def _get_user_id(self, username=None):
		''' Hash the user id with zero salt for filename purposes 
		'''
		assert username is not None
		black_box = AESCrypt()
		user_id_salt = "00000000000="
		user_id = base64.b64encode(black_box.hash_passphrase(username,user_id_salt, bits_to_read=32))
		return user_id

	def _open_key_manager(self):
		''' Load the key_manager.txt file which has all user info.
		Data in the key_manager.txt file will be separated by lines and
		tabs.
		Within a line, we will have data of the form
		username \t user_id \t pwd_salt \t hashed_pwd \t aes_key_salt_1 \t aes_key_salt_2 ... \t aes_key_salt_N \n
		'''
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

	def _get_code(self, s):
		''' This method takes a string, removes all non-alpha-numeric 
		characters, and returns the first four characters. 
		For filename generation; use with hashes of user information
		to generate unique(-ish) filenames.
		'''
		s = ''.join([x for x in s if x.isalpha()])
		return s[:4]

	def _encrypted_file_and_pwd_to_api_keys(self, username):
		''' In this method, we already have an encrypted files on record
		and we prompt the user for a password. We use the password to 
		decrypt the encrypted files.
		'''
		success = None
		black_box = AESCrypt()
		user_id_code = self._get_code(self.this_user['user_id'])
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
				salt_code = self._get_code(salt)
				filename = self.self_path + "/key_manager/" +  user_id_code + "." + salt_code + "." + str(self.key_manager[username]['aes_key_salts'].index(salt)) + ".txt"
				with open(filename, "r") as aes_file:
					encrypted_data = aes_file.read()
					api_keys.append(black_box.passphrase_decrypt(base64.b64decode(encrypted_data), pwd, base64.b64decode(salt)))
			self.this_user['api_keys'] = api_keys
		return success

	def _pwd_and_api_keys_to_encrypted_file(self, username=None, api_keys = [None, None]):
		''' In this method, we do not have any encrypted files on record 
		yet. So we ask a user for their password and their API keys and 
		we create a new encrypted file with the API keys inside.
		'''
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

			user_id_code = self._get_code(self.this_user['user_id'])
			salt_codes = [self._get_code( \
				self.this_user['aes_key_salts'][0]),  \
				self._get_code(self.this_user['aes_key_salts'][1])]

			salt_one = base64.b64decode(self.this_user['aes_key_salts'][0])
			salt_two = base64.b64decode(self.this_user['aes_key_salts'][1])
			plaintext_one = self.this_user['api_keys'][0]
			plaintext_two = self.this_user['api_keys'][1]

			encrypted_data = [base64.b64encode(\
				black_box.passphrase_encrypt(\
				plaintext_one, pwd, salt_one)), base64.b64encode(\
				black_box.passphrase_encrypt(\
				plaintext_two, pwd, salt_two))]

			filenames = [self.self_path + "/key_manager/" + \
				user_id_code + "." + salt_codes[0] + ".0.txt",\
				self.self_path + "/key_manager/" + user_id_code +\
				"." + salt_codes[1] + ".1.txt"]
			#if not os.path.isfile(filenames[0]):
			#    open(filenames[0], "w").close()
			with open(filenames[0], "w") as temp_file:
				temp_file.write(encrypted_data[0])
			with open(filenames[1],"w") as temp_file:
				temp_file.write(encrypted_data[1])
			success = True
	
		return success


#class Test_API_Key_Manager(unittest.TestCase):
#    def test_api_key_manager(self):
#        abed = API_Key_Manager()
#        abed.login()
#        api_keys = abed.get_api_keys()
#        print api_keys
#        
#suite = unittest.TestLoader().loadTestsFromTestCase(Test_API_Key_Manager)
#unittest.TextTestRunner(verbosity=1).run(suite)
