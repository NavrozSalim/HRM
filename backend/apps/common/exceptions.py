from django.db.models.deletion import ProtectedError
from rest_framework.exceptions import APIException
from rest_framework.response import Response
from rest_framework.views import exception_handler


class BusinessError(APIException):
    status_code = 400
    default_detail = "The request could not be completed."

    def __init__(self, detail=None, status_code=None):
        if status_code is not None:
            self.status_code = status_code
        super().__init__(detail=detail)


def custom_exception_handler(exc, context):
    if isinstance(exc, ProtectedError):
        return Response(
            {
                "detail": (
                    "This record is linked to attendance, leave, or payroll history and cannot be deleted. "
                    "Deactivate it instead."
                )
            },
            status=400,
        )
    return exception_handler(exc, context)
