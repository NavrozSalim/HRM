from rest_framework.pagination import PageNumberPagination


class DefaultPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "page_size"
    max_page_size = 200


def page_list(request, items, page_size=25):
    try:
        page = max(int(request.query_params.get("page", 1) or 1), 1)
    except (TypeError, ValueError):
        page = 1
    try:
        size = int(request.query_params.get("page_size", page_size) or page_size)
    except (TypeError, ValueError):
        size = page_size
    size = min(max(size, 1), 200)
    total = len(items)
    start = (page - 1) * size
    return {"count": total, "page": page, "page_size": size, "results": items[start : start + size]}
