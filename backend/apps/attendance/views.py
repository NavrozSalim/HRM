from datetime import datetime

from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.attendance.models import AttendanceRecord
from apps.attendance.services import (
    bulk_mark,
    employee_check_in,
    employee_check_out,
    import_workbook,
    local_hhmm,
    materialize_employee,
    office_now,
    shift_template,
    upsert_attendance,
)
from apps.common.exceptions import BusinessError
from apps.common.money import hours
from apps.common.pagination import page_list
from apps.common.permissions import IsHROrSuper
from apps.employees.services import can_manage_attendance, visible_employees
from apps.insights.services import fact_status, facts_for_employees
from apps.organization.models import OfficeSettings
from apps.payroll.services import preview_employee


def _parse_date(value, fallback):
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise BusinessError("Use dates in YYYY-MM-DD format.") from exc


def _row(employee, day, packet, tz_name):
    fact = next(item for item in packet["facts"] if item["date"] == day)
    stored = packet["attendance"].get(day)
    projected = stored is None
    return {
        "employee_id": employee.id,
        "employee_code": employee.employee_code,
        "full_name": employee.full_name,
        "department": employee.department.name if employee.department_id else "",
        "department_id": employee.department_id,
        "record_id": stored.get("id") if stored else None,
        "shift_slot": stored.get("shift_slot") if stored else 1,
        "extra_slots": stored.get("extra_slots", 0) if stored else 0,
        "status": fact_status(fact),
        "check_in": stored["check_in"].isoformat() if stored and stored.get("check_in") else None,
        "check_out": stored["check_out"].isoformat() if stored and stored.get("check_out") else None,
        "check_in_time": local_hhmm(stored.get("check_in") if stored else None, tz_name),
        "check_out_time": local_hhmm(stored.get("check_out") if stored else None, tz_name),
        "late_minutes": fact["late_minutes"],
        "early_departure_minutes": fact["early_minutes"],
        "working_hours": format(hours(fact["working_minutes"]), "f"),
        "overtime_hours": format(hours(fact["overtime_minutes"]), "f"),
        "incomplete": fact["incomplete"],
        "notes": stored.get("notes", "") if stored else "",
        "projected": projected,
    }


class DailyAttendanceView(APIView):
    def get(self, request):
        office = OfficeSettings.load()
        day = _parse_date(request.query_params.get("date"), office_now(office).date())
        employees = visible_employees(request.user).filter(status__in=["active", "on_notice"])
        if request.query_params.get("department"):
            employees = employees.filter(department_id=request.query_params["department"])
        if request.query_params.get("search"):
            term = request.query_params["search"]
            employees = employees.filter(first_name__icontains=term) | employees.filter(last_name__icontains=term) | employees.filter(employee_code__icontains=term)
        roster = list(employees.distinct().order_by("employee_code"))
        bundled = facts_for_employees(roster, day.year, day.month, day, office)
        tz_name = office.timezone
        rows = [_row(employee, day, bundled[employee.id], tz_name) for employee in roster]
        status = request.query_params.get("status")
        if status:
            rows = [row for row in rows if row["status"] == status]
        payload = page_list(request, rows)
        payload["date"] = day.isoformat()
        return Response(payload)


class AttendanceGridView(APIView):
    def get(self, request):
        office = OfficeSettings.load()
        today = office_now(office).date()
        try:
            year = int(request.query_params.get("year", today.year))
            month = int(request.query_params.get("month", today.month))
        except ValueError as exc:
            raise BusinessError("Year and month must be numbers.") from exc
        employees = visible_employees(request.user).filter(status__in=["active", "on_notice"])
        if request.query_params.get("department"):
            employees = employees.filter(department_id=request.query_params["department"])
        if request.query_params.get("search"):
            term = request.query_params["search"]
            employees = employees.filter(first_name__icontains=term) | employees.filter(last_name__icontains=term) | employees.filter(employee_code__icontains=term)
        roster = list(employees.distinct().order_by("employee_code"))
        page = page_list(request, roster, page_size=15)
        bundled = facts_for_employees(page["results"], year, month, today, office)
        results = []
        days = []
        for employee in page["results"]:
            facts = bundled[employee.id]["facts"]
            if not days:
                days = [fact["date"].isoformat() for fact in facts]
            results.append(
                {
                    "employee_id": employee.id,
                    "employee_code": employee.employee_code,
                    "full_name": employee.full_name,
                    "department": employee.department.name if employee.department_id else "",
                    "cells": [
                        {
                            "date": fact["date"].isoformat(),
                            "status": fact_status(fact),
                            "late_minutes": fact["late_minutes"],
                            "record_id": bundled[employee.id]["attendance"].get(fact["date"], {}).get("id"),
                            "projected": fact["date"] not in bundled[employee.id]["attendance"],
                        }
                        for fact in facts
                    ],
                }
            )
        return Response({"year": year, "month": month, "days": days, "count": page["count"], "page": page["page"], "results": results})


