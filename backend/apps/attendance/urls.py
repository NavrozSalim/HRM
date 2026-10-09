from django.urls import path

from apps.attendance.views import (
    AttendanceGridView,
    AttendanceRecordListView,
    BiometricView,
    BulkAttendanceView,
    CheckInView,
    CheckOutView,
    CloseDayView,
    DailyAttendanceView,
    ImportAttendanceView,
    MarkAttendanceView,
    PunctualityView,
)

urlpatterns = [
    path("attendance/daily/", DailyAttendanceView.as_view(), name="attendance-daily"),
    path("attendance/grid/", AttendanceGridView.as_view(), name="attendance-grid"),
    path("attendance/mark/", MarkAttendanceView.as_view(), name="attendance-mark"),
    path("attendance/bulk/", BulkAttendanceView.as_view(), name="attendance-bulk"),
    path("attendance/check-in/", CheckInView.as_view(), name="attendance-check-in"),
    path("attendance/check-out/", CheckOutView.as_view(), name="attendance-check-out"),
    path("attendance/import/", ImportAttendanceView.as_view(), name="attendance-import"),
    path("attendance/close-day/", CloseDayView.as_view(), name="attendance-close-day"),
    path("attendance/punctuality/", PunctualityView.as_view(), name="attendance-punctuality"),
    path("attendance/records/", AttendanceRecordListView.as_view(), name="attendance-records"),
    path("attendance/biometric/", BiometricView.as_view(), name="attendance-biometric"),
]
