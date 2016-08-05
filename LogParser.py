import os
import datetime
import time
from collections import deque

class LogParser(object):
    def __init__(self):
        self.self_path = os.path.dirname(os.path.realpath(__file__))
        self.logfilepath = self.self_path + "/data/coinbasetrader.log"

    def parse(self):
        dump = None
        with open(self.logfilepath,"r") as logfile:
            dump = logfile.read()
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
                #print "Resource = ", d_res, " and Amount = ", d_amt, " and total = ", d_tot
                history.append([d_res, d_amt, d_tot, d_time])
        #print history
        clean_history = []
        for thingy in history:
            resource_type = thingy[0][1]
            btc_amt = float((thingy[1][1].split())[1])
            usd_amt = float((thingy[2][1].split())[1])
            timestamp = None
            try:
                timestamp = datetime.datetime.strptime(thingy[3][1].strip(), "%Y-%m-%dT%H:%M:%SZ")
            except ValueError:
                print "FUCK FUCK FUCK ", thingy[3][1], " %Y-%m-%dT%H:%M:%SZ"
            #print thingy[0]
            #print thingy[1]
            #print thingy[2]
            #print thingy[3]
            #print "\n"
            #clean_history.append([resource_type, usd_amt/btc_amt, btc_amt])
            clean_history.append([resource_type, usd_amt/btc_amt, btc_amt, timestamp])
        buy_q = deque()
        sell_q = deque()
        for item in clean_history:
            if 'buy' in item[0]:
                buy_q.append(item[1:])
            elif 'sell' in item[0]:
                sell_q.append(item[1:])
        # Format of these objects: [cost_basis, amt_in_btc, datetime]
        print "\nBuys:\n============\n"
        for buy in buy_q:
            print buy
        print "\nSell:\n============\n"        
        for sell in sell_q:
            print sell
        
        pair_q = deque()
        temp_buy_q = deque()
        temp_sell_q = deque()
        while len(buy_q) > 0:
            # Take buys out of queue in order and store them as this_buy
            this_buy = buy_q.popleft()
            while len(sell_q) > 0 and this_buy is not None:
                # Take sells out of queue in order, store as this_sell
                this_sell = sell_q.popleft()
                # Set the `change` object to None... if a pairing is
                # possible, either the buy or the sell will be bigger,
                # and the leftover is `change` as in `making change`
                change = None
                if float(this_buy[0])*(1.015) >= float(this_sell[0]):
                    # In this case, a pair is not possible, so we put
                    # this_sell into a temporary sell queue.
                    temp_sell_q.append(this_sell)
                else:
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
                    # [change, first_action, second_action]
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
                    if this_buy[1] > this_sell[1]:
                        # Find traits of change object
                        # In this case, change is a buy because
                        # we bought more bitcoin than we sold
                        cost_basis = this_buy[0]
                        amt = this_buy[1] - this_sell[1]
                        created_at = this_buy[2]
                        change_type = 'buy'
                    else:
                        # Find traits of change object
                        # In this case, change is a sell because
                        # we sold more bitcoin than we bought
                        cost_basis = this_sell[0]
                        amt = this_sell[1] - this_buy[1]
                        created_at = this_sell[2]
                        change_type = 'sell'
                        
                    assert cost_basis is not None
                    assert amt is not None
                    assert created_at is not None
                    change = [cost_basis, amt, created_at, change_type]
                    pair.append(change)
                    
                    #### Next we compute the pair object ####
                    buy_obj = [this_buy[0], this_buy[2]]
                    sell_obj = [this_sell[0], this_sell[2]]
                    # Compare order of transactions
                    if this_buy[2] < this_sell[2]: 
                        # The buy happened first
                        pair.append("Buy low sell high")
                        pair.append(buy_obj)
                        pair.append(sell_obj)
                    else:
                        pair.append("Sell high buy low")
                        pair.append(sell_obj)
                        pair.append(buy_obj)
                    pair_q.append(pair)
                    if change_type == 'buy':
                        this_buy = change[:-1]
                        this_sell = None
                    else:
                        this_buy = None
                        temp_sell_q.append(change[:-1])
            
            # At this point, we have left the while looping sells, so
            # either this_buy is None (so we have fully paired this_buy)
            # or this_buy is not None and we have exhausted the sells
            # without finding a pair for this_buy.
            
            # If this_buy is not None, we want to throw it into the
            # temp buy queue.
            
            # No matter what, we want to merge the temp_sell_q and the sell_q
            while len(temp_sell_q) > 0:
                sell_q.appendleft(temp_sell_q.pop())
            if this_buy is not None:
                temp_buy_q.append(this_buy)
            
        # Now we merge the temp buy queue with the buy queue as above.
        while len(temp_buy_q) > 0:
            buy_q.appendleft(temp_buy_q.pop())
            
        print "\n\n======AFTER PARSING=======\n\n"
        print "====Unpaired Buy Queue=====\n"
        for buy in buy_q:
            print buy
        print "====Unpaired Sell Queue====\n"
        for sell in sell_q:
            print sell
        print "=========Pair Queue========\n"
        for pair in pair_q:
            change = pair[0]
            pair_type = pair[1]
            first_action = pair[2]
            second_action = pair[3]
            print "Change: ", change
            print "Pair type: ", pair_type
            print "First: ", first_action
            print "Second: ", second_action, "\n"
paul = LogParser()
paul.parse()
