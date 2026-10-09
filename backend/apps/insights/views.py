from datetime import datetime

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.attendance.models import AttendanceRecord
from apps.attendance.services import office_now
from apps.common.exceptions import BusinessError
from apps.common.models import AuditLog
from apps.common.permissions import IsHROrSuper
from apps.employees.services import visible_employees
from apps.insights.exports import choose_format, xlsx_response
from apps.insights.services import build_dashboard, company_monthly_report, employee_monthly_report
from apps.leaves.models import LeaveRequest
from apps.payroll.models import PayrollRecord


def _date(value, fallback):
    if not value:
        return fallback
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError as exc:
        raise BusinessError("Use YYYY-MM-DD dates.") from exc


class HealthView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({"status": "ok"})


class DashboardView(APIView):
    def get(self, request):
        office_day = office_now().date()
        day = _date(request.query_params.get("date"), office_day)
        department = request.query_params.get("department") or None
        return Response(build_dashboard(request.user, day, department))


class EmployeeReportView(APIView):
    def get(self, request):
        employee = visible_employees(request.user).filter(pk=request.query_params.get("employee")).first()
        if employee is None:
            raise BusinessError("Choose an employee you can access.", status_code=404)
        today = office_now().date()
        year = int(request.query_params.get("year", today.year))
        month = int(request.query_params.get("month", today.month))
        report = employee_monthly_report(employee, year, month, request.user)
        if request.query_params.get("format") in {"xlsx", "pdf"}:
            headers = ["Field", "Value"]
            rows = [[key, value] for key, value in report["attendance"].items()]
            if report["salary"]:
                rows.append(["Gross salary", report["salary"].get("gross_salary")])
                rows.append(["Total deductions", report["salary"].get("total_deductions")])
                rows.append(["Net salary", report["salary"].get("net_salary")])
                rows.append(["Payment status", report["salary"].get("payment_status")])
            return choose_format(request, f"employee-report-{employee.employee_code}-{year}-{month:02d}", report["period"]["label"], headers, rows)
        return Response(report)


class CompanyReportView(APIView):
    def get(self, request):
        if request.user.role not in {"super_admin", "management", "hr_manager", "accountant", "department_manager"}:
            raise BusinessError("Company reports are limited to managers.", status_code=403)
        today = office_now().date()
        year = int(request.query_params.get("year", today.year))
        month = int(request.query_params.get("month", today.month))
        department = request.query_params.get("department") or None
        report = company_monthly_report(request.user, year, month, department)
        if request.query_params.get("format") in {"xlsx", "pdf"}:
            headers = ["Code", "Name", "Department", "Present", "Absent", "Late", "Attendance %", "Net", "Payment"]
            rows = []
            for item in report["employees"]:
                salary = item["salary"] or {}
                rows.append([
                    item["employee"]["employee_code"],
                    item["employee"]["full_name"],
                    item["employee"]["department"],
                    item["attendance"].get("present_days"),
                    item["attendance"].get("absent_days"),
                    item["attendance"].get("late_count"),
                    item["attendance"].get("attendance_percentage"),
                    salary.get("net_salary", ""),
                    salary.get("payment_status", ""),
                ])
            return choose_format(request, f"company-report-{year}-{month:02d}", report["period"]["label"], headers, rows, landscape_page=True)
        return Response(report)


