from django.contrib import admin
from .models import Voter, Candidate, Vote, AdminUser

# Register your models here.

@admin.register(Voter)
class VoterAdmin(admin.ModelAdmin):
    list_display = ['phone_number', 'is_verified', 'has_voted', 'registered_at']
    list_filter = ['is_verified', 'has_voted', 'registered_at']
    search_fields = ['phone_number']
    readonly_fields = ['registered_at', 'voted_at']
    ordering = ['-registered_at']

@admin.register(Candidate)
class CandidateAdmin(admin.ModelAdmin):
    list_display = ['name', 'nickname', 'position', 'votes', 'created_at']
    search_fields = ['name', 'nickname', 'position']
    readonly_fields = ['created_at']
    ordering = ['name']

@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ['voter', 'candidate', 'voted_at']
    list_filter = ['candidate', 'voted_at']
    search_fields = ['voter__phone_number', 'candidate__name']
    readonly_fields = ['voted_at']
    ordering = ['-voted_at']

@admin.register(AdminUser)
class AdminUserAdmin(admin.ModelAdmin):
    list_display = ['user', 'created_at']
    search_fields = ['user__username', 'user__email']
    readonly_fields = ['created_at']