class MarkAttendanceView(APIView):
    def post(self, request):
        employee = visible_employees(request.user).filter(pk=request.data.get("employee_id")).first()
        if employee is None:
            raise BusinessError("Employee was not found.", status_code=404)
        if not can_manage_attendance(request.user, employee):
            raise BusinessError("You cannot mark attendance for this employee.", status_code=403)
        day = _parse_date(request.data.get("date"), None)
        if day is None:
            raise BusinessError("A date is required.")
        record = upsert_attendance(
            employee=employee,
            day=day,
            actor=request.user,
            shift_slot=request.data.get("shift_slot") or 1,
            check_in=request.data.get("check_in"),
            check_out=request.data.get("check_out"),
            status=request.data.get("status") or None,
            notes=request.data.get("notes") or "",
            break_minutes=request.data.get("break_minutes"),
            reason=request.data.get("reason") or "",
            request=request,
        )
        return Response({"id": record.id, "status": record.status, "late_minutes": record.late_minutes, "working_minutes": record.working_minutes})


class BulkAttendanceView(APIView):
    def post(self, request):
        day = _parse_date(request.data.get("date"), None)
        if day is None:
            raise BusinessError("A date is required.")
        employee_ids = request.data.get("employee_ids") or []
        if not employee_ids:
            raise BusinessError("Choose at least one employee.")
        result = bulk_mark(
            actor=request.user,
            day=day,
            employee_ids=employee_ids,
            check_in=request.data.get("check_in"),
            check_out=request.data.get("check_out"),
            status=request.data.get("status") or None,
            notes=request.data.get("notes") or "",
            reason=request.data.get("reason") or "",
            request=request,
        )
        return Response(result)


class CheckInView(APIView):
    def post(self, request):
        record = employee_check_in(request.user, notes=request.data.get("notes") or "", request=request)
        return Response({"id": record.id, "status": record.status, "check_in": record.check_in})


class CheckOutView(APIView):
    def post(self, request):
        record = employee_check_out(request.user, notes=request.data.get("notes") or "", request=request)
        return Response({"id": record.id, "status": record.status, "check_out": record.check_out})


class ImportAttendanceView(APIView):
    permission_classes = [IsHROrSuper]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        upload = request.FILES.get("file")
        if upload is None:
            raise BusinessError("Choose an Excel file to import.")
        return Response(import_workbook(upload, request.user, request=request))


class CloseDayView(APIView):
    permission_classes = [IsHROrSuper]

    def post(self, request):
        office = OfficeSettings.load()
        day = _parse_date(request.data.get("date"), office_now(office).date() - __import__("datetime").timedelta(days=1))
        from apps.attendance.services import assert_month_editable

        assert_month_editable(day)
        created = 0
        for employee in visible_employees(request.user).filter(status__in=["active", "on_notice"]):
            created += materialize_employee(employee, day.year, day.month, day + __import__("datetime").timedelta(days=1), actor=request.user)
        return Response({"detail": f"Locked past attendance through {day.isoformat()}.", "created": created})


