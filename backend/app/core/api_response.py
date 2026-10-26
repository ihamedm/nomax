from fastapi.responses import JSONResponse

from app.core.errors import AppError


def build_data_response(data: object, meta: object = None, status_code: int = 200):
    body: dict = {"data": data}
    if meta is not None:
        body["meta"] = meta
    return JSONResponse(status_code=status_code, content=body)


def build_error_response(exc: AppError) -> JSONResponse:
    content: dict = {"error": {"code": exc.code, "message": exc.message}}
    if exc.details is not None:
        content["error"]["details"] = exc.details
    return JSONResponse(status_code=exc.status_code, content=content)
