from django.db import models

class TimeSyncInit(models.Model):
    dev_eui = models.CharField(max_length=16)
    period = models.IntegerField()
    first_uplink_expected = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

class TimeCollection(models.Model):
    dev_eui = models.CharField(max_length=16)
    device_time = models.DateTimeField()
    time_expected = models.DateTimeField()
    time_received = models.DateTimeField()


class TimeSyncModels(models.Model):
    dev_eui = models.CharField(max_length=16)
    a=models.FloatField()
    b=models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

