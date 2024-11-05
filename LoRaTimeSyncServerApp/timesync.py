import time

from django.utils import timezone
from datetime import timedelta
from .models import TimeSyncInit, TimeCollection, TimeSyncModels
from sklearn.linear_model import LinearRegression
import numpy as np


def initTimeSync(dev_eui, period, now):
    reserve = 3
    first_uplink_expected = (
        (now + (period + reserve) * (1000**3))  # add period and reserve as nanoseconds
        // (1000**3) 
    ) * (1000**3)  # and cut it to nearest second
    
    time_sync_device = TimeSyncInit.objects.create(
        dev_eui=dev_eui,
        period=period,
        first_uplink_expected=first_uplink_expected,
    )

    return first_uplink_expected


def saveTimeCollection(dev_eui, device_time, time_received):
    device = TimeSyncInit.objects.filter(dev_eui=dev_eui).last()

    if device is None:
        return None

    time_diff = time_received - device.first_uplink_expected
    periods_passed = round(time_diff / device.period / (1000**3))
    time_expected = device.first_uplink_expected + periods_passed * device.period * (1000**3)
    
    # Create and save the TimeCollection instance
    time_collection = TimeCollection.objects.create(
        dev_eui=dev_eui,
        time_received=time_received,
        time_expected=time_expected,
        device_time=device_time
    )
    
    return time_collection


def createModel(collections, first_received):
    # Prepare data for linear regression
    X = np.array([c.time_received - first_received for c in collections]).reshape(-1, 1)
    y = np.array([c.time_expected - first_received for c in collections])

    # Perform linear regression
    model = LinearRegression()
    model.fit(X, y)

    return model


def perform_sync(dev_eui):

    # Fetch TimeCollection data for the specified dev_eui
    collections = TimeCollection.objects.filter(dev_eui=dev_eui).order_by('time_received')

    # MIN_N = 300
    # if len(collections) < MIN_N:
    #     return

    model = createModel(collections, collections[0].time_received)

    # Save the model parameters
    TimeSyncModels.objects.create(
        dev_eui=dev_eui,
        a=model.coef_[0],
        b=model.intercept_
    )

    return model



