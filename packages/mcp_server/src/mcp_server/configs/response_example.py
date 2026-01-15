success_response = {
    "example": {
        "code": 200,
        "message": "OK",
        "data": {
            "request_id": "75935cbd-d4b4-45b8-a7ac-4b8a7bf7ba3c",
            "successful_count": 2,
            "failed_count": 0,
            "results": [
                {
                    "file_id": "b8cba7d1-4e29-4b0a-9836-ae46893c7c81",
                    "file_url": "https://cdn-mineru.openxlab.org.cn/extract/release/2025-12-30/e3a89049-e052-41fb-a557-91d970754f98.html",
                    "url": "https://blog.csdn.net/zl811103/article/details/156276557",
                    "success": True,
                    "size": 0,
                    "error_code": None,
                    "error": None,
                    "zip_url": "https://cdn-mineru.openxlab.org.cn/html/release/2025-12-30/b8cba7d1-4e29-4b0a-9836-ae46893c7c81.zip",
                    "date": "Tue, 30 Dec 2025 07:48:43 GMT",
                },
                {
                    "file_id": "d943a425-c0e0-49ae-a2a8-a6baffc6784e",
                    "file_url": "https://cdn-mineru.openxlab.org.cn/html/release/2025-12-29/af824d1d-1250-4665-b1cb-c2b89ec9e9c5/test_data2.html",
                    "url": "https://arxiv.org/html/2501.00014v1#S4.T1",
                    "success": False,
                    "error_code": 30001,
                    "error": "HTML转Markdown发生错误",
                },
            ],
        },
    }
}

response_example = {
    200: {
        "description": "Successful Response",
        "content": {"application/json": success_response},
    },
    402: {
        "description": "Fail Response",
        "content": {"application/json": {"example": {"code": 402, "message": "params error", "data": None}}},
    },
    422: {
        "description": "Fail Response",
        "content": {"application/json": {"example": {"code": 402, "message": "content error", "data": None}}},
    },
}
