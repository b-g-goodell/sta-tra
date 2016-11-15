import unittest
import time
import datetime
import math
import os
import copy
from collections import deque
from coinbase.wallet.client import Client
from API_Key_Manager import API_Key_Manager
from scipy.stats import t as students_t


class Trader2(object):
    def __init__(self):
        self.self_path = os.path.dirname(os.path.realpath(__file__))

        directory = self.self_path + "/data"
        if not os.path.exists(directory):
            os.makedirs(directory)

        self.pair_filename = "pairslog.txt"
        directory = self.self_path + "/users"
        if not os.path.exists(directory):
            os.makedirs(directory)
        directory = self.self_path + "/key_manager"
        if not os.path.exists(directory):
            os.makedirs(directory)
        self.uncommited_action = None
        self.committed_action = None
        self.records = {}
        self.trigger_window = {}
        self.wallet = None
        self.user_preferences = {}
        self.time_interval = 2.
        self.buy_history = {}
        self.sell_history = {}

    def start_trader(self):
        self._user_login()
        self._load_queue()

        self._compute_trigger_window()
        loopin = 0
        while True:
            print "loopin loopin loopin loopin", loopin
            loopin += 1
            # Measure time at start of each loop
            this_time = time.time()
            current_price = self._pull_price()
            if self._outside_trigger_window(current_price):
                real_price = self._make_uncommitted_action()
                if self._outside_trigger_window(real_price):
                    self._commit_uncommitted_action()
                    self._update_records()
                    self._compute_trigger_window()
            new_time = time.time()
            time.sleep(max(this_time + self.time_interval - new_time, 0))

    def _user_login(self):
        alfred = API_Key_Manager()
        api_keys = None
        login_successful, username, api_keys = alfred.get_api_keys()
        self.wallet = None
        #print login_successful, username, api_keys
        if api_keys is not None and login_successful:
            #print "woop!"
            self.user_preferences['username'] = username
            self.wallet = Client(api_keys[0].encode('utf-8'), api_keys[1].encode('utf-8'))
            self.user_preferences['filename'] = self.self_path  + "/users/" + username + ".pref"
            if not os.path.isfile(self.user_preferences['filename']):
                self._set_user_preferences()
            else:
                self._open_user_preferences()
        assert self.wallet is not None

    def _set_user_preferences(self):
        print "=============="
        print "It appears that we don't have any user preferences on file for you..."
        print "Please answer the following questions before we proceed: "
        print "=============="

        experienced_user = False
        temp_trigger = float(raw_input("This code works by taking action after the price changes a certain percentage. What percent would you like as a trigger? Please enter a number larger than 0.0201. For example, if you want to take action every time the price changes by 5%, you would enter 0.05.  (Warning: please select a value greater than 0.0201 to guarantee actions taken are not unprofitable)  "))
        while temp_trigger < (1.01*1.01 - 1.0) and not experienced_user:
            is_exp = float(raw_input("WARNING: you selected a value that is less than the critical value of 0.0201, which means that in some rare cases your choice could lead to unprofitable actions. Did you mean to do this, say for testing purposes? (Y/N) "))
            if 'y' in is_exp:
                experienced_user = True
            else:
                temp_trigger = float(raw_input("Okay, if you didn't mean to select a number less than the critical value of 0.0201, what would you like your percent trigger to be? Please enter a number larger than 0.0201. For example, if you want to take action every time the price changes by 5%, you would enter 0.05. "))
        self.user_preferences['change_trigger'] = temp_trigger

        temp_percentile = float(raw_input("This code also works using % confidence intervals: the higher your desired % confidence, the fewer actions you will take. Please enter a number strictly between 0.0 and 1.0 signifiying your % confidence (suggested: 0.99)  "))
        while temp_percentile >= 1.0 or temp_percentile <= 0.0:
            temp_percentile = float(raw_input("Sorry, you selected a value that is not strictly between 0.0 and 1.0. Please enter a % confidence valeu between 0.0 and 1.0 (suggested 0.99) "))
        self.user_preferences['percentile'] = temp_percentile
        assert self.wallet is not None

        accounts = self.wallet.get_accounts().data
        #print "We have opened self.wallet.get_accounts().data, which has type(accounts)= ", type(accounts)
        commodity_account_list = []
        names = []
        for account in accounts:
            #print "We have an account here... which has type(account) = ", type(account)
            #print "And we have account = \n", account
            if account.type=="wallet":
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
        self.user_preferences['commodity_acct'] = copy.deepcopy(commodity_account_list[idx])

        print "============"

        print "\n Great, thanks. I see you have access to the following USD payment methods: \n"

        payment_methods = self.wallet.get_payment_methods().data
        currency_account_list = []
        names = []
        for method in payment_methods:
            #print "We have a payment method here with type(method) =", type(method)
            #print "And we have method = \n", method
            #print method.name, "==========\n", method, "====================\n", method.allow_buy, "==========================================\n\n"
            if method.allow_buy and method.allow_sell:
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
        self.user_preferences['currency_acct'] = copy.deepcopy(currency_account_list[idx])
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
                br_returned = False
                continue
        self.user_preferences['commodity_bankroll'] = br
        self._write_user_preferences()

    def _write_user_preferences(self):
        """ Update written user preferences, including current bankroll."""
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

    def _load_queue(self):
        print "Loading your history of buys and sells"
        buy_q = deque()
        temp_buy_q = deque()
        buys = self.wallet.get_buys(self.user_preferences['commodity_acct'].id)
        print buys
        buys = self.wallet.get_buys(self.user_preferences['commodity_acct'].id, buys.pagination['next_uri'])
        print buys
        for buy in buys['data']:
            if buy['committed'] and buy['status']=='completed':
                amt = float(buy['amount']['amount']) # in btc
                assert amt != 0.0, "FAIL LOUDLY FAIL EARLY"

                created_at = buy['created_at'] # timestamp
                id = buy['id']

                subtotal = float(buy['subtotal']['amount'])  # in USD
                #print subtotal
                #print "printing fees key for buy"
                #print buy['fees']
                #print buy['fees'][0], buy['fees'][1]
                #print buy['fees']['amount']
                #print buy['fees']['amount']['amount']
                fees = float(buy['fees'][0]['amount']['amount']) # in USD
                total = float(buy['total']['amount']) # in USD
                cost_basis = total/amt

                this_buy = {'amount':amt, 'created_at':created_at, 'fees':fees, 'id':id, 'subtotal':subtotal, 'total':total, 'cost_basis':cost_basis}

                self.buy_history[created_at] = copy.deepcopy(this_buy)
                buy_q.append(copy.deepcopy(this_buy))
        print "Buys loaded, we obtained ", len(buy_q), " buys. Printing..."
        count = 0
        temp_buy_q = deque()
        while len(buy_q) > 0:
            x = buy_q.popleft()
            print count, x
            count += 1
            temp_buy_q.appendleft(x)
        while len(temp_buy_q) > 0:
            buy_q.appendleft(temp_buy_q.popleft())

        #print "Now obtaining sells..."
        sell_q = deque()
        temp_sell_q = deque()
        sells = self.wallet.get_sells(self.user_preferences['commodity_acct'].id)
        for sell in sells['data']:
            if sell['committed'] and sell['status'] == 'completed':
                amt = float(sell['amount']['amount'])  # in btc
                assert float(amt) != 0.0, "FAIL LOUDLY FAIL EARLY"

                created_at = sell['created_at']  # timestamp
                id = sell['id']

                subtotal = float(sell['subtotal']['amount'])  # in USD
                fees = float(sell['fees'][0]['amount']['amount'])  # in USD
                total = float(sell['total']['amount'])  # in USD
                cost_basis = total/amt

                this_sell = {'amount':amt, 'created_at': created_at, 'fees': fees, 'id': id, 'subtotal': subtotal, 'total': total, 'cost_basis':cost_basis}

                self.sell_history[created_at] = copy.deepcopy(this_sell)
                sell_q.append(copy.deepcopy(this_sell))
        #print "We got ", len(sell_q), "sells.  Printing..."
        count = 0
        temp_sell_q = deque()
        while len(sell_q) > 0:
            x = sell_q.popleft()
            print count, x
            count += 1
            temp_sell_q.appendleft(x)
        while len(temp_sell_q) > 0:
            sell_q.appendleft(temp_sell_q.popleft())
        #print "Now making pairs..."
        pair_q = deque()
        while len(buy_q) > 0:
            this_buy = buy_q.popleft()
            #this_sell = 1
            while len(sell_q) > 0 and this_buy is not None:
                this_sell = sell_q.popleft()
                #print "Comparing buy to sell:...\n"
                #print "Buy\n", this_buy, "\n"
                #print "Sell\n", this_sell, "\n"
                #print "Match possible?"
                #print "Comparing ", this_buy, "to ", this_sell
                if float(this_buy['cost_basis'])*(1.0 + self.user_preferences['change_trigger']) < float(this_sell['cost_basis']) and float(this_buy['amount']) > 0.0 and float(this_sell['amount']) > 0.0:
                    print "Yes!"
                    pair = {}
                    pair['amount'] = copy.deepcopy(min(float(this_buy['amount']), float(this_sell['amount'])))
                    pair['created_at'] = copy.deepcopy(max(this_buy['created_at'],this_sell['created_at']))

                    pair['buy'] = copy.deepcopy(this_buy)
                    pair['sell'] = copy.deepcopy(this_sell)

                    this_buy['amount'] = float(pair['buy']['amount']) - float(pair['amount'])
                    this_sell['amount'] = float(pair['sell']['amount']) - float(pair['amount'])
                    if this_buy['amount'] <= 0.0:
                        pair['fees'] = copy.deepcopy(float(this_buy['fees']) +float(this_sell['fees'])*float(pair['amount'])/(float(this_sell['amount'])+float(pair['amount'])))
                        this_sell['fees'] = copy.deepcopy(float(this_sell['fees'])*float(this_sell['amount'])/(float(this_sell['amount'])+float(pair['amount'])))
                        pair['total'] = copy.deepcopy(float(this_sell['total'])*float(pair['amount'])/(float(this_sell['amount'])+float(pair['amount'])) - float(this_buy['total']))
                        this_sell['total'] = copy.deepcopy(float(this_sell['total'])*float(this_sell['amount'])/(float(this_sell['amount'])+float(pair['amount'])))
                        this_buy = None
                    if this_sell['amount'] <= 0.0:
                        pair['fees'] = copy.deepcopy(float(this_sell['fees']) +float(this_buy['fees'])*float(pair['amount'])/(float(this_buy['amount'])+float(pair['amount'])))
                        this_buy['fees'] = copy.deepcopy(float(this_buy['fees'])*float(this_buy['amount'])/(float(this_buy['amount'])+float(pair['amount'])))
                        pair['total'] = copy.deepcopy(float(this_sell['total']) - this_buy['total']*float(pair['amount'])/(float(this_buy['amount'])+float(pair['amount'])))
                        this_buy['total'] = copy.deepcopy(float(this_buy['total'])*float(this_buy['amount'])/(float(this_buy['amount'])+float(pair['amount'])))
                        this_sell = None
                    pair_q.append(pair)
                if this_sell is not None:
                    temp_sell_q.append(this_sell)
            if this_buy is not None:
                temp_buy_q.append(this_buy)
            while len(temp_sell_q) > 0:
                sell_q.appendleft(temp_sell_q.pop())
        while len(temp_buy_q) > 0:
            buy_q.appendleft(temp_buy_q.pop())
        print "Printing pairs to file... we have ", len(pair_q), " pairs to print."
        if len(pair_q) > 0:
            with open(self.pair_filename, "a") as pair_file:
                pair_file.write("Amount,fees,total,created_at\n")
                for pair in pair_q:
                    this_sell = pair['sell']
                    this_buy = pair['buy']
                    amt = pair['amount']
                    fees = pair['fees']
                    tot = pair['total']
                    created_at = pair['created_at']
                    pair_file.write(str(str(amt) + "," + str(fees) + "," + str(tot) + "," + str(created_at) + "\n"))
        pass

    def _compute_trigger_window(self):
        pass

    def _pull_price(self):
        pass

    def _make_uncommitted_action(self):
        pass

    def _outside_trigger_window(self, this_price):
        #return this_price['buy'] < self.trigger_window['buy'] or this_price['sell'] > self.trigger_window['sell']
        pass

    def _commit_uncommitted_action(self):
        pass

    def _update_records(self):
        pass


Taylor = Trader2()
Taylor.start_trader()