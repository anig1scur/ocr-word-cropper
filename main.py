import easyocr
from PIL import Image
import os
import io
import base64


def ocr_and_crop_core(image, target_words, reader):
    result = reader.readtext(image)
    cropped_items = []

    for idx, (bbox, text, prob) in enumerate(result):
        if any(target_word in text for target_word in target_words):
            top_left, _, bottom_right, _ = bbox
            left, top = map(int, top_left)
            right, bottom = map(int, bottom_right)

            left = max(0, left - 2)
            top = max(0, top - 2)
            right = min(image.width, right + 2)
            bottom = min(image.height, bottom + 2)

            cropped_image = image.crop((left, top, right, bottom))
            cropped_items.append((text, cropped_image))

    return cropped_items


def ocr_and_crop_words_for_api(image_bytes, target_words):
    reader = easyocr.Reader(["ch_sim", "en"])
    image = Image.open(io.BytesIO(image_bytes))

    cropped_items = ocr_and_crop_core(image, target_words, reader)

    return [
        {
            "text": text,
            "image": base64.b64encode(
                io.BytesIO(cropped_image.tobytes()).getvalue()
            ).decode(),
        }
        for text, cropped_image in cropped_items
    ]


def ocr_and_crop_words(image_path, target_words, output_dir):
    image_name = os.path.splitext(os.path.basename(image_path))[0]

    image_output_dir = os.path.join(output_dir, image_name)

    if os.path.exists(image_output_dir):
        print(f"Skipping already processed image: {image_path}")
        return

    os.makedirs(image_output_dir, exist_ok=True)

    reader = easyocr.Reader(["ch_sim", "en"])
    image = Image.open(image_path)

    cropped_items = ocr_and_crop_core(image, target_words, reader)

    for idx, (text, cropped_image) in enumerate(cropped_items):
        output_path = os.path.join(image_output_dir, f"{idx}_{text}.png")
        cropped_image.save(output_path)
        print(f"Saved: {output_path}")


if __name__ == "__main__":
    image_dir = "images"
    target_words = ["限定", "品质", "贴近自然", "好口感"]
    output_dir = "output"

    os.makedirs(output_dir, exist_ok=True)

    for image_file in os.listdir(image_dir):
        if image_file.lower().endswith((".png", ".jpg", ".jpeg")):
            image_path = os.path.join(image_dir, image_file)
            ocr_and_crop_words(image_path, target_words, output_dir)
