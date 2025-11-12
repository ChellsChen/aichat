import uuid
from django.db import models
from django.utils.timezone import now

# Create your models here.

class ModelBase(models.Model):
    # id
    uuid = models.UUIDField(default=uuid.uuid4, unique=True, editable=False, help_text="uuid")
    # uuid = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False, help_text="uuid")

    #id = models.UUIDField(primary_key=True, unique=True, default=uuid.uuid4, editable=False, help_text="id")

    # 记录创建时间
    gmt_create = models.DateTimeField(blank=True, auto_now_add=True, editable=False, help_text='创建时间')

    # 记录修改时间
    gmt_modify = models.DateTimeField(blank=True, auto_now=True, editable=False, help_text='修改时间')

    version = models.IntegerField(default=0, blank=True, help_text='记录版本')

    def save(self, *args, **kwargs):
        '''自动更新记录的 创建时间 和 修改时间'''
        if not self.gmt_create:
            self.gmt_create = now()

        self.gmt_modify = now()

        self.version += 1

        return super(ModelBase, self).save(*args, **kwargs)

    class Meta:
        # ordering = ('-gmt_create', )
        ordering = ('-id', )
        abstract = True