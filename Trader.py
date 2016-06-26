import unittest
import time, datetime
import os
import json
from collections import deque
from coinbase.wallet.client import Client
from API_Key_Manager import API_Key_Manager

class Trader(object):
	def __init__(self):
		self.self_path = os.path.dirname(os.path.realpath(__file__))
		self.user_preferences = {}
		self.wallet = None
		self.api_url = "https://api.coinbase.com/v2/"
		self.trigger_filename = self.self_path + "/data/triggers.dat"
		self.unmatched_buys = self.self_path + "/data/unmatched_buys."
		self.unmatched_sells = self.self_path + "/data/unmatched_sells."
		self.lag_time = 1.0 # float, seconds
		self.max_runs = 45 # int, number of runs.
		self.Buy_Q = deque()
		self.Sell_Q = deque()
		self._user_login()
		self.start_trader()
		self.triggers = {}
		self.triggers['buy'] = None
		self.triggers['sell'] = None
		self.state = None
		pass
		
	def start_trader(self):
		assert self.wallet is not None
		with open(self.trigger_filename, "r") as trigger_file:
			trigger_parameters = trigger_file.read()
		[width, t_mean, log_y_mean, slope] = [float(x) for x in trigger_parameters.rstrip().split()]
		self._load_unmatched()
		count = 0
		while count < self.max_runs:
			count += 1
			this_time = time.time()
			self._set_triggers(t_mean, y_mean, slope, this_time)
			try:
				quoted_buy_price = self.wallet.get_buy_price().amount
				quoted_sell_price  = self.wallet.get_sell_price().amount
			except:
				print "Something went wrong pulling current price. Proceeding anyway."
				continue
			effective_buy_price = float(self.wallet.get_buy_price().amount)*1.01 # Coinbase has 1% fees
			effective_sell_price = float(self.wallet.get_sell_price().amount)/1.01	# Coinbase has 1 fees

			print "\n------Price Report------\n"
			print "Buy price : ", effective_buy_price, "\n"
			print "Sell price : ", effective_sell_price, "\n"

			if effective_buy_price < self.triggers['buy']:
				self._make_buy(quoted_buy_price)
			elif effective_sell_price > self.triggers['sell']:
				self._make_sell(quoted_sell_price)
			
			#self.load_unmatched()
			next_time = time.time()
			if next_time - this_time < self.lag_time:
				time.sleep(next_time - this_time)

	def _get_btc_amt_to_sell(self):
		bankroll = self.user_preferences['commodity_bankroll']
		return float(self.attitude['leeway']*self.bankroll['BTC']*(1.0-1.0/self.attitude['upward']))
	def _get_usd_amt_to_spend(self):
		return float(self.attitude['leeway']*self.bankroll['USD']*(1.0-self.attitude['downward']))
		
	def _make_buy(self, quoted_price):
		
		
	def execute_buy(self, goal_price):
		print "Executing buy!"
		result = None
		usd_amt = self._get_usd_amt_to_spend()
		assert goal_price > 0.0, "Error, goal price is nonpositive"
		btc_amt = usd_amt/goal_price
		print "USD Amt: ", usd_amt, " BTC Amt: ", btc_amt, "\n"
		assert usd_amt > 1.0, "Error, tried to buy only " + str(usd_amt) + " in USD..."
		b = self.coinbase_client.buy(self.commodity_account.id, total=usd_amt, commit='false', currency = self.currency_account.currency, payment_method=self.currency_account.id)
		actual_price = None
		try:
			actual_price = float(float(b.subtotal.amount)/float(b.amount.amount))
		except:
			print "Oops! The actual buy price does not match the goal buy price!"
		if actual_price != None and abs(actual_price - goal_price) < 0.5:
			b = self.coinbase_client.commit_buy(self.commodity_account.id, b.id)
			self.bankroll['BTC'] += float(b.amount.amount)
			self.bankroll['USD'] -= float(b.total.amount)
			result = {}
			result['amount'] = float(b.amount.amount)
			result['cost_basis'] = float(b.total.amount)/float(b.amount.amount)
			result['created_at'] = b.created_at
			result['type'] = 'buy'
		if result != None:
			log_file = open(self.log_filename, "w")
			for item in b:
				log_file.write(str(item) + ", " + str(b[item]))
			log_file.close()
		return result
		
	def execute_sell(self, goal_price):
		print "Executing sell!"
		result = None
		btc_amt = self._get_btc_amt_to_sell()
		usd_amt = goal_price * btc_amt
		print "USD Amt: ", usd_amt, " BTC Amt: ", btc_amt, "\n"
		assert usd_amt > 1.0, "Error, tried to sell only " + str(usd_amt) + " in USD..."
		s = self.coinbase_client.sell(self.commodity_account.id, total=btc_amt, commit='false', currency = self.commodity_account.currency, payment_method=self.currency_account.id)
		actual_price = None
		try:
			actual_price = float(float(s.subtotal.amount)/float(s.amount.amount))
		except:
			print "Oops! The actual buy price does not match the goal buy price!"
		if actual_price != None and abs(actual_price - goal_price) < 0.5:
			s = self.coinbase_client.commit_sell(self.commodity_account.id, s.id)
			self.bankroll['BTC'] += float(s.amount.amount)
			self.bankroll['USD'] -= float(s.total.amount)
			result = {}
			result['amount'] = float(s.amount.amount)
			result['cost_basis'] = float(s.total.amount)/float(s.amount.amount)
			result['created_at'] = s.created_at
			result['type'] = 'sell'
		if result != None:
			log_file = open(self.log_filename, "w")
			for item in s:
				log_file.write(str(item) + ", " + str(s[item]))
			log_file.close()
		return result

		pass
	def _make_sell(self, quoted_price):
		pass
		
	def _load_unmatched(self):
		pass

	def _set_triggers(self, t_mean, y_mean, slope, this_time):
		lower_trend_price = math.exp((y_mean + slope*(this_time - t_mean))-width)
		upper_trend_price = math.exp((y_mean + slope*(this_time - t_mean))+width)
		lower_pairing_price = self._get_lowest_buy_price()*self.user_preferences['change_trigger']
		upper_pairing_price = self._get_lowest_buy_price()/self.user_preferences['change_trigger']
		self.triggers['buy'] = max(lower_trend_price, lower_pairing_price)
		self.triggers['sell'] = min(upper_trend_price, upper_pairing_price)
	
		
	def _load_unmatched(self):
		with open(self.unmatched_buys, "r") as umb_file:
			umb = umb_file.readlines()
		with open(self.unmatched_sells, "r") as ums_file:
			ums = ums_file.readlines()
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
			line = "change_trigger\t" + str(self.user_preferences['change_trigger']) + "\n"
			lines.append(line)
			line = "percentile\t" + str(self.user_preferences['percentile']) + "\n"
			lines.append(line)
			line = "commodity_acct\t" + str(self.user_preferences['commodity_acct'].id) + "\n"
			lines.append(line)
			line = "currency_acct\t" + str(self.user_preferences['currency_acct'].id) + "\n"
			lines.append(line)
			line = "currency_br\t" + str(self.user_preferences['currency_bankroll']) + "\n"
			lines.append(line)
			line = "commodity_br\t" + str(self.user_preferences['commodity_bankroll']) + "\n"
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
