# core/admin.py
from django.contrib import admin
from .models import *

@admin.register(HostelBlock)
class HostelBlockAdmin(admin.ModelAdmin):
    list_display = ['name', 'floors', 'created_at']
    search_fields = ['name']

@admin.register(Room)
class RoomAdmin(admin.ModelAdmin):
    list_display = ['room_number', 'block', 'room_type', 'capacity', 'rent', 'is_available']
    list_filter = ['block', 'room_type', 'is_available']
    search_fields = ['room_number']

@admin.register(StudentProfile)
class StudentProfileAdmin(admin.ModelAdmin):
    list_display = ['student_id', 'user', 'phone', 'room', 'created_at']
    search_fields = ['student_id', 'user__username', 'user__first_name', 'user__last_name']
    list_filter = ['room']

@admin.register(LeaveRequest)
class LeaveRequestAdmin(admin.ModelAdmin):
    list_display = ['student', 'start_date', 'end_date', 'status', 'created_at']
    list_filter = ['status', 'start_date']
    search_fields = ['student__user__first_name', 'student__user__last_name']

@admin.register(Complaint)
class ComplaintAdmin(admin.ModelAdmin):
    list_display = ['subject', 'student', 'category', 'status', 'created_at']
    list_filter = ['category', 'status']
    search_fields = ['subject', 'description']

@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['student', 'amount', 'payment_method', 'payment_date']
    list_filter = ['payment_method']
    search_fields = ['student__user__first_name']

@admin.register(HostelNotice)
class HostelNoticeAdmin(admin.ModelAdmin):
    list_display = ['title', 'created_by', 'is_active', 'created_at']
    list_filter = ['is_active']
    search_fields = ['title']

@admin.register(MaintenanceRequest)
class MaintenanceRequestAdmin(admin.ModelAdmin):
    list_display = ['room', 'student', 'status', 'created_at']
    list_filter = ['status']
    search_fields = ['issue']