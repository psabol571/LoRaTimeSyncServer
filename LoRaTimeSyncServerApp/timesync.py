import time

from django.utils import timezone
from datetime import timedelta
from .models import TimeSyncInit, TimeCollection, TimeSyncModels
from sklearn.linear_model import LinearRegression
import numpy as np

import logging
logger = logging.getLogger('django')


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
    X = np.array([c.time_expected - first_received for c in collections]).reshape(-1, 1)
    y = np.array([c.time_received - first_received for c in collections])

    # Perform linear regression
    model = LinearRegression()
    model.fit(X, y)

    return model


def createModelV2(collections, first_received):
    # Prepare data for linear regression
    X = np.array([c.time_received - first_received for c in collections]).reshape(-1, 1)
    y = np.array([c.time_expected - first_received for c in collections])

    # Perform linear regression
    model = LinearRegression()
    model.fit(X, y)

    return model

def createModelV3(collections, first_received):
    # Prepare data for linear regression
    X = np.array([c.time_received for c in collections]).reshape(-1, 1)
    y = np.array([c.time_expected for c in collections])

    # Perform linear regression
    model = LinearRegression()
    model.fit(X, y)

    return model


def perform_sync(dev_eui):

    logger.info("Perform sync")

    # Get the last TimeSyncInit record 
    sync_init = TimeSyncInit.objects.filter(
        dev_eui=dev_eui,
    ).order_by('-created_at').first()

    logger.info("Sync init is None: ")
    logger.info(sync_init is None)

    if sync_init is None:
        return

    existing_model = TimeSyncModels.objects.filter(dev_eui=dev_eui, created_at__gte=sync_init.created_at).first()

    logger.info("existing_model is not None: ")
    logger.info(existing_model is not None)

    # for now perform sync only once
    if existing_model is not None:
        return

    # Fetch TimeCollection data for the specified dev_eui with time_expected greater than the first_uplink_expected
    collections = TimeCollection.objects.filter(dev_eui=dev_eui, time_expected__gte=sync_init.first_uplink_expected).order_by('time_received')

    logger.info("Collections length")
    logger.info(len(collections))

    # perform sync only when you have at least MIN_N records of data
    MIN_N = 15
    if len(collections) <= MIN_N:
        # Calculate the offset for the first uplink
        first_collection = collections[0]
        offset = first_collection.time_expected - first_collection.time_received

        logger.info(f"offset {offset}")

        tolerance = 0.2 * 1e9
        if abs(offset) < tolerance:
            return
        # send offset after first uplink
        return f's,{int(offset)}'  # You can log this or handle it as needed

    
    if len(collections) < MIN_N:
        return

    model = createModelV2(collections, collections[0].time_received)

    new_period_ns = int(sync_init.period * 1e9 * model.coef_[0])
    new_period_ms = int(new_period_ns / 1e3)

    # Save the model parameters
    model = TimeSyncModels.objects.create(
        dev_eui=dev_eui,
        a=model.coef_[0],
        b=model.intercept_,
        new_period_ms=new_period_ms,
        new_period_ns=new_period_ns,
    )

    return f's,{int(model.b)},{model.new_period_ns}'



