import unittest
import time
import math
import os
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
        with open(self.trigger_filename, "r") as trigger_file:
            trigger_parameters = trigger_file.read()
        [self.k, self.sample_size, self.time_mean, self.log_y_mean, self.slope] = [float(x) for x in trigger_parameters.rstrip().split()]

        # Load any unmatched buys and sells written to file into mem
        self._load_unmatched()

        count = 0
        #while count < self.max_runs:
        while True:
            # Repeat self.max_runs times
            count += 1
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
                continue

            effective_buy_price = float(quoted_buy_price)#*1.01 # Coinbase has 1% fees
            effective_sell_price = float(quoted_sell_price)#/1.01	# Coinbase has 1 fees

            print "\n------Price Report------\n"
            print "Eff. Buy price : ", effective_buy_price, ", buy_trigger : ", self.triggers['buy'], "\n"
            print "Eff. Sell price : ", effective_sell_price, ", sell_trigger : ", self.triggers['sell'], "\n"

            action_taken = False
            if effective_buy_price < self.triggers['buy']:
                old_len = len(self.buy_q)
                action_taken = self._make_buy(quoted_buy_price)
                assert action_taken #(len(self.buy_q) - old_len) > 0
            elif effective_sell_price > self.triggers['sell']:
                old_len = len(self.sell_q)
                action_taken = self._make_sell(quoted_sell_price)
                assert action_taken #len(self.sell_q) - old_len > 0
            if action_taken:
                self._write_user_preferences() # Ensures bankroll is tracked appropriately
                self._make_pairs()
                self._update_records()
            # When these actions are made, they are added to unmatched
            # action queues. Whenever an unmatched action is added, we
            # seek pairs and strip them from the queues.

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
        self.user_preferences['change_trigger'] = float(raw_input("This code works by taking action after the price changes a certain percentage. What percent would you like as a trigger? Please enter a number between 0.0 and 1.0. For example, if you want to take action every time the price changes by 5%, you would enter 0.05.  "))
        self.user_preferences['percentile'] = float(raw_input("This code also works using % confidence intervals: the higher your desired % confidence, the fewer actions you will take. Please enter a number between 0.0 and 1.0 signifiying your % confidence (suggested: higher than 0.95 or 0.975)  " ))
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

        self._write_user_preferences()

    def _write_user_preferences(self):
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
        if os.path.isfile(self.unmatched_filename):
            with open(self.unmatched_filename, "r") as unmatched_file:
                data = unmatched_file.readlines()
            if len(data) > 0:
                for line in data:
                    line = line.rstrip()
                    line = line.split("\t")
                    self._add_action(line)

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
        #print entry
        #print entry[0]
        #new_action = {}
        #for entry in line:
        #	new_action[entry[0]] = entry[1]
        #print new_action.keys()
        #if new_action['type'] == 'buy':
        #	self.buy_q.append(new_action)
        #elif new_action['type'] == 'sell':
        #	self.sell_q.append(new_action)


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

        should_pull_data = (self.k is None) or \
                           (self.sample_size is None) or \
                           (self.y_mean is None) or \
                           (self.slope is None) or \
                           (int(this_time) % 180 == 0)
        if should_pull_data:
            with open(self.trigger_filename, "r") as trigger_file:
                trigger_parameters = trigger_file.read()
                [self.k, self.sample_size, self.t_mean, self.y_mean, \
                    self.slope] = [float(x) for x in trigger_parameters.rstrip( \
                    ).split()]

        alpha = (1.0-self.user_preferences['percentile'])/2.0
        df = self.sample_size - 1
        t_score = -1.0*students_t.ppf(alpha, df)

        trend_buy_trig = math.exp((self.y_mean + self.slope*(this_time - self.t_mean))-self.k*t_score) #/(1.0+self.user_preferences['change_trigger'])
        trend_sell_trig = math.exp((self.y_mean + self.slope*(this_time - self.t_mean))+self.k*t_score) #*(1.0+self.user_preferences['change_trigger'])

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
        usd_amt = 0.95*self.user_preferences['change_trigger']/(1.0+self.user_preferences['change_trigger'])*self.user_preferences['currency_bankroll']
        print "Executing buy!"
        result = None
        btc_amt = usd_amt/quoted_price
        print "USD Amt: ", usd_amt, " BTC Amt: ", btc_amt, "\n"
        assert usd_amt > 1.0, "Error, tried to buy only " + str(usd_amt) + " in USD..."
        b = self.wallet.buy( self.user_preferences['commodity_acct'].id, total=usd_amt, commit='false', currency = self.user_preferences['currency_acct'].currency, payment_method=self.user_preferences['currency_acct'].id)
        #s = self.wallet.sell(self.user_preferences['commodity_acct'].id, total=usd_amt, commit='false', currency = self.user_preferences['currency_acct'].currency, payment_method=self.user_preferences['currency_acct'].id)
        actual_price = None
        try:
            actual_price = float(float(b.total.amount)/float(b.amount.amount))
        except:
            print "Oops! Couldn't compute actual price!"
        result = False
        #print "actual price ", actual_price, " abs(actual_price-quoted_price) ", abs(actual_price - quoted_price)
        if actual_price is not None and abs(actual_price - quoted_price) < 0.5:
            result = True
            #print "wooo, set result = true"
            try:
                b = self.wallet.commit_buy(self.user_preferences['commodity_acct'].id, b.id)
            except:
                result = False
            #continue
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
        return result

    def _make_sell(self, quoted_price):
        amount_in_btc = 0.95*self.user_preferences['change_trigger']/(1.0 + self.user_preferences['change_trigger'])*self.user_preferences['commodity_bankroll']
        print "Executing sell!"
        result = None
        usd_amt = quoted_price*amount_in_btc
        print "USD Amt: ", quoted_price*amount_in_btc, " BTC Amt: ", amount_in_btc, "\n"
        assert usd_amt > 1.0, "Error, tried to sell only " + str(usd_amt) + " in USD..."

        s = self.wallet.sell(self.user_preferences['commodity_acct'].id, total=usd_amt, commit='false', currency = self.user_preferences['currency_acct'].currency, payment_method=self.user_preferences['currency_acct'].id)
        actual_price = None
        try:
            actual_price = float(float(s.total.amount)/float(s.amount.amount))
        except:
            print "Oops! Could not compute actual price"
        result = False
        if actual_price is not None and abs(actual_price - quoted_price) < 0.5:
            result = True
            try:
                s = self.wallet.commit_sell(self.user_preferences['commodity_acct'].id, s.id)
            except:
                result = False
            #continue
            if result:
                self.user_preferences['commodity_bankroll'] -= float(s.amount.amount)
                self.user_preferences['currency_bankroll'] += 0.999*float(s.total.amount)
                resulting_sell = {}
                resulting_sell['amount'] = float(s.amount.amount)
                resulting_sell['cost_basis'] = float(s.total.amount)/float(s.amount.amount)
                resulting_sell['created_at'] = s.created_at
                resulting_sell['type'] = 'sell'
                print "Length of sell_Q: ", len(self.sell_q)
                self.sell_q.append(resulting_sell)
                print "Length of sell_Q: ", len(self.sell_q)
                with open(self.log_filename, "a") as log_file:
                    for item in s:
                        log_file.write(str(item) + ", " + str(s[item]) + "\n")
                    log_file.write("\n")

        return result

    def _make_pairs(self):
        temp_buy_q = deque()
        temp_sell_q = deque()
        while len(self.buy_q) > 0:
            # Take buys out of queue in order and store them as this_buy
            this_buy = self.buy_q.popleft()
            while len(self.sell_q) > 0 and this_buy is not None:
                # Take sells out of queue in order, store as this_sell
                this_sell = self.sell_q.popleft()
                # Set the `change` object to None... if a pairing is
                # possible, either the buy or the sell will be bigger,
                # and the leftover is `change` as in `making change`
                change = None
                if this_buy['cost_basis']*(1.0 + self.user_preferences['change_trigger']) >= this_sell['cost_basis']:
                    # In this case, a pair is not possible, so we put
                    # this_sell into a temporary sell queue.
                    temp_sell_q.append(this_sell)
                else:
                    # In this case, a pair is possible. So we use the
                    # _pair function with the buy and sell in chrono-
                    # logical order.
                    if this_buy['created_at'] < this_sell['created_at']:
                        change = self._pair(this_buy, this_sell)
                    else:
                        change = self._pair(this_sell, this_buy)

                    # We have a `change` thingy, which is either a buy
                    # or a sell. If it's a buy, simply set this_buy
                    # to the change and clear out this_sell. If change
                    # is a sell, then we put the change into the temp
                    # sell queue and clear out this_buy.
                    if change['type'] == 'buy':
                        this_buy = change
                        this_sell = None
                    else:
                        this_buy = None
                        temp_sell_q.append(change)
            # Okay, now we've exhausted the sell queue or we matched
            # this_buy. Either way, we want to go on to the next buy.
            # If we have matched this_buy then we have a temp
            # sell queue and self.sell_q which we must merge in order
            # before we look at the next buy in the buy_queue for match.
            # On the other hand, if we have exhausted the sell queue,
            # then the temporary sell queue is (possibly) full and
            # we use this as self.sell_q before we look at the next
            # buy in the buy queue.
            if this_buy is None:
                while len(temp_sell_q) > 0:
                    self.sell_q.appendleft(temp_sell_q.pop())
            else:
                temp_buy_q.append(this_buy)
                self.sell_q = temp_sell_q
                temp_sell_q = deque()
            # No matter what at this point, the self.sell_q has not
            # lost any information unless matches have occurred.
        # Okay, now we've exhaused the buy queue, and we have temp_buy_q
        self.buy_q = temp_buy_q


    def _pair(self, action_1, action_2):
        change = {}
        data_to_write = ""
        assert action_1['created_at'] <= action_2['created_at']
        cash_1 = float(action_1['amount'])*float(action_1['cost_basis'])
        cash_2 = float(action_2['amount'])*float(action_2['cost_basis'])
        if action_1['amount'] <= action_2['amount']:
            change['amount'] = action_2['amount'] - action_1['amount']
            change['cost_basis'] = (cash_2 - cash_1)/change['amount']
            change['created_at'] = action_2['created_at']
            change['type'] = action_2['type']
            data_to_write = action_1['type'] + "\t" + action_1['created_at'] + "\t" + action_2['type'] + "\t" + action_2['created_at'] + "\t" + str(action_1['amount']) + "\t" + str(action_1['cost_basis']) + "\t" + str(action_2['cost_basis']) + "\n"
        else:
            change['amount'] = float(action_1['amount']) - float(action_2['amount'])
            change['cost_basis'] = (cash_1 - cash_2)/change['amount']
            change['created_at'] = action_1['created_at']
            change['type'] = action_1['type']
            data_to_write = action_1['type'] + "\t" + action_1['created_at'] + "\t" + action_2['type'] + "\t" + action_2['created_at'] + "\t" + str(action_2['amount']) + "\t" + str(action_1['cost_basis']) + "\t" + str(action_2['cost_basis']) + "\n"
        with open(self.pair_filename, "a") as pair_file:
            pair_file.write(data_to_write)
        return change

    def _update_records(self):
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
