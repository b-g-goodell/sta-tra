# sta-tra
Use basic statistical tools to execute buys/sells using Coinbase API. I'm in the midst of refactoring from an older Python2 version of this code that was... less well-planned than I hoped... up to a Python3 version that follows some more organized abstract guidelines.

## Running in Windows 10

This has entirely been developed in Ubuntu (precise and trusty usually) so I have no idea how well it will port to windows. I also am under the impression that numpy and scipy are both a pain in the ass with Windows. So, I dunno, dual boot yourself some Ubuntu or use some Crouton for this.

## Running Crouton

After entering developer mode and downloading crouton, use 

        sudo sh ~/Downloads/crouton -t unity-desktop -r trusty
        
Install the dependencies below. Install the a browser (we use chrome).For *cron*, according to dnschneid we "edit /etc/rc.local and add the following line before exit 0:"

        exec cron
        
dnschneid: "This will start the cron process as root for the system. Being the case, any cron jobs added at the user level will not work (ie anything added using the command crontab -e). For this reason you will have to add crons to the /etc/crontab file." I don't like vim and I'm too lazy to change the default editor to gedit, so I use

        EDITOR=/usr/bin/gedit crontab -e

Since we need historical prices pulled every T minutes (say once an hour, with `pull_historical_data.py` ) and we need to execute a script watching live price for action triggers every t seconds (say every minute, with `watch_for_triggers.py` ), we would use in cron:

        1 * * * * /path/to/scripts python pull_historical_data.py
        * * * * * /path/to/scripts python watch_for_triggers.py
        
Or something similar.

### Dependencies

We use the coinbase python library, the json library, the requests library, and both numpy and scipy.

What's worked for me is to use the following:

        sudo apt-get install python-scipy
        
        sudo apt-get install python-numpy
        
        sudo apt-get install python-pip
        
        sudo apt-get install libffi-dev libssl-dev
        
        sudo pip install pyopenssl ndg-httpsclient pyasn1
        
        sudo pip install coinbase

## Mechanics

This section describes how the refactored code will work. Older versions are different.

### Bookkeeping works like this: 

We have `buy` actions and `sell` actions that take place on a timeline. We link actions into bets with `buy_low_sell_high` bets and `sell_high_buy_low` bets, consisting of an ordered pair `(action1, action2)`. The timestamp of `action1` always occurs before the timestamp of `action2`. If `action1` is a `buy` action then `action2` must be a `sell` action such that the net profit in USD is positive. If `action2` is a `sell` action then `action1` must be a `buy` action such that the net profit in BTC is positive. If a pair of actions are linked in such an ordered pair, so we call these actions "paired."

As we issue actions to Coinbase and then receive confirmation of those actions, the results are added to a `Buy_Q` and a `Sell_Q` in chronological order. After an action is added to these queues, we look for possible pairs/bets following first-in-first-out rules: we will pair the earliest chronologically occurring action in either `Buy_Q` or `Sell_Q` that has a corresponding action in the opposite queue satisfying the profit condition. We de-queue the to-be-paired actions, store them into an ordered pair of the form `(action1, action2)`, and append the resulting ordered pair to a file, say `bet_history.csv` (these are resolved bets, no need to keep their information liquid).

If an action remains in the `Buy_Q` or the `Sell_Q` for a long time, this means that the price hasn't allowed this action to be paired. This corresponds to buying high before a price drop, or selling low before a price rise. These are bad moves that we need to remember, historically, so that we can try to recover from epic bad decisions from the past. Hence, we need our current `Buy_Q` and `Sell_Q` to also be written to file after each time they are updated, say `Buy_Q.csv` and `Sell_Q.csv`. This way, each time we load the program, we pick up where we left off.

### Dynamics work like this: 

The above describese how we keep track of our historical data; it's natural to ask "how and when do we decide to issue `buy` or `sell` actions?"

We make new actions in the following way. Every time we receive new information, we compute a running pair of price thresholds, `buy_trigger` and `sell_trigger`, such that if the price drops below `buy_trigger` or if the price rises above `sell_trigger`, we issue a new `buy` or `sell` actions. We require rules to compute these thresholds, and we require rules for computing the amount in these transactions. 

To compute thresholds, we use the recent price trend and the current `Buy_Q` and `Sell_Q`, and a pair of constants, `p` and `q`. In the `Buy_Q`, we find the lowest price in USD of the buys in `Buy_Q`, say `min_buy_price`. If the current price is bigger than `sell_trigger = (1+p)*min_buy_price` then we can sell a bit of Bitcoin and make some profit in USD. If the `Buy_Q` is empty, we set our `sell_trigger = upper_bound_on_trend` (see below).  In the `Sell_Q`, we find the highest price in USD of the sells in `Sell_Q`, say `max_sell_price`. If the current price is smaller than `buy_trigger = (1-q)*max_sell_price` then we can buy a bit of bitcoin for cheaper than we sold it. If the `Sell_Q` is empty, we set our `buy_trigger = lower_bound_on_trend` (see below).

The trend and its upper/lower bounds are constantly being computed using a statistical significance level, `a=alpha`, and the hourly pricing information published on Coinbase: the goal is to find a `100(1-a/2)%` two-sided confidence interval around a trendline. When new pricing information is published, we determine a `preferred_timescale` that maximizes a normalized signal-to-noise ratio (SNR) for `log(price)`. For each possible timescale, `T` hours (integer), compute the average of the past `T` hours of `log(price)` and call this `average_historical_log_price`. Also compute and the (unbiased) standard deviation of the past `T` hours, `stdev_historical_log_price`, and define the SNR `snr[T] = average_historical_log_price*sqrt(T)/stdev_historical_log_price` and we choose `T` that maximizes this ratio. Then, for the last `T` measurements of `log(price)`, we find the OLS best-fit line, say `log(trend_price) = slope*time + intercept`. Then we hypothesize that deviations from this `trend_price`, say `z_i = abs(log(price(i)) - log(trend_price))` are i.i.d. zero-mean normal random variables (this assumption is false in general, and will be improved eventually). We compute the corresponding `100(1-a/2)%` two-sided confidence interval for the mean. We call the upper and lower bounds of this window `(lower_bound_on_trend, upper_bound_on_trend)`: when we are outside of this interval, our hypothesis that deviations from the price trend are normal with mean zero is rejected, so we make a `buy` or `sell` bet. 


#### Future implementations 

We will have more complicated buy/sell strategies. After we have some probabilities estimated, we can start using Kelly betting. Eventually, I would like to develop some neural networks that are trained to respond to time series.