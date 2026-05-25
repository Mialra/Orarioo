"""
Serves the user manual PDF, requiring a valid authenticated session.
"""

from pathlib import Path

from django.http import FileResponse, Http404
from rest_framework.permissions import IsAuthenticated
from rest_framework.views import APIView

_PDF_PATH = Path(__file__).resolve().parent / "USER_GUIDE.pdf"


class UserManualPDFView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        if not _PDF_PATH.exists():
            raise Http404
        return FileResponse(
            open(_PDF_PATH, "rb"),
            content_type="application/pdf",
            as_attachment=False,
            filename="manual_usuario_orarioo.pdf",
        )
