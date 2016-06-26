import unittest
import time, datetime
import os
import json
from coinbase.wallet.client import Client
from API_Key_Manager import API_Key_Manager

class Trader(object):
	def __init__(self):
		self.self_path = os.path.dirname(os.path.realpath(__file__))
		self.user_preferences = {}
		self.wallet = None
		self.api_url = "https://api.coinbase.com/v2/"
		pass
		
	def _user_login(self):
		alfred = API_Key_Manager()
		login_successful, username, api_keys = alfred.get_api_keys()
		print login_successful, username, api_keys
		if api_keys is not None and login_successful == True:
			self.user_preferences['username'] = username
			self.wallet = Client(api_keys[0].encode('utf-8'), api_keys[1].encode('utf-8'))
			self.user_preferences['filename'] = self.self_path  + "/users/" + username + ".pref"
			#self.user_preferences['filename']
			if not os.path.isfile(self.user_preferences['filename']):
				self._set_user_preferences()
			else:
				self._open_user_preferences()
        
		assert self.wallet != None
	
	def _set_user_preferences(self):
		print "=============="
		print "It appears that we don't have any user preferences on file for you. Please answer the following questions before we proceed:"
		print "=============="
		self.user_preferences['change_trigger'] = float(raw_input("This code works by taking action after the price changes a certain percentage. What percent would you like as a trigger? Please enter a number between 0.0 and 1.0:"))
		self.user_preferences['percentile'] = float(raw_input("This code also works using \% confidence intervals: the higher your desired \% confidence, the fewer actions you will take. Please enter a number between 0.0 and 1.0 signifiying your \% confidence (suggested: higher than 0.95 or 0.975)"))
		assert self.wallet is not None

		accounts = self.wallet.get_accounts().data
		commodity_account_list = []
		names = []
		for account in accounts:
			if account.currency=="BTC":
				commodity_account_list.append(account)
				names.append(account.name)
		print "Account Number: " + 5*" " + "Account Name:"
		for i, name in enumerate(names):
			print 4*" ", i, 15*" ", name
		idx = -1
		while idx not in range(len(names)):
			print "\n"
			idx = int(raw_input("Which (account number) of these would you like to trade with?    "))
			print "\n"
		self.user_preferences['commodity_acct'] = accounts[idx]
		
		print "============"

		print "\n Great, thanks. I see you have access to the following USD payment methods: \n"

		payment_methods = self.wallet.get_payment_methods().data
		currency_account_list = []
		names = []
		for method in payment_methods:
			if method.currency == "USD":
				currency_account_list.append(method)
				names.append(method.name)
		print "Payment Method Number " + 5*" " + "Payment Method Name:"
		for i, nam in enumerate(names):
			print 8*" ", i, 15*" ", nam

		idx = -1
		while idx not in range(len(names)):
			print "\n"
			idx = int(raw_input("Which (number) payment method of these would you like to trade with?  "))
			print "\n"
		self.user_preferences['currency_acct'] = currency_account_list[idx]
		print "============"
		print "\n Great, accounts chosen. Refreshing data before beginning. \n"

		#self.refresh()

		br_returned = False
		while not br_returned:
			try:
				print "\n"
				br = float(raw_input("How much money in USD would you like to start trading with?  BEWARE: We can't do automated checks on a bank account balance, so NEVER enter more than your current bank account balance here, and NEVER enter more than you are willing to lose by throwing down a garbage disposal!"))
				print "\n"
				br_returned = True
			except:
				print "\nError in _set_user_preferences while entering USD bankroll: possibly not a float? Please try again."
				continue
		self.user_preferences['currency_bankroll'] =  br
		
		#br = float(raw_input("I see you have a balance of " + str(self.user_preferences['commodity_acct'].balance.amount) + " bitcoin in your chosen commodity account. How much of this would you like to start trading with?   "))
		#print br
		br_returned = False
		while not br_returned:
			try:
				print "\n"
				br = float(raw_input("I see you have a balance of " + str(self.user_preferences['commodity_acct'].balance.amount) + " bitcoin in your chosen commodity account. How much of this would you like to start trading with?   "))
				print "\n"
				br_returned = True
			except:
				print "Error build_ini_file while entering BTC bankroll: possibly not a float? Please try again."
				print "\n"
				continue
			try:
				assert br <= self.user_preferences['commodity_acct'].balance.amount
				br_returned = True
			except AssertionError:
				print "Error! The bitcoin balance you are attempting to trade with is greater than your current bitcoin balance. Please try again."
				continue
		self.user_preferences['commodity_bankroll'] = br
		#print self.user_preferences
		with open(self.user_preferences['filename'],"w") as port_file:
			lines = []
			line = "change_trigger \t " + str(self.user_preferences['change_trigger']) + " \n"
			lines.append(line)
			line = "percentile \t " + str(self.user_preferences['percentile']) + " \n"
			lines.append(line)
			line = "commodity_acct \t " + str(self.user_preferences['commodity_acct'].id) + " \n"
			lines.append(line)
			line = "currency_acct \t " + str(self.user_preferences['currency_acct'].id) + " \n"
			lines.append(line)
			line = "currency_br \t " + str(self.user_preferences['currency_bankroll']) + " \n"
			lines.append(line)
			line = "commodity_br \t " + str(self.user_preferences['commodity_bankroll']) + " \n"
			lines.append(line)
			for line in lines:
				port_file.write(line)
	
		pass

	def refresh(self):
		commodity_account_name = self.user_preferences['commodity_account'].name
		commodity_account_id = self.user_preferences['commodity_account'].id
		currency_account_name = self.user_preferences['currency_account'].name
		currency_account_id = self.user_preferences['currency_account'].id
		
		accounts = self.wallet.get_accounts().data
		for account in accounts:
			if account.name == commodity_account_name:
				assert account.id == commodity_account_id, "Error in refresh, found an account name id mismatch!"
				self.commodity_account = account
		payment_methods = self.wallet.get_payment_methods().data
		for method in payment_methods:
			if method.name == currency_account_name:
				assert method.id == currency_account_id, "Error in refresh, found a name id mismatch!"
				self.currency_account = method
		
		
	def _open_user_preferences(self):
		with open(self.user_preferences['filename'], "r") as pref_file:
			lines = pref_file.readlines()
			for i in range(len(lines)):
				lines[i] = lines[i].rstrip()
				lines[i] = lines[i].split("\t")
			self.user_preferences['change_trigger'] = float(lines[0][1])
			self.user_preferences['percentile'] = float(lines[1][1])
			accounts = self.wallet.get_accounts().data
			for account in accounts:
				if account.id == lines[2][1]:
					self.user_preferences['commodity_acct'] = account
			payment_methods = self.wallet.get_payment_methods().data
			for method in payment_methods:
				if method.id == lines[3][1]:
					self.user_preferences['currency_acct'] = method
			self.user_preferences['currency_bankroll'] = float(lines[4][1])
			self.user_preferences['commodity_bankroll'] = float(lines[5][1])
			 	
		pass
		#self.user_preferences['filename'] = username + ".pref"
		#with open(self.user_preferences['filename'], "r") as pref_file:
			#lines = pref_file.readlines()
			#lines[0]
			#lines[1]
			#lines[2]
			#lines[3]
#		
#		try:
#			with open(self.user_preferences['filename'], "w") as port_file:
#				portfolio_lines = port_file.readlines()
#				comm_acct_info = portfolio_lines[0].rstrip().split("\t")
#				curr_acct_info = portfoloio_lines[1].rstrip().split("\t")
#		except:
#			print "oops what?"
		
tim = Trader()
tim._user_login()
#tim._set_user_preferences
