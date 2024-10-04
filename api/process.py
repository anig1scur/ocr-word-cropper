from http.server import BaseHTTPRequestHandler
import easyocr
from PIL import Image
import io
import base64
import json


def ocr_and_crop_words(image_bytes, target_words):
    reader = easyocr.Reader(["ch_sim", "en"])
    image = Image.open(io.BytesIO(image_bytes))

    result = reader.readtext(image)

    cropped_images = []

    for idx, (bbox, text, prob) in enumerate(result):
        if any(target_word in text for target_word in target_words):
            top_left, top_right, bottom_right, bottom_left = bbox
            left, top = map(int, top_left)
            right, bottom = map(int, bottom_right)

            left = max(0, left - 2)
            top = max(0, top - 2)
            right = min(image.width, right + 2)
            bottom = min(image.height, bottom + 2)

            cropped_image = image.crop((left, top, right, bottom))

            buffered = io.BytesIO()
            cropped_image.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()

            cropped_images.append({"text": text, "image": img_str})

    return cropped_images


class handler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers["Content-Length"])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data.decode("utf-8"))

        image_data = base64.b64decode(data["image"])
        target_words = data["target_words"]

        result = ocr_and_crop_words(image_data, target_words)

        self.send_response(200)
        self.send_header("Content-type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(result).encode())
        return