class PunctualityView(APIView):
    def get(self, request):
        office = OfficeSettings.load()
        today = office_now(office).date()
        year = int(request.query_params.get("year", today.year))
        month = int(request.query_params.get("month", today.month))
        employees = visible_employees(request.user).filter(status__in=["active", "on_notice"])
        if request.query_params.get("department"):
            employees = employees.filter(department_id=request.query_params["department"])
        rows = []
        departments = {}
        for employee in employees.order_by("employee_code"):
            preview = preview_employee(employee, year, month, today=today, office=office)
            counts = preview["counts"]
            row = {
                "employee_id": employee.id,
                "employee_code": employee.employee_code,
                "full_name": employee.full_name,
                "department": employee.department.name if employee.department_id else "Unassigned",
                "late_count": counts["late_count"],
                "late_minutes": counts["late_minutes"],
                "absent_days": format(counts["absent_days"], "f"),
                "paid_leave_days": format(counts["paid_leave_days"], "f"),
                "unpaid_leave_days": format(counts["unpaid_leave_days"], "f"),
                "half_days": counts["half_days"],
                "early_departures": counts["early_departures"],
                "overtime_hours": format(counts["overtime_hours"], "f"),
                "consecutive_absences": counts["consecutive_absences"],
                "attendance_percentage": format(counts["attendance_percentage"], "f"),
                "punctuality_percentage": None if counts["punctuality_percentage"] is None else format(counts["punctuality_percentage"], "f"),
                "scheduled_working_days": counts["scheduled_working_days"],
                "present_days": format(counts["present_days"], "f"),
                "warning": counts["late_count"] >= office.monthly_late_warning_threshold,
            }
            rows.append(row)
            bucket = departments.setdefault(row["department"], {"department": row["department"], "late_count": 0, "absent_days": 0, "employees": 0, "attendance_total": 0})
            bucket["late_count"] += row["late_count"]
            bucket["absent_days"] += float(row["absent_days"])
            bucket["employees"] += 1
            bucket["attendance_total"] += float(row["attendance_percentage"])
        department_rows = [
            {
                "department": item["department"],
                "late_count": item["late_count"],
                "absent_days": f"{item['absent_days']:.2f}",
                "attendance_percentage": f"{(item['attendance_total'] / item['employees']) if item['employees'] else 0:.2f}",
            }
            for item in departments.values()
        ]
        payload = page_list(request, rows)
        payload["departments"] = department_rows
        payload["year"] = year
        payload["month"] = month
        payload["monthly_late_warning_threshold"] = office.monthly_late_warning_threshold
        return Response(payload)


class AttendanceRecordListView(APIView):
    def get(self, request):
        qs = AttendanceRecord.objects.filter(employee__in=visible_employees(request.user)).select_related("employee", "shift")
        if request.query_params.get("employee"):
            qs = qs.filter(employee_id=request.query_params["employee"])
        if request.query_params.get("from"):
            qs = qs.filter(date__gte=request.query_params["from"])
        if request.query_params.get("to"):
            qs = qs.filter(date__lte=request.query_params["to"])
        if request.query_params.get("status"):
            qs = qs.filter(status=request.query_params["status"])
        office = OfficeSettings.load()
        rows = [
            {
                "id": record.id,
                "employee_id": record.employee_id,
                "employee_code": record.employee.employee_code,
                "full_name": record.employee.full_name,
                "date": record.date.isoformat(),
                "shift_slot": record.shift_slot,
                "status": record.status,
                "check_in_time": local_hhmm(record.check_in, office.timezone),
                "check_out_time": local_hhmm(record.check_out, office.timezone),
                "late_minutes": record.late_minutes,
                "early_departure_minutes": record.early_departure_minutes,
                "working_hours": format(hours(record.working_minutes), "f"),
                "overtime_hours": format(hours(record.overtime_minutes), "f"),
                "incomplete": record.is_incomplete,
                "notes": record.notes,
                "source": record.source,
            }
            for record in qs.order_by("-date")[:500]
        ]
        return Response({"results": rows})


class BiometricView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        office = OfficeSettings.load()
        return Response(
            {
                "connected": False,
                "enabled": office.biometric_enabled,
                "message": (
                    "No biometric device is configured. Attendance can be marked manually, by employee check-in, "
                    "or by Excel import. A future adapter can post punches here only after a real device is connected "
                    "and biometric ingestion is enabled by a super admin."
                ),
            }
        )

    def post(self, request):
        office = OfficeSettings.load()
        if not office.biometric_enabled:
            return Response(
                {
                    "connected": False,
                    "detail": "Biometric ingestion is disabled. No device is connected, so nothing was recorded.",
                },
                status=409,
            )
        return Response(
            {"connected": False, "detail": "Biometric ingestion is enabled in settings, but no device adapter is installed."},
            status=501,
        )
