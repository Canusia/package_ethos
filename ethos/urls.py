from django.urls import path, include
from django.contrib.auth.decorators import user_passes_test

from rest_framework import routers

from .views.status import status_page, run_method

from .views.academic_periods import (
    lookup_academic_period,
    create_from_sis as academic_year_create_from_sis,
)
from .views.sections import (
    trigger_section_import,
    section_import_status,
)
from .views.resources import resources_list, resources_sync, resource_detail, EthosResourceViewSet
from .views.logs import logs_list, log_detail, EthosLogViewSet

app_name = 'ethos'


def _has_cis_role(user):
    if user.is_anonymous:
        return False
    return 'ce' in user.get_roles()


router = routers.DefaultRouter()
router.register('ethos-resource', EthosResourceViewSet, basename='ethos-resource')
router.register('ethos-log', EthosLogViewSet, basename='ethos-log')

urlpatterns = [
    path('api/', include(router.urls)),

    path('status/', user_passes_test(_has_cis_role, login_url='/')(status_page), name='ethos_status'),
    path('status/run/', user_passes_test(_has_cis_role, login_url='/')(run_method), name='ethos_run_method'),

    path('academic_periods/lookup/', user_passes_test(_has_cis_role, login_url='/')(lookup_academic_period), name='lookup_academic_period'),
    path('academic_periods/create_from_sis/', user_passes_test(_has_cis_role, login_url='/')(academic_year_create_from_sis), name='academic_year_create_from_sis'),

    path('sections/import/', user_passes_test(_has_cis_role, login_url='/')(trigger_section_import), name='ethos_section_import'),
    path('sections/import/status/', user_passes_test(_has_cis_role, login_url='/')(section_import_status), name='ethos_section_import_status'),

    path('resources/', user_passes_test(_has_cis_role, login_url='/')(resources_list), name='ethos_resources'),
    path('resources/sync/', user_passes_test(_has_cis_role, login_url='/')(resources_sync), name='ethos_resources_sync'),
    path('resources/<int:pk>/', user_passes_test(_has_cis_role, login_url='/')(resource_detail), name='ethos_resource_detail'),

    path('logs/', user_passes_test(_has_cis_role, login_url='/')(logs_list), name='ethos_logs'),
    path('logs/<int:pk>/', user_passes_test(_has_cis_role, login_url='/')(log_detail), name='ethos_log_detail'),
]
