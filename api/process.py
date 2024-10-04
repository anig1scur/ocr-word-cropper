from http.server import BaseHTTPRequestHandler
import base64
import json

from ..main import ocr_and_crop_words_for_api

# vercel serverless 内存限制所以跑不了 .....


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode("utf-8"))

        image_data = base64.b64decode(data["image"])
        target_words = data["target_words"]

        result = ocr_and_crop_words_for_api(image_data, target_words)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())
        return
