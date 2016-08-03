import unittest
import time
import calendar
import requests
import os
import math


class Oracle(object):
    def __init__(self, fn="triggers.dat", hist_url="https://api.coinbase.com/v2/prices/historic", default_perc=0.99):
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

        self.self_path = os.path.dirname(os.path.realpath(__file__))
        self.history_url = hist_url
        self.window = [None, None]
        self.sample_size = None
        self.percentile = default_perc
        self.alpha = 2.0*(1.0-self.percentile)
        self.trigger_filename = self.self_path + "/data/" + fn
        self.data = {'time_data': None, 'price_data': None}
        #self.data['time_data'] = None
        #self.data['price_data'] = None
        self.sample_size = None
        self._find_good_sample_size()
        pred = self.get_prediction()
        self._write_prediction(pred)

    def _write_prediction(self, pred):
        with open(self.trigger_filename, "w") as temp_file:
            k = pred[0]
            sample_size = pred[1]
            t_mean = pred[2]
            y_mean = pred[3]
            slope = pred[4]
            resids = pred[5]
            line = str(k) + "\t" + str(sample_size) + "\t" + str(t_mean) + "\t" + str(y_mean) + "\t" + str(slope)
            temp_file.write(line)

    def _pull_data(self,number_hours=168):
        """ Pull hourly pricing data from coinbase """
        url = self.history_url + '?hours=' + str(number_hours)
        #results = None
        self.data['time_data'] = []
        self.data['price_data'] = []
        
        successful = False
        
        # In the following loop, we repetitively try to pull hourly
        # pricing information from coinbase. In heavy load times, 
        # this can return an error rather than our desired data, so
        # We will try every few seconds until successful.
        x = None
        count = 0 
        while not successful and count <10:
            print "Pulling data..."
            count += 1
            try:
                x = requests.get(url, timeout=22).json()
            except:
                print "Error in _pull_data, no JSON object was returned from requests.get(url).json()"
            print "Pull seemed to succeed. Computing if errors included in pull."
            successful = (x is not None) and (u'errors' not in x) and (u'data' in x)
            if not successful:
                print "Woops, something went wrong. Pulling data again in a little over 3 seconds."
                time.sleep(3.05)
        try:
            assert successful
        except AssertionError:
            print "Error in _pull_data, we exited a while loop prematurely for some reason!"
        print "Successfully pulled data..."
        # Now we will set self.data to the last 168 hours of data after
        # a bit of pre-processing.
        p = x[u'data'][u'prices'] # p is for prices
        temp_data = []
        for point in p:
            timepoint = float(calendar.timegm(time.strptime(point[u'time'].replace("-", "").replace("Z", ""), \
                "%Y%m%dT%H:%M:%S")))
            value_point = math.log(float(point[u'price']))
            temp_data.append((timepoint,value_point))
        
        # Sort by timestamp
        temp_data = sorted(temp_data, key = lambda x:x[0])
        #print temp_data
        self.data['time_data'] = [x[0] for x in temp_data]
        self.data['price_data'] = [x[1] for x in temp_data]

    def _find_good_sample_size(self, max_num_hours=168):
        """ Find an optimal sample size (number of hours) to take data"""
        print "Finding sample size. Please wait..."
        min_num_hours=11
        best_snr = None
        pref_length = None
        self._pull_data()
        for i in range(min_num_hours, max_num_hours):
            next_snr = self._get_snr(i)
            if best_snr is None or next_snr > best_snr:
                best_snr = next_snr
                pref_length = i
                print "Best snr so far is ", best_snr, " with preferred sample size ", pref_length
            print "Best snr so far comes with sample_size ", pref_length, " checking sample_size = ", (i+1), " next."
        self.sample_size = pref_length # Number of hours, sample size...
        print "We've determined we should use ", self.sample_size, " hours worth of samples."
        #self._pull_data(number_hours=self.sample_size)
        self.data['time_data'] = self.data['time_data'][-self.sample_size:]
        self.data['price_data'] = self.data['price_data'][-self.sample_size:]
        pass

    def _get_linear_trend(self,number_hours=168):
        """ Find a linear trend of self.data """
        # First let's center our data:
        y_mean = self._get_mean(self.data['price_data'])
        t_mean = self._get_mean(self.data['time_data'])
        translated_t_data = [x - t_mean for x in self.data['time_data']]
        translated_y_data = [x - y_mean for x in self.data['price_data']]

        # Next we project y_data onto time_data:
        # First we compute the unit time vector:
        t_len = self._get_length_of_vector(translated_t_data)
        unit_t_data = [x/t_len for x in translated_t_data]
        scalar_product = self._get_dot_product(translated_y_data, unit_t_data)
        best_fit_slope = scalar_product/t_len
        #print best_fit_slope

        z_data = [translated_y_data[i] - best_fit_slope*translated_t_data[i] for i in range(len(translated_y_data))]
        #z_mean = self._get_mean(z_data)
        #print z_data, len(z_data), z_mean

        results = (t_mean, y_mean, best_fit_slope, z_data)
        #z_data = residuals

        #except ValueError:
        #    "Error in pull_history, no JSON object could be decoded."
        #except requests.exceptions.ConnectionError:
        #    "Error: requests.exceptions.ConnectionError thrown for some reason. Passing through."
        return results

    def _get_snr(self, sampleSize):
        """ This finds the sample size that maximizes a normalized 
        signal-noise ratio statistic.
        """
        y_mean = self._get_mean(self.data['price_data'][-sampleSize:])
        y_stdev = self._get_stdev(self.data['price_data'][-sampleSize:])
        result = y_mean*((sampleSize-1)**0.5)/y_stdev
        return result

    def get_prediction(self):
        self._find_good_sample_size()
        result = self._get_linear_trend()
        noise = result[3]

        sample_mean_of_noise = self._get_mean(noise)
        sample_stdv_of_noise = self._get_stdev(noise)

        # df = self.sample_size - 1
        # t_score = -1.0*t.ppf(self.alpha/2.0, df)
        k = sample_stdv_of_noise / (self.sample_size ** 0.5)
        # print sample_mean_of_noise - k*t_score, sample_mean_of_noise + k*t_score
        # assert sample_mean_of_noise - k*t_score < 0.0 and sample_mean_of_noise + k*t_score > 0.0
        return (k, self.sample_size, result[0], result[1], result[2], result[3])

    def _get_stdev(self, data):
        mean = self._get_mean(data)
        squared_deviations = [(d-mean)**2.0 for d in data]
        sample_size = len(data)
        variance = sum(squared_deviations)/(sample_size - 1)
        return variance**0.5

    @staticmethod
    def _get_dot_product(y_data, unit_t_data):
        assert len(y_data) == len(unit_t_data)
        s = 0.0
        for i in range(len(y_data)):
            s += y_data[i] * unit_t_data[i]
        return s

    @staticmethod
    def _get_length_of_vector(data):
        s = 0.0
        for d in data:
            s += d * d
        return s ** 0.5

    @staticmethod
    def _get_mean(data):
        s = 0.0
        # print len(data)
        try:
            assert len(data) > 0
        except AssertionError:
            print "Error in _get_mean: possible array of length zero"
        try:
            assert data is not None
        except AssertionError:
            print "Error in _get_mean: trying to find mean of None"
        for d in data:
            s += d
        # print "sum: ", s
        # print "sum/len(data): ", s/len(data)
        # print "sum/float(len(data)): ", s/float(len(data))
        return s / len(data)

ollie = Oracle()
