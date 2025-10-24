from django_filters.rest_framework import DjangoFilterBackend

from rest_framework import viewsets
from rest_framework import filters
from rest_framework.permissions import IsAuthenticated

from aichat.pagination import StandardResultsPagination

from llm.models import Llm
from llm.serializers import LlmSerializer


# Create your views here.

class LlmViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = Llm.objects.all()
    serializer_class = LlmSerializer
    pagination_class = StandardResultsPagination
    filter_backends = [filters.SearchFilter, DjangoFilterBackend]
    filterset_fields = ['name', 'value']
    permission_classes = (IsAuthenticated, )

    def get_queryset(self):
        queryset = super().get_queryset()
        queryset = queryset.filter(status=Llm.STATUS_INLINE)
        return queryset

