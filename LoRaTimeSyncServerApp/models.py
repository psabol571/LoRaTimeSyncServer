from django.db import models


class TimeSyncInit(models.Model):
    dev_eui = models.CharField(max_length=16)
    period = models.IntegerField()
    first_uplink_expected = models.BigIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)


class TimeCollection(models.Model):
    dev_eui = models.CharField(max_length=16)
    device_time = models.BigIntegerField()
    time_expected = models.BigIntegerField()
    time_received = models.BigIntegerField()


class TimeSyncModels(models.Model):
    dev_eui = models.CharField(max_length=16)
    a=models.FloatField()
    b=models.FloatField()
    created_at = models.DateTimeField(auto_now_add=True)

