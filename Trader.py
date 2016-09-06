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


class Trader(object):
    def __init__(self):
        self.self_path = os.path.dirname(os.path.realpath(__file__))

        directory = self.self_path + "/data"
        if not os.path.exists(directory):
            os.makedirs(directory)
        directory = self.self_path + "/users"
        if not os.path.exists(directory):
            os.makedirs(directory)
        directory = self.self_path + "/key_manager"
        if not os.path.exists(directory):
            os.makedirs(directory)

        self.log_filename = self.self_path + "/data/coinbasetrader.log"
        self.pair_filename = self.self_path + "/data/pairs.log"
        self.trigger_filename = self.self_path + "/data/triggers.dat"
        self.unmatched_filename = self.self_path + "/data/unmatched.dat"
        self.user_preferences = {}
        self.wallet = None
        self.k = None
        self.sample_size = None
        self.t_mean = None
        self.y_mean = None
        self.slope = None
        self.buy_q = deque()
        self.sell_q = deque()
        self.max_runs = 45
        self.triggers = {}
        self.triggers['buy'] = None
        self.triggers['sell'] = None
        self.lag_time = 1

        pass

    def start_trader(self):
        self._user_login()
        assert self.wallet is not None

        # Retrieve trend parameters
        #with open(self.trigger_filename, "r") as trigger_file:
        #    trigger_parameters = trigger_file.read()
        #[self.k, self.sample_size, self.time_mean, self.log_y_mean, self.slope] = [float(x) for x in trigger_parameters.rstrip().split()]

        # Load any unmatched buys and sells written to file into mem
        self._load_unmatched()

        while True:
            # Measure time at start of each loop
            this_time = time.time()
            #print this_time
            # Compute buy and sell triggers
            self._compute_trigger_window()

            try:
                quoted_buy_price = float(self.wallet.get_buy_price().amount)
                quoted_sell_price  = float(self.wallet.get_sell_price().amount)
            except:
                print "Something went wrong pulling current price. Proceeding anyway."
                #continue

            # Coinbase API v2 allegedly reports your price after 1% fees
            effective_buy_price = float(quoted_buy_price)#*1.01 
            effective_sell_price = float(quoted_sell_price)#/1.01

            print "\n------Price Report------\n"
            print "Eff. Buy price : ", effective_buy_price, ", buy_trigger : ", self.triggers['buy'], "\n"
            print "Eff. Sell price : ", effective_sell_price, ", sell_trigger : ", self.triggers['sell'], "\n"

            action_taken = None
            resulting_action = None
            action_type = None
            if effective_buy_price < self.triggers['buy']:
                old_len = len(self.buy_q)
                action_taken, resulting_action  = self._make_buy(quoted_buy_price)
                action_type = 'buy'
            if effective_sell_price > self.triggers['sell']:
                old_len = len(self.sell_q)
                action_taken, resulting_action = self._make_sell(quoted_sell_price)
                action_type = 'sell'
            # When these actions are made, they are added to unmatched
            # action queues. Whenever an unmatched action is added, we
            # seek pairs and strip them from the queues.
            if resulting_action is not None and action_taken is not None:
                if action_taken:
                    self._write_user_preferences() # Ensures bankroll is tracked appropriately
                    self._make_pairs() # Go through our record of unmatched actions and see if any pairings are possible
                    self._update_records() # Update the records of unmatched pairings.
                else:
                    if action_type == 'buy':
                        print "Woops, we tried to take a buy action, but it didn't go through."
                        with open(self.log_filename, "a") as log_file:
                            log_file.write("Woops we failed to take a buy action to buy at quoted price, " + str(quoted_buy_price) + "\n\n")
                    elif action_type == 'sell':
                        print "Woops, we tried to take a sell action, but it didn't go through."
                        with open(self.log_filename, "a") as log_file:
                            log_file.write("Woops we failed to take a sell action to buy at quoted price, " + str(quoted_sell_price) + "\n\n")
            #else:
                #print "Woops, we tried to do something but got a NoneType resulting action!"
                #with open(self.log_filename, "a") as log_file:
                #    log_file.write("Woops, we tried to do something but got a NoneType resulting action!")
            # Measure how long all that took and delay an appropriate
            # amount of time before moving onto next loop.
            next_time = time.time()
            print next_time- this_time
            if next_time - this_time < self.lag_time:
                time.sleep(next_time - this_time)

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
        pass

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

    def _load_unmatched(self):
        if os.path.isfile(self.log_filename):
            with open(self.log_filename, "r") as log_file:
               dump = log_file.read()
            assert dump is not None
            dump = dump.split("status, created")
            history = []
            for d in dump:
                d_amt = None
                d_tot = None
                d_res = None
                d_time = None
                d = d.strip().split("\n")
                for thingy in d:
                    split_thingy = thingy.split(",")
                    if 'resource'==split_thingy[0]:
                        d_res = split_thingy
                    if 'amount' in thingy:
                        d_amt = split_thingy
                    if 'total' in thingy and 'subtotal' not in thingy:
                        d_tot = split_thingy
                    if 'created_at' in thingy:
                        d_time = split_thingy
                if d_amt is not None and d_tot is not None:
                    history.append([d_res, d_amt, d_tot, d_time])
            clean_history = []
            for thingy in history:
                resource_type = thingy[0][1] # String = 'buy' or 'sell'
                btc_amt = float((thingy[1][1].split())[1]) # Float with btc amount
                usd_amt = float((thingy[2][1].split())[1]) # Float with usd amount
                created_at = thingy[3][1].strip() # apply datetime.datetime.strptime(timestamp, "%Y-%m-%dT%H:%M:%SZ") to get a datetime object
                clean_history.append([resource_type, usd_amt/btc_amt, btc_amt, created_at])
                
            ####RECALL!####
            # Format of this_buy is a dictionary:
            # 'key': 'value'
            # 'amount': amount in bitcoin, string containing float
            # 'cost_basis': price of bitcoin (usd/btc), string containing float
            # 'created_at': string with format "%Y-%m-%dT%H:%M:%SZ"
            # 'type': string = 'buy' or 'sell'
            ###############
            for item in clean_history:
                if 'buy' in item[0]:
                    this_buy = {'amount': None, 'cost_basis': None, 'created_at': None, 'type': 'buy'}
                    this_buy['amount'] = str(item[2])
                    this_buy['cost_basis'] = str(item[1])
                    this_buy['created_at'] = str(item[3])
                    self.buy_q.append(this_buy)
                elif 'sell' in item[0]:
                    this_sell = {'amount': None, 'cost_basis': None, 'created_at': None, 'type': 'sell'}
                    this_sell['amount'] = str(item[2])
                    this_sell['cost_basis'] = str(item[1])
                    this_sell['created_at'] = item[3]
                    self.sell_q.append(this_sell)
            self._update_records()
            

    def _add_action(self, line):
        #print line
        new_action = {}
        for entry in line:
            entry = entry.split(",")
            new_action[entry[0]] = entry[1]
        #print new_action.keys()
        if new_action['type'] == 'buy':
            self.buy_q.append(new_action)
        elif new_action['type'] == 'sell':
            self.sell_q.append(new_action)
        pass

    def _compute_trigger_window(self):
        this_time = time.time()
        prices_in_buy_q = [float(x['cost_basis']) for x in self.buy_q] # *(1.0+self.user_preferences['change_trigger'])
        prices_in_sell_q = [float(x['cost_basis']) for x in self.sell_q] # *(1.0+self.user_preferences['change_trigger'])
        if len(prices_in_sell_q) > 0:
            max_old_sell = max(prices_in_sell_q)
        else:
            max_old_sell = None
        if len(prices_in_buy_q) > 0:
            min_old_buy = min(prices_in_buy_q)
        else:
            min_old_buy = None

        #should_pull_data = (self.k is None) or \
        #                   (self.sample_size is None) or \
        #                   (self.y_mean is None) or \
        #                   (self.slope is None) or \
        #                   (int(this_time) % 180 == 0)
        #if should_pull_data:
        #    with open(self.trigger_filename, "r") as trigger_file:
        #        trigger_parameters = trigger_file.read()
        #        [self.k, self.sample_size, self.t_mean, self.y_mean, \
        #            self.slope] = [float(x) for x in trigger_parameters.rstrip( \
        #            ).split()]
        with open(self.trigger_filename, "r") as trigger_file:
            trigger_parameters = trigger_file.read()
            #print trigger_parameters
        [self.k, self.sample_size, self.t_mean, self.y_mean, \
            self.slope] = [float(x) for x in trigger_parameters.rstrip( \
            ).split()]
        #print "Testing trigger price: ", math.exp(self.y_mean)

        alpha = (1.0-self.user_preferences['percentile'])/2.0
        df = self.sample_size - 1
        t_score = -1.0*students_t.ppf(alpha, df)

        trend_buy_trig = math.exp((self.y_mean + self.slope*(this_time - self.t_mean))-self.k*t_score) #/(1.0+self.user_preferences['change_trigger'])
        trend_sell_trig = math.exp((self.y_mean + self.slope*(this_time - self.t_mean))+self.k*t_score) #*(1.0+self.user_preferences['change_trigger'])
        #print "Trend buy trigger: ", trend_buy_trig
        #print "Trend_sell_trigger: ", trend_sell_trig

        if max_old_sell is not None:
            sell_trigger_new = max(trend_sell_trig, max_old_sell*(1.0+self.user_preferences['change_trigger']))
        else:
            sell_trigger_new = trend_sell_trig
        if min_old_buy is not None:
            buy_trigger_new = min(trend_buy_trig, min_old_buy/(1.0+self.user_preferences['change_trigger']))
        else:
            buy_trigger_new = trend_buy_trig

        if max_old_sell is not None:
            self.triggers['buy'] = max(max_old_sell/(1.0+self.user_preferences['change_trigger']),buy_trigger_new)
        else:
            self.triggers['buy'] = buy_trigger_new
        if min_old_buy is not None:
            self.triggers['sell'] = min(min_old_buy*(1.0+self.user_preferences['change_trigger']),sell_trigger_new)
        else:
            self.triggers['sell'] = sell_trigger_new

    def _make_buy(self, quoted_price):
        """ This method issues a buy order and verifies it is correct."""
        print "Executing buy!"
        
        # First let's compute the amount in USD we wish to use in our buy order.
        usd_amt = max(5.0,0.95*self.user_preferences['change_trigger']/(1.0+self.user_preferences['change_trigger'])*self.user_preferences['currency_bankroll'])
        
        # Let's verify that our supposed buy order is non-trivial
        btc_amt = usd_amt/quoted_price
        print "Details on the incoming buy... USD Amt: ", usd_amt, " BTC Amt: ", btc_amt, "\n"
        try:
            assert usd_amt > 5.0
        except AssertionError:
            print "Error, tried to buy only " + str(usd_amt) + " in USD, which is " + str(btc_amt) + " in BTC... try a larger bankroll. Continuing..."

        
        # Let's issue the buy order, uncommitted...
        b = None
        while b is None:
            try:
                b = self.wallet.buy( self.user_preferences['commodity_acct'].id, total=usd_amt, commit='false', currency = self.user_preferences['currency_acct'].currency, payment_method=self.user_preferences['currency_acct'].id)
            except ValueError:
                b = None
        
        # Let's compute the price we got.
        actual_price = None
        try:
            actual_price = float(float(b.total.amount)/float(b.amount.amount))
        except:
            print "Oops! Couldn't compute actual price! Continuing..."
            
        # Let's verify the price we got is close to our quoted price:
        result = False
        while not result and b is not None and actual_price is not None and math.abs(actual_price - quoted_price) < 0.5:
            try:
                b = self.wallet.commit_buy(self.user_preferences['commodity_acct'].id, b.id)
                result = True
            except:
                result = False


        # If the buy went through, update our stuff!
        if result:
            self.user_preferences['commodity_bankroll'] += 0.999*float(b.amount.amount)
            self.user_preferences['currency_bankroll'] -= float(b.total.amount)
            resulting_buy = {}
            resulting_buy['amount'] = float(b.amount.amount)
            resulting_buy['cost_basis'] = float(b.total.amount)/float(b.amount.amount)
            resulting_buy['created_at'] = b.created_at
            resulting_buy['type'] = 'buy'
            #print "Length of buy_Q:", len(self.buy_q)
            self.buy_q.append(resulting_buy)
            #print "Length of buy_Q: ", len(self.buy_q)
            with open(self.log_filename, "a") as log_file:
                for item in b:
                    log_file.write(str(item) + ", " + str(b[item]) + "\n")
                log_file.write("\n")
        # If the buy did not go through, return a None object for resulting_buy
        else:
            resulting_buy = {}
        return result, resulting_buy
        
    def _make_sell(self, quoted_price):
        """ This method issues a sell order and verifies it is correct."""
        print "Executing sell!"
        
        # First let's compute the amount in USD we wish to use in our sell order.
        btc_amt = max(0.005,0.95*self.user_preferences['change_trigger']/(1.0+self.user_preferences['change_trigger'])*self.user_preferences['commodity_bankroll'])
        
        # Let's verify that our supposed sell order is non-trivial
        usd_amt = btc_amt*quoted_price
        print "Details on the incoming sell... USD Amt: ", usd_amt, " BTC Amt: ", btc_amt, "\n"
        try:
            assert btc_amt > 0.005
        except AssertionError:
            print "Error, tried to sell only " + str(usd_amt) + " in USD, which is " + str(btc_amt) + " in BTC... try a larger bankroll. Continuing..."
            # Let's verify that our supposed buy order is non-trivial
            btc_amt = usd_amt / quoted_price

        # Let's issue the sell order, uncommitted...
        s = None
        while s is None:
            try:
                s = self.wallet.sell(self.user_preferences['commodity_acct'].id, total=usd_amt, commit='false',
                                     currency=self.user_preferences['currency_acct'].currency,
                                     payment_method=self.user_preferences['currency_acct'].id)
            except ValueError:
                s = None

        # Let's compute the price we got.
        actual_price = None
        try:
            actual_price = float(float(s.total.amount) / float(s.amount.amount))
        except:
            print "Oops! Couldn't compute actual price! Continuing..."

        # Let's verify the price we got is close to our quoted price:
        result = False
        while not result s is not None and actual_price is not None and math.abs(actual_price - quoted_price) < 0.5:
            try:
                s = self.wallet.commit_sell(self.user_preferences['commodity_acct'].id, b.id)
                result = True
            except:
                result = False
        
        # If the sell went through, update our stuff!
        if result:
            self.user_preferences['commodity_bankroll'] += 0.999*float(s.amount.amount)
            self.user_preferences['currency_bankroll'] -= float(s.total.amount)
            resulting_sell = {}
            resulting_sell['amount'] = float(s.amount.amount)
            resulting_sell['cost_basis'] = float(s.total.amount)/float(s.amount.amount)
            resulting_sell['created_at'] = s.created_at
            resulting_sell['type'] = 'sell'
            self.sell_q.append(resulting_sell)
            with open(self.log_filename, "a") as log_file:
                for item in s:
                    log_file.write(str(item) + ", " + str(s[item]) + "\n")
                log_file.write("\n")
        # If the sell did not go through, return a None object for resulting_sell
        else:
            resulting_sell = {}
        return result, resulting_sell
        
    def _make_pairs(self):
        pair_q = deque()
        temp_buy_q = deque()
        temp_sell_q = deque()
        while len(self.buy_q) > 0:
            # Take buys out of queue in order and store them as this_buy
            this_buy = self.buy_q.popleft()
            #print this_buy 
            while len(self.sell_q) > 0 and this_buy is not None:
                # Take sells out of queue in order, store as this_sell
                this_sell = self.sell_q.popleft()
                #print this_sell
                # Set the `change` object to None... if a pairing is
                # possible, either the buy or the sell will be bigger,
                # and the leftover is `change` as in `making change`
                change = None
                if float(this_buy['cost_basis'])*(1.0 + self.user_preferences['change_trigger']) >= float(this_sell['cost_basis']):
                    #print "No pair possible"
                    # In this case, a pair is not possible, so we put
                    # this_sell into a temporary sell queue.
                    temp_sell_q.append(this_sell)
                else:
                    print "pair possible!"
                    # In this case, a pair is possible. So we compute a
                    # change object, a buy object, and a sell object,
                    # and we put them into a pairs queue.
                    
                    # If the change object is a sell, we put it into the
                    # temp_sell_queue. If the change object is a buy,
                    # we set this_buy to the change object and move 
                    # onto the next sell.
                    
                    # Format of change object: 
                    # [cost_basis, amt_in_btc, datetime, change_type]
                    # where change_type = 'buy' or 'sell'
                    change = []
                    
                    # Format of pair object:
                    # [change, pair_type, first_action, second_action]
                    # where change = change object above
                    # where first_action is either a buy or a sell
                    
                    pair = []
                    cost_basis = None
                    amt = None
                    created_at = None 
                    change_type = None
                    
                    #### First we compute the change object ####                  
                    # Compare amounts of the transactions. If the buy
                    # is bigger than the sell, then change will be a buy
                    # otherwise change will be a sell
                    if float(this_buy['amount']) > float(this_sell['amount']):
                        # Find traits of change object
                        # In this case, change is a buy because
                        # we bought more bitcoin than we sold
                        cost_basis = this_buy['cost_basis']
                        amt = str(float(this_buy['amount']) - float(this_sell['amount']))
                        created_at = this_buy['created_at']
                        change_type = 'buy'
                    else:
                        # Find traits of change object
                        # In this case, change is a sell because
                        # we sold more bitcoin than we bought
                        cost_basis = this_sell['cost_basis']
                        amt = str(float(this_sell['amount']) - float(this_buy['amount']))
                        created_at = this_sell['created_at']
                        change_type = 'sell'
                        
                    assert cost_basis is not None
                    assert amt is not None
                    assert created_at is not None
                    change = [cost_basis, amt, created_at, change_type]
                    print pair
                    pair.append(change)
                    print pair
                    
                    #### Next we compute the pair object ####
                    buy_obj = [this_buy['cost_basis'], this_buy['amount'], this_buy['created_at']]
                    sell_obj = [this_sell['cost_basis'], this_sell['amount'], this_sell['created_at']]
                    
                    buy_time = datetime.datetime.strptime(this_buy['created_at'].strip(), "%Y-%m-%dT%H:%M:%SZ")
                    sell_time = datetime.datetime.strptime(this_sell['created_at'].strip(), "%Y-%m-%dT%H:%M:%SZ")
                    
                    # Compare order of transactions
                    if buy_time < sell_time: 
                        # The buy happened first
                        pair.append("Buy low sell high")
                        pair.append(buy_obj)
                        pair.append(sell_obj)
                    else:
                        pair.append("Sell high buy low")
                        pair.append(sell_obj)
                        pair.append(buy_obj)
                    print pair
                    pair_q.append(pair)
                    print "\n======Pair queue so far=======\n"
                    for p in pair_q:
                        print p
                    print "\n======End of pair queue=======\n"
                    
                    ####RECALL!####
                    # Format of pair is a list of lists:
                    # pair = [change_list, pair_type, first_action_list, second_action_list]
                    # where change_list is a list with
                    #    change[0] = cost_basis
                    #    change[1] = amt_in_btc
                    #    change[2] = datetime
                    #    change[3] = change_type
                    # where pair_type is actually not a list, just a string
                    #    pair_type = "buy low sell high" or "sell high buy low"
                    # where first_action_list follows the format of this_buy
                    # above, and so does second_action_list
                    ###############
                    
                    if change_type == 'buy':
                        this_buy['cost_basis'] = change[0]
                        this_buy['amount'] = change[1]
                        this_buy['created_at'] = change[2]
                        this_buy['type'] = 'buy'
                        this_sell = None
                    else:
                        this_buy = None
                        temp_dict = {'cost_basis': None, 'amount': None, 'created_at': None, 'type': None}
                        temp_dict['cost_basis'] = change[0]
                        temp_dict['amount'] = change[1]
                        temp_dict['created_at'] = change[2]
                        temp_dict['type'] = 'sell'
                        temp_sell_q.append(temp_dict)
            
            # At this point, we have left the while looping sells, so
            # either this_buy is None (so we have fully paired this_buy)
            # or this_buy is not None and we have exhausted the sells
            # without finding a pair for this_buy.
            
            # If this_buy is not None, we want to throw it into the
            # temp buy queue.
            
            # No matter what, we want to merge the temp_sell_q and the sell_q
            while len(temp_sell_q) > 0:
                self.sell_q.appendleft(temp_sell_q.pop())
            if this_buy is not None:
                temp_buy_q.append(this_buy)
            
        # Now we merge the temp buy queue with the buy queue as above.
        while len(temp_buy_q) > 0:
            self.buy_q.appendleft(temp_buy_q.pop())
        
        # Format of pair (list) object in pair_q:
        #   pair[0] = change object = [cost_basis, amt, created_at, change_type]
        #   pair[1] = pair type = "Buy low sell high" or "Sell high buy low"
        #   pair[2] = first_action
        #   pair[3] = second_action
        # where both actions are lists with
        #   pair[2][0] = cost basis, string containing float
        #   pair[2][1] = amount in btc, string containing float,
        #   pair[2][2] = timestamp string with format "%Y-%m-%dT%H:%M:%SZ"
        # and similarly for pair[3], but opposite type of transaction
        if len(pair_q) > 0:
            with open(self.pair_filename, "w") as pair_file:
                for pair in pair_q:
                    data_to_write = ""
                    data_to_write += pair[1] + ", "
                    data_to_write += pair[2][0] + ", " + pair[2][1] + ", " + pair[2][2] + ", "
                    data_to_write += pair[3][0] + ", " + pair[3][1] + ", " + pair[3][2] + ", "
                    data_to_write += pair[0][0] + ", " + pair[0][1] + ", " + pair[0][2] + ", " + pair[0][3] + "\n"
                    pair_file.write(data_to_write)
        pass

    def _update_records(self):
        """ Update written file of unmatched buys and sells. """
        self._make_pairs()
        with open(self.unmatched_filename, "w") as unmatched_file:
            for buy in self.buy_q:
                newline = ""
                for key in buy:
                    newline += key + "," + str(buy[key]) + "\t"
                newline += "\n"
                unmatched_file.write(newline)
            for sell in self.sell_q:
                newline = ""
                for key in sell:
                    newline += key + "," + str(sell[key]) + "\t"
                newline += "\n"
                unmatched_file.write(newline)
        pass

tim = Trader()
tim.start_trader()
