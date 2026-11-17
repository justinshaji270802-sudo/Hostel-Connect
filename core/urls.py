
from django.urls import path
from . import views

urlpatterns = [
    path("", views.home, name="home"),

    path(
        "send-rent-reminder/",
        views.send_rent_reminder,
        name="send_rent_reminder",
    ),

    path("register/", views.register, name="register"),
    path("login/", views.user_login, name="login"),
    path("logout/", views.user_logout, name="logout"),

    path("dashboard/", views.dashboard, name="dashboard"),
    path("admin-dashboard/", views.admin_dashboard, name="admin_dashboard"),
    path("student-dashboard/", views.student_dashboard, name="student_dashboard"),
    path("profile/", views.profile, name="profile"),

    path(
        "hostel-rooms-blocks/",
        views.hostel_rooms_blocks,
        name="hostel_rooms_blocks",
    ),
    path("room-allocation/", views.room_allocation, name="room_allocation"),
    path("room-list/", views.room_list, name="room_list"),
    path("add-room/", views.add_room, name="add_room"),
    path("add-block/", views.add_block, name="add_block"),

    path(
        "leave-management/",
        views.leave_management,
        name="leave_management",
    ),
    path(
        "admin-leave-management/",
        views.admin_leave_management,
        name="admin_leave_management",
    ),

    path(
        "complaint-tracking/",
        views.complaint_tracking,
        name="complaint_tracking",
    ),
    path(
        "admin-complaint-management/",
        views.admin_complaint_management,
        name="admin_complaint_management",
    ),

    path("fee-management/", views.fee_management, name="fee_management"),

    path(
        "payment-management/",
        views.payment_management,
        name="payment_management",
    ),

    path("student-list/", views.student_list, name="student_list"),

    path("notice-board/", views.notice_board, name="notice_board"),
    path("reports/", views.reports, name="reports"),

    path("about/", views.about, name="about"),
    path("contact/", views.contact, name="contact"),
]
