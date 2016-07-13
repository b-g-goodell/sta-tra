# sta-tra
Use basic statistical tools to execute buys/sells using Coinbase API. I'm in the midst of refactoring from an older version of this code that was less well-planned than I hoped...

## Running with Windows 10

This has entirely been developed in Ubuntu (precise and trusty usually) so I have no idea how well it will port to windows. I also am under the impression that numpy and scipy are both a pain in the ass with Windows. So, I dunno, dual boot yourself some Ubuntu or use some Crouton for this.

## Running with Crouton

### Installing crouton:

I have had some success with unity, but I primarily use xfce. To start using crouton on your Chromebook: after entering developer mode and downloading crouton, I use:

        sudo sh ~/Downloads/crouton -r trusty -t xfce,xiwi,extension,chrome
        sudo start xfce4
        
Make sure you are up to date with this:

        sudo sh ~/Downloads/crouton -n trusty -u
        
Despite that it seems like trusty tahr works better on my chromebook than precise pangolin, and xfce is the only version I've gotten to work so far, it's still quite janky/iffy using ctrl-alt-shift-forward/back to switch operating systems. 

### Running Oracle.py with cron 

Now to get cron working.... According to [dnschneid](https://github.com/dnschneid/crouton/wiki/Setting-Up-Cron-Job) crouton needs some massaging to run cron. To get cron working with crouton, I use 

        sudo gedit /etc/rc.local

and add the line `exec cron` before the line `exit 0:` which will get cron running. Dnschneid says user level process don't work, so to add jobs we need to add them to cron at the root level. I use the command

        sudo gedit /etc/crontab

and add the following line to the bottom of my crontab file:

        1 * * * * root /usr/bin/python /path/to/scripts/Oracle.py
        
### Dependencies

We use the coinbase python library, the json library, the requests library, and both numpy and scipy.

What's worked for me is to use the following:

        sudo apt-get install git python-scipy python-numpy python-pip libffi-dev libssl-dev
        sudo pip install pyopenssl ndg-httpsclient pyasn1 coinbase pbkdf2

Sometimes pip gives me trouble and it appears to be resolved by adding `-H` to the pip command above.

## Mechanics

This section describes how the refactored code works.

### Password management, logging in, encryption:

All this is handled by AESCrypt.py and API_Key_Manager.py.

A file, `key_manager.txt`, with user login info will be kept for encryption purposes. Each user's username appears, as well as the salt for hashing their password, and their hashed password (raw passwords are not stored). Additionally, two more salts are stored in this file for hashing the same password to get AES encryption/decryption keys. Why two? Coinbase API keys come in pairs (the key and the secret).

If the username does not exist in the directory, a password is registered to them, the program prompts the user for API keys, generates salt for encrypting each key, and uses the password to encrypt those keys with the appropriate salt. The password is also hashed with some known salt, and the username, password salt, hashed password, and encryption key salts are all written to `key_manager.txt`. Thus, if a username exists in the directory, salts and hashed passwords should also be in the directory. After all that, the API keys are returned.

If the username exists and the provided password concatenated with the salt in `key_manager.txt` hashes to the hashed password in `key_manager.txt`, the user is validated and the keys for decrypting the API info are generated, and the API keys are returned to the user.


### Dynamics work like this: 

First problem: "How and when do we decide to issue `buy` or `sell` actions?" Part of this is determined with the market information using `Oracle.py`, and part of this is determined by the history of recent buys and sells we are trying to match, using `Trader.py`. Certainly, regardless of the market trend and history, if a chance is available to take some profit by matching an old `buy` or `sell` action with a new, dual action, we should take it. On the other hand, if we have no historical information, we should judge the recent trend of prices before making a move.

Judging trends: the file `Oracle.py` should be run once an hour using `cron` or whatever. It pulls hourly historical pricing information from Coinbase. We determine a preferred timescale that maximizes a normalized signal-to-noise ratio (SNR) for the log of the price in `_find_good_sample_size`. That sounds technical but we do the following: for each possible timescale, `i` hours (integer), compute the average of the past `i` hours of the natural log of the price and call this `y_mean`. Also compute and the (unbiased) standard deviation of the past `i` hours, `y_stdev`, and define the SNR `snr = y_mean*sqrt(i)/y_stdev` and we choose the `i` that maximizes this ratio. 

Then, in `_get_linear_trend` with our preferred timescale in hand, we sample the last `i` hours of pricing information and we find the OLS best-fit line, say `log(trend_price) - y_mean = best_fit_slope*(time - t_mean)` . Then we hypothesize that deviations from this line, (residual, say `z_i = abs(log(price(i)) - log(trend_price))`) are i.i.d. zero-mean normal random variables (this assumption is false in general, and will be improved eventually).  From this and using `y_stdev`, we can generate a `100(1-alpha/2)` percent confidence interval, which we can apply to the trend to get an upper and lower bound on price. These parameters (`y_mean`, `t_mean`, `best_fit_slope`, `y_stdev`, and the residuals) are used in `Trader.py`; we call the upper and lower bounds of this window `trend_buy_trig` and `trend_sell_trig` in `Trader.py`

The file `Trader.py` should be run once - it runs forever or until canceled by the user. This file will make new buy and sell actions based on the current price (which it pulls from Coinbase every second or so), based on the upper and lower bound on price from `Oracle.py`, and based on unmatched buys and sells. We compute a running pair of price thresholds, `self.triggers['buy']` and `self.triggers['sell']`, such that if the price drops below the buy trigger or if the price rises above the sell trigger, we issue a new buy or sell action. We require rules to compute these thresholds (we already know how we compute trend-based triggers, see above), and we require rules for computing the amount in these transactions. 

Users set their personal parameter choice for a value of `p` between 0.0 and 1.0 (I use 0.05). In the `buy_q`, we find the lowest price in USD of the buys, say `min_buy_price`. If the effective current sell price after fees is bigger than `(1+p)*min_buy_price` then we can sell a bit of Bitcoin and make some profit in USD.  If the effective current sell price after fees is not bigger than this value, but still is bigger than `trend_sell_trigger` we will go ahead and make the sell anyway in the hopes that the trendline computation is true-ish. If the `buy_q` is empty, we have no option except to set the sell trigger as `trend_sell_trigger`.

Dually, in the `Sell_Q`, we find the highest price in USD of the sells in `Sell_Q`, say `max_sell_price`. If the effective current buy price is smaller than `max_sell_price/(1+p)` then we can buy a bit of bitcoin for cheaper than we sold it. If the effective current buy price after fees is not smaller than this value, but is still smaller than `trend_buy_trigger` we will go ahead and make the buy anyway in the hopes that the trendline computation is true-ish. If the `Sell_Q` is empty, we set our buy trigger as `trend_buy_trigger`.




### Bookkeeping works like this: 

We have `buy` actions and `sell` actions that take place on a timeline. We want to link actions into bets with a low buy and high sell. These bets will  consisting of an ordered pair `(action1, action2)`. The timestamp of `action1` always occurs before the timestamp of `action2`. If `action1` is a `buy` action then `action2` must be a `sell` action such that the net profit in USD is positive. If `action2` is a `sell` action then `action1` must be a `buy` action such that the net profit in BTC is positive. If a pair of actions are linked in such an ordered pair, so we call these actions "paired."

As we issue actions to Coinbase and then receive confirmation of those actions, the results are added to a `Buy_Q` and a `Sell_Q` in chronological order. After an action is added to these queues, we look for possible pairs/bets following first-in-first-out rules: we will pair the earliest chronologically occurring action in either `Buy_Q` or `Sell_Q` that has a corresponding action in the opposite queue satisfying the profit condition. We de-queue the to-be-paired actions, store them into an ordered pair of the form `(action1, action2)`, and append the resulting ordered pair to a file, say `bet_history.csv` (these are resolved bets, no need to keep their information liquid).

If an action remains in the `Buy_Q` or the `Sell_Q` for a long time, this means that the price hasn't allowed this action to be paired. This corresponds to buying high before a price drop, or selling low before a price rise. These are bad moves that we need to remember, historically, so that we can try to recover from epic bad decisions from the past. Hence, we need our current `Buy_Q` and `Sell_Q` to also be written to file after each time they are updated, say `Buy_Q.csv` and `Sell_Q.csv`. This way, each time we load the program, we pick up where we left off.

#### Future implementations 

We will have more complicated buy/sell strategies. After we have some probabilities estimated, we can start using Kelly betting. Eventually, I would like to develop some neural networks that are trained to respond to time series.
