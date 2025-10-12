"""
URL configuration for Voting project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.0/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from django.conf import settings
from django.conf.urls.static import static
from VotingApp import views

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', views.landing_page, name='landing'),
    path('login/', views.login_page, name='login'),
    path('results/', views.results_page, name='results'),
    path('admin-login/', views.admin_login, name='admin_login'),
    path('admin-logout/', views.admin_logout, name='admin_logout'),
    path('add-voters/', views.add_voters, name='add_voters'),
    path('delete-voter/<int:voter_id>/', views.delete_voter, name='delete_voter'),
    path('add-candidates/', views.add_candidates, name='add_candidates'),
    path('edit-candidate/<int:candidate_id>/', views.edit_candidate, name='edit_candidate'),
    path('vote/', views.vote, name='vote'),
    path('public-results/', views.public_results, name='public_results'),
    path('admin-change-password/', views.admin_change_password, name='admin_change_password'),
    path('election-settings/', views.election_settings, name='election_settings'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