class ExportView(APIView):
    def get(self, request, kind):
        user = request.user
        employees = visible_employees(user)
        if request.query_params.get("department"):
            employees = employees.filter(department_id=request.query_params["department"])
        if kind == "employees":
            if request.query_params.get("status"):
                employees = employees.filter(status=request.query_params["status"])
            headers = ["Code", "Name", "Email", "Phone", "Department", "Title", "Status", "Joining date", "Shift"]
            rows = [
                [item.employee_code, item.full_name, item.email, item.phone, getattr(item.department, "name", ""), getattr(item.job_title, "name", ""), item.status, item.joining_date.isoformat(), getattr(item.shift, "name", "")]
                for item in employees
            ]
            if user.role in {"super_admin", "management", "hr_manager", "accountant"}:
                headers += ["Salary type", "Basic salary"]
                for index, item in enumerate(employees):
                    rows[index] += [item.salary_type, format(item.basic_salary, "f")]
            return choose_format(request, "employees", "Employee directory", headers, rows, landscape_page=True)
        if kind == "attendance":
            start = _date(request.query_params.get("from"), office_now().date().replace(day=1))
            end = _date(request.query_params.get("to"), office_now().date())
            records = AttendanceRecord.objects.filter(employee__in=employees, date__range=(start, end)).select_related("employee")
            if request.query_params.get("status"):
                records = records.filter(status=request.query_params["status"])
            headers = ["Code", "Name", "Date", "Status", "Check in", "Check out", "Late minutes", "Early minutes", "Working minutes", "Overtime minutes", "Incomplete"]
            rows = [
                [item.employee.employee_code, item.employee.full_name, item.date.isoformat(), item.status, item.check_in.isoformat() if item.check_in else "", item.check_out.isoformat() if item.check_out else "", item.late_minutes, item.early_departure_minutes, item.working_minutes, item.overtime_minutes, item.is_incomplete]
                for item in records.order_by("date", "employee__employee_code")
            ]
            return choose_format(request, "attendance", "Attendance", headers, rows, landscape_page=True)
        if kind == "attendance-template":
            return xlsx_response(
                "attendance-import-template.xlsx",
                [{
                    "title": "Attendance",
                    "headers": ["employee_code", "date", "check_in", "check_out", "status", "notes", "shift_slot", "break_minutes", "reason"],
                    "rows": [["EMP-001", "2026-10-01", "09:05", "17:00", "", "", 1, 60, ""]],
                }],
            )
        if kind == "leave":
            qs = LeaveRequest.objects.filter(employee__in=employees).select_related("employee", "leave_type")
            if request.query_params.get("status"):
                qs = qs.filter(status=request.query_params["status"])
            headers = ["Code", "Name", "Type", "Start", "End", "Days", "Part", "Status", "Reason"]
            rows = [[item.employee.employee_code, item.employee.full_name, item.leave_type.name, item.start_date.isoformat(), item.end_date.isoformat(), format(item.total_days, "f"), item.day_part, item.status, item.reason] for item in qs]
            return choose_format(request, "leave", "Leave requests", headers, rows, landscape_page=True)
        if kind == "payroll":
            if user.role not in {"super_admin", "management", "accountant", "hr_manager"}:
                raise BusinessError("You cannot export payroll.", status_code=403)
            qs = PayrollRecord.objects.filter(employee__in=employees).select_related("employee", "period")
            if request.query_params.get("period"):
                qs = qs.filter(period_id=request.query_params["period"])
            if request.query_params.get("payment_status"):
                qs = qs.filter(payment_status=request.query_params["payment_status"])
            headers = ["Period", "Code", "Name", "Basic", "Allowances", "Bonuses", "Overtime", "Gross", "Deductions", "Net", "Status", "Paid"]
            rows = [[f"{item.period.year}-{item.period.month:02d}", item.employee.employee_code, item.employee.full_name, format(item.basic_salary, "f"), format(item.allowances_total, "f"), format(item.bonuses_total, "f"), format(item.overtime_pay, "f"), format(item.gross_salary, "f"), format(item.total_deductions, "f"), format(item.net_salary, "f"), item.payment_status, format(item.amount_paid, "f")] for item in qs]
            return choose_format(request, "payroll", "Payroll", headers, rows, landscape_page=True)
        raise BusinessError("Unknown export.", status_code=404)


class SearchView(APIView):
    def get(self, request):
        term = (request.query_params.get("q") or "").strip()
        if len(term) < 2:
            return Response({"employees": [], "leave_requests": []})
        employees = visible_employees(request.user).filter(first_name__icontains=term) | visible_employees(request.user).filter(last_name__icontains=term) | visible_employees(request.user).filter(employee_code__icontains=term) | visible_employees(request.user).filter(email__icontains=term)
        people = [
            {"id": item.id, "employee_code": item.employee_code, "full_name": item.full_name, "department": item.department.name if item.department_id else "", "status": item.status}
            for item in employees.distinct()[:20]
        ]
        leaves = LeaveRequest.objects.filter(employee__in=visible_employees(request.user), reason__icontains=term).select_related("employee", "leave_type")[:10]
        return Response(
            {
                "employees": people,
                "leave_requests": [
                    {"id": item.id, "employee": item.employee.full_name, "type": item.leave_type.name, "status": item.status, "start_date": item.start_date.isoformat()}
                    for item in leaves
                ],
            }
        )


class AuditLogView(APIView):
    def get(self, request):
        if request.user.role not in {"super_admin", "management", "hr_manager", "accountant"}:
            raise BusinessError("You cannot view the audit log.", status_code=403)
        qs = AuditLog.objects.select_related("actor")
        if request.user.role == "accountant":
            qs = qs.filter(model_name__startswith="payroll")
        if request.query_params.get("q"):
            qs = qs.filter(summary__icontains=request.query_params["q"])
        return Response(
            {
                "results": [
                    {
                        "id": item.id,
                        "actor": item.actor.display_name if item.actor_id else "System",
                        "action": item.action,
                        "summary": item.summary,
                        "model_name": item.model_name,
                        "object_id": item.object_id,
                        "reason": item.reason,
                        "changes": item.changes,
                        "created_at": item.created_at.isoformat(),
                    }
                    for item in qs[:200]
                ]
            }
        )
